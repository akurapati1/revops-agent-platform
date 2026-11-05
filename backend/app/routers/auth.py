from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.core.ratelimit import auth_rate_limit
from app.core.security import create_state_token, decode_token
from app.db import get_session
from app.deps import Ctx, get_ctx, get_user_only
from app.models import Membership, Org, User
from app.schemas.api import AcceptInviteIn, LoginIn, MeOut, OrgBrief, RefreshIn, SignupIn, SwitchOrgIn, TokenPair, UserOut
from app.services import auth as auth_svc
from app.services import oauth as oauth_svc
from app.services import orgs as org_svc

router = APIRouter(prefix="/auth", tags=["auth"])

# Tests can inject an httpx transport to fake the provider.
oauth_transport: httpx.AsyncBaseTransport | None = None


@router.post("/signup", response_model=TokenPair, status_code=201, dependencies=[Depends(auth_rate_limit)])
async def signup(data: SignupIn, session: AsyncSession = Depends(get_session)):
    return await auth_svc.signup(session, data)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(auth_rate_limit)])
async def login(data: LoginIn, session: AsyncSession = Depends(get_session)):
    return await auth_svc.login(session, data.email, data.password)


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(auth_rate_limit)])
async def refresh(data: RefreshIn, session: AsyncSession = Depends(get_session)):
    return await auth_svc.refresh(session, data.refresh_token)


async def _orgs_for(session: AsyncSession, user_id: str) -> list[OrgBrief]:
    rows = (await session.execute(select(Membership, Org).join(Org, Org.id == Membership.org_id)
                                  .where(Membership.user_id == user_id).order_by(Membership.created_at))).all()
    return [OrgBrief(id=o.id, name=o.name, slug=o.slug, role=m.role) for m, o in rows]


@router.get("/me", response_model=MeOut)
async def me(ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    orgs = await _orgs_for(session, ctx.user.id)
    return MeOut(user=UserOut.model_validate(ctx.user),
                 org=OrgBrief(id=ctx.org.id, name=ctx.org.name, slug=ctx.org.slug, role=ctx.role), orgs=orgs)


@router.post("/switch-org", response_model=TokenPair)
async def switch_org(data: SwitchOrgIn, user: User = Depends(get_user_only), session: AsyncSession = Depends(get_session)):
    if not await session.scalar(select(Membership.id).where(Membership.user_id == user.id, Membership.org_id == data.org_id)):
        raise NotFound("Organization not found")
    return auth_svc.issue_tokens(user.id, data.org_id)


@router.post("/accept-invite", response_model=TokenPair)
async def accept_invite(data: AcceptInviteIn, user: User = Depends(get_user_only), session: AsyncSession = Depends(get_session)):
    org = await org_svc.accept_invite(session, data.token, user)
    return auth_svc.issue_tokens(user.id, org.id)


@router.get("/oauth/providers")
async def providers():
    s = get_settings()
    return {p: s.oauth_configured(p) for p in oauth_svc.PROVIDERS}


@router.get("/oauth/{provider}/login")
async def oauth_login(provider: str):
    s = get_settings()
    if provider not in oauth_svc.PROVIDERS or not s.oauth_configured(provider):
        raise NotFound(f"{provider} sign-in is not configured")
    return RedirectResponse(oauth_svc.authorize_url(s, provider, create_state_token({"p": provider})))


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str | None = Query(default=None), state: str = Query(default=""),
                         error: str | None = Query(default=None), session: AsyncSession = Depends(get_session)):
    s = get_settings()
    fail = f"{s.frontend_url.rstrip('/')}/login?{urlencode({'error': 'oauth_failed'})}"
    if provider not in oauth_svc.PROVIDERS or not s.oauth_configured(provider) or error or not code:
        return RedirectResponse(fail)
    try:
        if decode_token(state, "oauth_state").get("p") != provider:
            return RedirectResponse(fail)
        profile = await oauth_svc.fetch_profile(s, provider, code, oauth_transport)
        tokens = await auth_svc.oauth_login(session, provider, profile.provider_user_id, profile.email, profile.name, profile.avatar)
    except (ValueError, AppError):
        return RedirectResponse(fail)
    frag = urlencode({"access_token": tokens.access_token, "refresh_token": tokens.refresh_token})
    return RedirectResponse(f"{s.frontend_url.rstrip('/')}/auth/callback#{frag}")

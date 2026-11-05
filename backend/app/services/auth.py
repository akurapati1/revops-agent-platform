from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import Conflict, Unauthorized
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models import Invitation, Membership, OAuthAccount, User
from app.schemas.api import SignupIn, TokenPair
from app.services import orgs as org_svc


def issue_tokens(user_id: str, org_id: str | None) -> TokenPair:
    return TokenPair(access_token=create_access_token(user_id, org_id), refresh_token=create_refresh_token(user_id, org_id))


async def first_org_id(session: AsyncSession, user_id: str) -> str | None:
    return await session.scalar(select(Membership.org_id).where(Membership.user_id == user_id).order_by(Membership.created_at))


async def signup(session: AsyncSession, data: SignupIn) -> TokenPair:
    if await session.scalar(select(User.id).where(User.email == data.email)):
        raise Conflict("An account with this email already exists")
    user = User(email=data.email, name=data.name or data.email.split("@")[0], password_hash=hash_password(data.password))
    session.add(user)
    await session.flush()
    org_id: str | None = None
    if data.invite_token:
        inv = await session.scalar(select(Invitation).where(Invitation.token == data.invite_token))
        if not inv or inv.accepted or inv.email != data.email:
            raise Conflict("Invitation is invalid or was issued to a different email")
        org_id = (await org_svc.accept_invite(session, data.invite_token, user)).id
    else:
        org = await org_svc.create_org(session, data.org_name or f"{user.name}'s workspace", user)
        org_id = org.id
    return issue_tokens(user.id, org_id)


async def login(session: AsyncSession, email: str, password: str) -> TokenPair:
    user = await session.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise Unauthorized("Invalid email or password")
    return issue_tokens(user.id, await first_org_id(session, user.id))


async def refresh(session: AsyncSession, refresh_token: str) -> TokenPair:
    try:
        payload = decode_token(refresh_token, "refresh")
    except ValueError as exc:
        raise Unauthorized("Invalid refresh token") from exc
    user = await session.get(User, payload["sub"])
    if not user or not user.is_active:
        raise Unauthorized("Invalid refresh token")
    org_id = payload.get("org")
    if org_id and not await session.scalar(select(Membership.id).where(Membership.user_id == user.id, Membership.org_id == org_id)):
        org_id = await first_org_id(session, user.id)
    return issue_tokens(user.id, org_id)


async def oauth_login(session: AsyncSession, provider: str, provider_user_id: str, email: str, name: str,
                      avatar: str | None) -> TokenPair:
    """Sign in (or sign up) via a verified provider identity."""
    acct = await session.scalar(select(OAuthAccount).where(OAuthAccount.provider == provider,
                                                            OAuthAccount.provider_user_id == provider_user_id))
    if acct:
        user = await session.get(User, acct.user_id)
        assert user is not None
    else:
        user = await session.scalar(select(User).where(User.email == email.lower()).options(selectinload(User.memberships)))
        if not user:
            user = User(email=email.lower(), name=name or email.split("@")[0], avatar_url=avatar)
            session.add(user)
            await session.flush()
            await org_svc.create_org(session, f"{user.name}'s workspace", user)
        session.add(OAuthAccount(user_id=user.id, provider=provider, provider_user_id=provider_user_id))
        await session.flush()
    return issue_tokens(user.id, await first_org_id(session, user.id))

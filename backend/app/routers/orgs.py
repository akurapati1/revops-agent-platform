from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import Ctx, get_ctx, require_role
from app.schemas.api import InviteIn, InviteOut, MemberOut, MemberRoleIn, OrgOut, OrgSettings, OrgUpdate
from app.services import orgs as svc

router = APIRouter(prefix="/orgs/current", tags=["org"])


def _out(ctx: Ctx) -> OrgOut:
    o = ctx.org
    return OrgOut(id=o.id, name=o.name, slug=o.slug, role=ctx.role, monthly_token_limit=o.monthly_token_limit,
                  settings=OrgSettings.model_validate(o.settings or {}),
                  webhook_token=o.webhook_token if ctx.role in ("owner", "admin") else None)


@router.get("", response_model=OrgOut)
async def get_org(ctx: Ctx = Depends(get_ctx)):
    return _out(ctx)


@router.patch("", response_model=OrgOut)
async def update_org(data: OrgUpdate, ctx: Ctx = Depends(require_role("admin"))):
    if data.name:
        ctx.org.name = data.name
    if data.monthly_token_limit:
        ctx.org.monthly_token_limit = data.monthly_token_limit
    if data.settings:
        ctx.org.settings = data.settings.model_dump()
    return _out(ctx)


@router.get("/members", response_model=list[MemberOut])
async def list_members(ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return [MemberOut(user_id=u.id, email=u.email, name=u.name, role=m.role, created_at=m.created_at)
            for m, u in await svc.members(session, ctx.org.id)]


@router.patch("/members/{user_id}", response_model=dict)
async def change_role(user_id: str, data: MemberRoleIn, ctx: Ctx = Depends(require_role("admin")),
                      session: AsyncSession = Depends(get_session)):
    m = await svc.change_role(session, ctx.org.id, ctx.role, user_id, data.role)
    return {"user_id": user_id, "role": m.role}


@router.delete("/members/{user_id}", status_code=204)
async def remove_member(user_id: str, ctx: Ctx = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    await svc.remove_member(session, ctx.org.id, ctx.role, user_id)
    return Response(status_code=204)


@router.post("/invitations", response_model=InviteOut, status_code=201)
async def invite(data: InviteIn, ctx: Ctx = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    return await svc.invite(session, ctx.org.id, data.email, data.role)

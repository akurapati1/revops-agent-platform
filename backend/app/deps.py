from dataclasses import dataclass

from fastapi import Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_token
from app.db import get_session
from app.models import Membership, Org, User

ROLE_RANK = {"member": 1, "admin": 2, "owner": 3}


@dataclass
class Ctx:
    user: User
    org: Org
    role: str


async def _resolve(session: AsyncSession, token: str) -> Ctx:
    try:
        payload = decode_token(token, "access")
    except ValueError as exc:
        raise Unauthorized("Invalid or expired token") from exc
    user = await session.get(User, payload["sub"])
    if not user or not user.is_active:
        raise Unauthorized("Unknown user")
    q = select(Membership, Org).join(Org, Org.id == Membership.org_id).where(Membership.user_id == user.id)
    if payload.get("org"):
        q = q.where(Membership.org_id == payload["org"])
    row = (await session.execute(q.order_by(Membership.created_at).limit(1))).first()
    if not row:
        raise Forbidden("You do not belong to an organization")
    return Ctx(user=user, org=row[1], role=row[0].role)


async def get_user_only(authorization: str | None = Header(default=None), session: AsyncSession = Depends(get_session)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Missing bearer token")
    try:
        payload = decode_token(authorization[7:], "access")
    except ValueError as exc:
        raise Unauthorized("Invalid or expired token") from exc
    user = await session.get(User, payload["sub"])
    if not user or not user.is_active:
        raise Unauthorized("Unknown user")
    return user


async def get_ctx(authorization: str | None = Header(default=None), session: AsyncSession = Depends(get_session)) -> Ctx:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Missing bearer token")
    return await _resolve(session, authorization[7:])


async def get_ctx_query_token(token: str = Query(...), session: AsyncSession = Depends(get_session)) -> Ctx:
    """For EventSource, which cannot set headers."""
    return await _resolve(session, token)


def require_role(minimum: str):
    async def dep(ctx: Ctx = Depends(get_ctx)) -> Ctx:
        if ROLE_RANK[ctx.role] < ROLE_RANK[minimum]:
            raise Forbidden(f"Requires {minimum} role")
        return ctx

    return dep

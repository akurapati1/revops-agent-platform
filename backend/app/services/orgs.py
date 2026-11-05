import re
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound
from app.models import Invitation, Membership, Org, User

DEFAULT_SETTINGS = {
    "icp": {"industries": ["B2B SaaS", "FinTech", "Cybersecurity"], "min_employees": 50, "max_employees": 1000,
            "regions": ["North America", "EMEA"]},
    "sender_name": "",
    "product_pitch": "",
}


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    return base[:60]


async def create_org(session: AsyncSession, name: str, owner: User) -> Org:
    slug = slugify(name)
    while await session.scalar(select(Org.id).where(Org.slug == slug)):
        slug = f"{slugify(name)}-{secrets.token_hex(2)}"
    org = Org(name=name, slug=slug, monthly_token_limit=get_settings().default_monthly_token_limit,
              settings={**DEFAULT_SETTINGS, "sender_name": owner.name or ""})
    session.add(org)
    await session.flush()
    session.add(Membership(user_id=owner.id, org_id=org.id, role="owner"))
    await session.flush()
    return org


async def members(session: AsyncSession, org_id: str) -> list[tuple[Membership, User]]:
    q = select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.org_id == org_id).order_by(Membership.created_at)
    return [(m, u) for m, u in (await session.execute(q)).all()]


async def _owner_count(session: AsyncSession, org_id: str) -> int:
    return len((await session.scalars(select(Membership.id).where(Membership.org_id == org_id, Membership.role == "owner"))).all())


async def change_role(session: AsyncSession, org_id: str, actor_role: str, user_id: str, role: str) -> Membership:
    m = await session.scalar(select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id))
    if not m:
        raise NotFound("Member not found")
    if (role == "owner" or m.role == "owner") and actor_role != "owner":
        raise Forbidden("Only owners can change owner roles")
    if m.role == "owner" and role != "owner" and await _owner_count(session, org_id) <= 1:
        raise Conflict("An organization needs at least one owner")
    m.role = role
    return m


async def remove_member(session: AsyncSession, org_id: str, actor_role: str, user_id: str) -> None:
    m = await session.scalar(select(Membership).where(Membership.org_id == org_id, Membership.user_id == user_id))
    if not m:
        raise NotFound("Member not found")
    if m.role == "owner":
        if actor_role != "owner":
            raise Forbidden("Only owners can remove owners")
        if await _owner_count(session, org_id) <= 1:
            raise Conflict("An organization needs at least one owner")
    await session.delete(m)


async def invite(session: AsyncSession, org_id: str, email: str, role: str) -> Invitation:
    exists = await session.scalar(
        select(Membership.id).join(User, User.id == Membership.user_id).where(Membership.org_id == org_id, User.email == email.lower())
    )
    if exists:
        raise Conflict("That user is already a member")
    inv = Invitation(org_id=org_id, email=email.lower(), role=role, token=secrets.token_urlsafe(24))
    session.add(inv)
    await session.flush()
    return inv


async def accept_invite(session: AsyncSession, token: str, user: User) -> Org:
    inv = await session.scalar(select(Invitation).where(Invitation.token == token))
    if not inv or inv.accepted:
        raise NotFound("Invitation is invalid or already used")
    if inv.email != user.email.lower():
        raise Forbidden("This invitation was issued to a different email address")
    if not await session.scalar(select(Membership.id).where(Membership.org_id == inv.org_id, Membership.user_id == user.id)):
        session.add(Membership(user_id=user.id, org_id=inv.org_id, role=inv.role))
    inv.accepted = True
    org = await session.get(Org, inv.org_id)
    assert org is not None
    return org

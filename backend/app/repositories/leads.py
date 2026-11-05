from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFound
from app.models import Lead


async def get(session: AsyncSession, org_id: str, lead_id: str) -> Lead:
    lead = await session.scalar(select(Lead).where(Lead.id == lead_id, Lead.org_id == org_id))
    if not lead:
        raise NotFound("Lead not found")
    return lead


async def by_email(session: AsyncSession, org_id: str, email: str) -> Lead | None:
    return await session.scalar(select(Lead).where(Lead.org_id == org_id, Lead.email == email.lower()))


async def search(session: AsyncSession, org_id: str, *, q: str | None, status: str | None,
                 min_score: int | None, limit: int, offset: int) -> tuple[list[Lead], int]:
    cond = [Lead.org_id == org_id]
    if status:
        cond.append(Lead.status == status)
    if min_score is not None:
        cond.append(Lead.icp_score >= min_score)
    if q:
        like = f"%{q.lower()}%"
        cond.append(or_(func.lower(Lead.email).like(like), func.lower(Lead.company).like(like),
                        func.lower(Lead.first_name).like(like), func.lower(Lead.last_name).like(like)))
    total = await session.scalar(select(func.count(Lead.id)).where(*cond)) or 0
    rows = await session.scalars(select(Lead).where(*cond).order_by(Lead.created_at.desc(), Lead.id).limit(limit).offset(offset))
    return list(rows.all()), int(total)

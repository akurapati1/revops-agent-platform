from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFound
from app.models import AgentRun, Lead


async def get(session: AsyncSession, org_id: str, run_id: str, with_steps: bool = False) -> AgentRun:
    q = select(AgentRun).where(AgentRun.id == run_id, AgentRun.org_id == org_id)
    if with_steps:
        q = q.options(selectinload(AgentRun.steps))
    run = await session.scalar(q)
    if not run:
        raise NotFound("Run not found")
    return run


async def list_runs(session: AsyncSession, org_id: str, *, status: str | None = None, lead_id: str | None = None,
                    limit: int = 50, offset: int = 0) -> list[tuple[AgentRun, Lead]]:
    q = select(AgentRun, Lead).join(Lead, Lead.id == AgentRun.lead_id).where(AgentRun.org_id == org_id)
    if status:
        q = q.where(AgentRun.status == status)
    if lead_id:
        q = q.where(AgentRun.lead_id == lead_id)
    q = q.order_by(AgentRun.created_at.desc()).limit(limit).offset(offset)
    return [(r, l) for r, l in (await session.execute(q)).all()]

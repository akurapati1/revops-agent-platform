from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict
from app.models import AgentRun, Lead, Org, Reply
from app.repositories import leads as lead_repo
from app.repositories import runs as run_repo
from app.services import approvals as approval_svc
from app.services import usage as usage_svc
from app.services.jobs import enqueue_run

ACTIVE = ("queued", "running")


async def start_outreach(session: AsyncSession, org: Org, user_id: str, lead_id: str, campaign: str) -> AgentRun:
    lead = await lead_repo.get(session, org.id, lead_id)
    if lead.status in ("unsubscribed", "bounced"):
        raise Conflict(f"Lead is {lead.status}; outreach is blocked")
    if await session.scalar(select(AgentRun.id).where(AgentRun.lead_id == lead.id, AgentRun.kind == "outreach",
                                                      AgentRun.status.in_(ACTIVE + ("awaiting_approval",)))):
        raise Conflict("This lead already has an active run (finish or cancel it first)")
    await usage_svc.assert_within_limit(session, org)
    run = AgentRun(org_id=org.id, lead_id=lead.id, created_by=user_id, kind="outreach", status="queued",
                   campaign=campaign, state={})
    session.add(run)
    await session.commit()
    await enqueue_run(run.id)
    return run


async def cancel(session: AsyncSession, org_id: str, run_id: str) -> AgentRun:
    run = await run_repo.get(session, org_id, run_id)
    if run.status not in ("awaiting_approval", "scheduled", "queued"):
        raise Conflict(f"A {run.status} run cannot be cancelled")
    await approval_svc.cancel_open_for_lead(session, org_id, run.lead_id, "Run cancelled")
    for a in await approval_svc.list_approvals(session, org_id, run_id=run.id):
        if a.status in ("pending", "approved"):
            a.status = "cancelled"
    run.status = "cancelled"
    return run


async def ingest_reply(session: AsyncSession, org: Org, lead: Lead, body: str, source: str, user_id: str | None) -> tuple[Reply, AgentRun]:
    await usage_svc.assert_within_limit(session, org)
    reply = Reply(org_id=org.id, lead_id=lead.id, source=source, body=body)
    session.add(reply)
    await session.flush()
    run = AgentRun(org_id=org.id, lead_id=lead.id, created_by=user_id, kind="triage", status="queued", campaign="reply triage",
                   state={"_extra": {"reply_id": reply.id, "reply_body": body}})
    session.add(run)
    await session.commit()
    await enqueue_run(run.id)
    return reply, run

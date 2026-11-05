"""Human approval gate + email dispatch."""
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import Conflict, NotFound
from app.core.logging import get_logger
from app.models import AgentRun, Approval, Lead
from app.services.email import OutboundEmail, get_email_provider

log = get_logger("approvals")
OPEN = ("pending", "approved")


async def list_approvals(session: AsyncSession, org_id: str, status: str | None = None,
                         lead_id: str | None = None, run_id: str | None = None, limit: int = 200) -> list[Approval]:
    q = select(Approval).where(Approval.org_id == org_id)
    if status:
        q = q.where(Approval.status == status)
    if lead_id:
        q = q.where(Approval.lead_id == lead_id)
    if run_id:
        q = q.where(Approval.run_id == run_id)
    q = q.order_by(Approval.created_at.desc(), Approval.step_number).limit(limit)
    return list((await session.scalars(q)).all())


async def get_approval(session: AsyncSession, org_id: str, approval_id: str) -> Approval:
    a = await session.scalar(select(Approval).where(Approval.id == approval_id, Approval.org_id == org_id))
    if not a:
        raise NotFound("Approval not found")
    return a


async def edit(session: AsyncSession, org_id: str, approval_id: str, subject: str | None, body: str | None) -> Approval:
    a = await get_approval(session, org_id, approval_id)
    if a.status != "pending":
        raise Conflict("Only pending drafts can be edited")
    if subject is not None:
        a.subject = subject
    if body is not None:
        a.body = body
    return a


async def approve(session: AsyncSession, org_id: str, user_id: str, approval_id: str) -> Approval:
    a = await get_approval(session, org_id, approval_id)
    if a.status != "pending":
        raise Conflict(f"Draft is already {a.status}")
    a.status = "approved"
    a.reviewed_by = user_id
    a.reviewed_at = datetime.now(UTC)
    await _send_if_due(session, a)
    await refresh_run(session, a.run_id)
    return a


async def reject(session: AsyncSession, org_id: str, user_id: str, approval_id: str) -> Approval:
    a = await get_approval(session, org_id, approval_id)
    if a.status != "pending":
        raise Conflict(f"Draft is already {a.status}")
    a.status = "rejected"
    a.reviewed_by = user_id
    a.reviewed_at = datetime.now(UTC)
    await refresh_run(session, a.run_id)
    return a


async def _send_if_due(session: AsyncSession, a: Approval) -> bool:
    if a.status != "approved" or a.scheduled_at > datetime.now(UTC):
        return False
    lead = await session.get(Lead, a.lead_id)
    if lead is None or lead.org_id != a.org_id or lead.status in ("unsubscribed", "bounced"):
        a.status = "cancelled"
        a.error = "Lead is unsubscribed or missing"
        return False
    s = get_settings()
    try:
        res = await get_email_provider().send(OutboundEmail(to=a.to_email, subject=a.subject, body=a.body, from_addr=s.email_from))
    except Exception as exc:
        log.exception("email.send_failed", extra={"approval_id": a.id})
        a.status = "failed"
        a.error = str(exc)[:500]
        return False
    a.status = "sent"
    a.sent_at = datetime.now(UTC)
    a.provider_message_id = res.message_id
    a.error = None
    if lead.status in ("new", "researched", "awaiting_approval"):
        lead.status = "contacted"
    return True


async def dispatch_due(session: AsyncSession) -> int:
    """Send approved emails whose scheduled time has passed (all orgs; called by the scheduler)."""
    rows = (await session.scalars(
        select(Approval).where(Approval.status == "approved", Approval.scheduled_at <= datetime.now(UTC)).limit(200)
    )).all()
    n = 0
    runs: set[str] = set()
    for a in rows:
        if await _send_if_due(session, a):
            n += 1
        runs.add(a.run_id)
    for rid in runs:
        await refresh_run(session, rid)
    return n


async def refresh_run(session: AsyncSession, run_id: str) -> None:
    """Move a run out of `awaiting_approval` once all drafts are resolved."""
    run = await session.get(AgentRun, run_id)
    if run is None or run.status not in ("awaiting_approval", "scheduled"):
        return
    await session.flush()
    items = (await session.scalars(select(Approval).where(Approval.run_id == run_id))).all()
    statuses = {i.status for i in items}
    if "pending" in statuses:
        run.status = "awaiting_approval"
    elif "approved" in statuses:
        run.status = "scheduled"
    else:
        run.status = "completed" if "sent" in statuses else "rejected"
        run.finished_at = datetime.now(UTC)


async def cancel_open_for_lead(session: AsyncSession, org_id: str, lead_id: str, reason: str) -> int:
    rows = (await session.scalars(
        select(Approval).where(Approval.org_id == org_id, Approval.lead_id == lead_id,
                               Approval.status.in_(OPEN), Approval.kind == "sequence")
    )).all()
    runs = set()
    for a in rows:
        a.status = "cancelled"
        a.error = reason
        runs.add(a.run_id)
    for rid in runs:
        await refresh_run(session, rid)
    return len(rows)

from datetime import UTC, datetime, timedelta

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRun, Approval, Lead, Reply
from app.services import usage as usage_svc


async def stats(session: AsyncSession, org_id: str, org_limit: int) -> dict:
    async def count(q):
        return int(await session.scalar(q) or 0)

    total_leads = await count(select(func.count(Lead.id)).where(Lead.org_id == org_id))
    researched = await count(select(func.count(Lead.id)).where(Lead.org_id == org_id, Lead.brief.is_not(None)))
    qualified = await count(select(func.count(Lead.id)).where(Lead.org_id == org_id, Lead.icp_score >= 50))
    drafted = await count(select(func.count(distinct(Approval.lead_id))).where(Approval.org_id == org_id, Approval.kind == "sequence"))
    sent_leads = await count(select(func.count(distinct(Approval.lead_id))).where(
        Approval.org_id == org_id, Approval.kind == "sequence", Approval.status == "sent"))
    replied = await count(select(func.count(distinct(Reply.lead_id))).where(Reply.org_id == org_id))
    interested = await count(select(func.count(Lead.id)).where(Lead.org_id == org_id, Lead.status == "interested"))
    pending = await count(select(func.count(Approval.id)).where(Approval.org_id == org_id, Approval.status == "pending"))
    emails_sent = await count(select(func.count(Approval.id)).where(Approval.org_id == org_id, Approval.status == "sent"))
    total_runs = await count(select(func.count(AgentRun.id)).where(AgentRun.org_id == org_id))
    active_runs = await count(select(func.count(AgentRun.id)).where(AgentRun.org_id == org_id, AgentRun.status.in_(("queued", "running"))))

    since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=13)
    rows = (await session.execute(select(AgentRun.created_at, AgentRun.kind).where(AgentRun.org_id == org_id, AgentRun.created_at >= since))).all()
    per_day = {(since + timedelta(days=i)).date().isoformat(): 0 for i in range(14)}
    for ts, kind in rows:
        if kind == "outreach" and ts.date().isoformat() in per_day:
            per_day[ts.date().isoformat()] += 1

    avg = await session.scalar(select(func.avg(Lead.icp_score)).where(Lead.org_id == org_id, Lead.icp_score.is_not(None)))
    usage = await usage_svc.month_totals(session, org_id)
    return {
        "kpis": {
            "total_leads": total_leads, "pending_approvals": pending, "emails_sent": emails_sent,
            "reply_rate": round(replied / sent_leads, 3) if sent_leads else 0.0,
            "total_runs": total_runs, "active_runs": active_runs, "avg_icp_score": round(float(avg), 1) if avg is not None else None,
        },
        "funnel": [
            {"stage": "Leads", "count": total_leads}, {"stage": "Researched", "count": researched},
            {"stage": "ICP fit (50+)", "count": qualified}, {"stage": "Drafted", "count": drafted},
            {"stage": "Contacted", "count": sent_leads}, {"stage": "Replied", "count": replied},
            {"stage": "Interested", "count": interested},
        ],
        "runs_per_day": [{"date": d, "runs": n} for d, n in per_day.items()],
        "usage": {**usage, "limit": org_limit},
    }

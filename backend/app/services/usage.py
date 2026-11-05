from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import UsageLimitExceeded
from app.models import Org, UsageRecord


def month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def month_totals(session: AsyncSession, org_id: str) -> dict:
    q = select(
        func.coalesce(func.sum(UsageRecord.tokens_in), 0),
        func.coalesce(func.sum(UsageRecord.tokens_out), 0),
        func.coalesce(func.sum(UsageRecord.cost_usd), 0.0),
        func.count(UsageRecord.id),
    ).where(UsageRecord.org_id == org_id, UsageRecord.created_at >= month_start())
    tin, tout, cost, calls = (await session.execute(q)).one()
    return {"tokens_in": int(tin), "tokens_out": int(tout), "tokens": int(tin) + int(tout),
            "cost_usd": round(float(cost), 6), "calls": int(calls)}


async def assert_within_limit(session: AsyncSession, org: Org) -> None:
    used = (await month_totals(session, org.id))["tokens"]
    if used >= org.monthly_token_limit:
        raise UsageLimitExceeded(
            f"Monthly token limit reached ({used:,}/{org.monthly_token_limit:,}). Raise the limit in Settings > API usage."
        )


async def record(session: AsyncSession, *, org_id: str, run_id: str | None, agent: str, model: str,
                 tokens_in: int, tokens_out: int, cost_usd: float) -> None:
    session.add(UsageRecord(org_id=org_id, run_id=run_id, agent=agent, model=model,
                            tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd))


async def breakdown(session: AsyncSession, org_id: str) -> dict:
    since = month_start()
    by_agent = (await session.execute(
        select(UsageRecord.agent, func.sum(UsageRecord.tokens_in + UsageRecord.tokens_out), func.sum(UsageRecord.cost_usd),
               func.count(UsageRecord.id))
        .where(UsageRecord.org_id == org_id, UsageRecord.created_at >= since).group_by(UsageRecord.agent)
    )).all()
    rows = (await session.execute(
        select(UsageRecord.created_at, UsageRecord.tokens_in + UsageRecord.tokens_out, UsageRecord.cost_usd)
        .where(UsageRecord.org_id == org_id, UsageRecord.created_at >= since)
    )).all()
    daily: dict[str, dict] = {}
    for ts, tok, cost in rows:
        d = daily.setdefault(ts.date().isoformat(), {"date": ts.date().isoformat(), "tokens": 0, "cost_usd": 0.0})
        d["tokens"] += int(tok)
        d["cost_usd"] = round(d["cost_usd"] + float(cost), 6)
    return {
        "by_agent": [{"agent": a, "tokens": int(t or 0), "cost_usd": round(float(c or 0), 6), "calls": int(n)}
                     for a, t, c, n in by_agent],
        "daily": sorted(daily.values(), key=lambda x: x["date"]),
    }

"""DAG orchestrator: runs agents in dependency order, persists a trace per step, pauses at the approval gate."""
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import RunContext
from app.agents.registry import DAGS, get_agent, topo_order
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.llm.factory import get_llm
from app.models import AgentRun, Approval, Lead, Org, Reply, RunStep
from app.services import approvals as approval_svc
from app.services import usage as usage_svc

log = get_logger("orchestrator")


def _json_safe(v: Any) -> Any:
    return json.loads(json.dumps(v, default=str))


def lead_snapshot(lead: Lead) -> dict[str, Any]:
    return {"id": lead.id, "email": lead.email, "first_name": lead.first_name, "last_name": lead.last_name,
            "company": lead.company, "title": lead.title, "website": lead.website,
            "linkedin_url": lead.linkedin_url, "notes": lead.notes}


def org_snapshot(org: Org) -> dict[str, Any]:
    st = org.settings or {}
    return {"id": org.id, "name": org.name, "icp": st.get("icp", {}), "sender_name": st.get("sender_name", ""),
            "product_pitch": st.get("product_pitch", "")}


async def _fail(session: AsyncSession, run: AgentRun, lead: Lead | None, message: str) -> None:
    run.status = "failed"
    run.error = message[:1000]
    run.finished_at = datetime.now(UTC)
    await session.commit()


async def execute_run(run_id: str) -> None:
    async with SessionLocal() as session:
        try:
            await _execute(session, run_id)
        except Exception as exc:  # last-resort guard so a run never stays 'running'
            log.exception("run.crashed", extra={"run_id": run_id})
            await session.rollback()
            run = await session.get(AgentRun, run_id)
            if run and run.status in ("queued", "running"):
                await _fail(session, run, None, f"Internal error: {exc}")


async def _execute(session: AsyncSession, run_id: str) -> None:
    run = await session.get(AgentRun, run_id)
    if run is None or run.status != "queued":
        return
    org = await session.get(Org, run.org_id)
    lead = await session.get(Lead, run.lead_id)
    if org is None or lead is None:
        await _fail(session, run, lead, "Org or lead no longer exists")
        return

    settings = get_settings()
    extra = dict(run.state.get("_extra", {})) if run.state else {}
    ctx = RunContext(run_id=run.id, org=org_snapshot(org), lead=lead_snapshot(lead), settings=settings,
                     llm=get_llm(), state={}, extra=extra)
    run.status = "running"

    order = [n for layer in topo_order(DAGS[run.kind]) for n in layer]
    steps: list[RunStep] = []
    for i, name in enumerate(order):
        st = RunStep(run_id=run.id, org_id=run.org_id, seq=i, agent=name, status="pending")
        session.add(st)
        steps.append(st)
    await session.commit()

    for step in steps:
        agent = get_agent(step.agent)
        inp = _json_safe(agent.build_input(ctx))
        step.input = inp
        step.status = "running"
        step.started_at = datetime.now(UTC)
        await session.commit()
        try:
            if agent.uses_llm:
                await usage_svc.assert_within_limit(session, org)
            result = await agent.run(ctx, inp)
        except Exception as exc:
            log.warning("step.failed", extra={"run_id": run.id, "agent": step.agent, "error": str(exc)})
            step.status = "failed"
            step.error = getattr(exc, "message", str(exc))[:1000]
            step.finished_at = datetime.now(UTC)
            await _fail(session, run, lead, f"{step.agent} failed: {step.error}")
            return

        step.status = "succeeded"
        step.output = _json_safe(result.output)
        step.tool_calls = _json_safe(result.tool_calls)
        step.model = result.model
        step.finished_at = datetime.now(UTC)
        if result.usage:
            u = result.usage
            step.tokens_in, step.tokens_out, step.cost_usd = u.tokens_in, u.tokens_out, u.cost_usd
            step.latency_ms, step.attempts = u.latency_ms, u.attempts
            run.total_tokens += u.total_tokens
            run.total_cost_usd = round(run.total_cost_usd + u.cost_usd, 6)
            await usage_svc.record(session, org_id=org.id, run_id=run.id, agent=step.agent, model=u.model,
                                   tokens_in=u.tokens_in, tokens_out=u.tokens_out, cost_usd=u.cost_usd)
        else:
            step.latency_ms = int((step.finished_at - step.started_at).total_seconds() * 1000)
        ctx.state[agent.name] = result.output
        run.state = {**(run.state or {}), agent.name: result.output}
        await _after_step(session, run, org, lead, step.agent, result.output)
        await session.commit()

    run.finished_at = datetime.now(UTC) if run.status == "completed" else None
    await session.commit()


async def _after_step(session: AsyncSession, run: AgentRun, org: Org, lead: Lead, agent: str, out: dict[str, Any]) -> None:
    if agent == "researcher":
        lead.brief = out
        if lead.status == "new":
            lead.status = "researched"
    elif agent == "enricher":
        lead.firmographics = out
        lead.icp_score = out["icp_score"]
    elif agent == "sequencer":
        for s in out["steps"]:
            session.add(Approval(org_id=org.id, run_id=run.id, lead_id=lead.id, kind="sequence",
                                 step_number=s["step_number"], to_email=lead.email, subject=s["subject"],
                                 body=s["body"], scheduled_at=datetime.fromisoformat(s["scheduled_at"])))
        if lead.status in ("new", "researched"):
            lead.status = "awaiting_approval"
        run.status = "awaiting_approval"  # HUMAN GATE: nothing is sent until approved
    elif agent == "triage":
        await _apply_triage(session, run, org, lead, out)


async def _apply_triage(session: AsyncSession, run: AgentRun, org: Org, lead: Lead, out: dict[str, Any]) -> None:
    cls = out["classification"]
    reply = await session.get(Reply, run.state["_extra"]["reply_id"])
    if reply:
        reply.classification, reply.confidence, reply.summary, reply.run_id = cls, out["confidence"], out["summary"], run.id
    if cls == "unsubscribe":
        lead.status = "unsubscribed"
        await approval_svc.cancel_open_for_lead(session, org.id, lead.id, "Lead unsubscribed")
    elif cls == "interested":
        lead.status = "interested"
    elif cls in ("objection", "out_of_office", "other") and lead.status not in ("unsubscribed",):
        lead.status = "replied"
    if cls in ("interested", "objection") and out.get("draft_reply"):
        session.add(Approval(org_id=org.id, run_id=run.id, lead_id=lead.id, kind="reply", step_number=1,
                             to_email=lead.email, subject="Re: your reply", body=out["draft_reply"]))
        run.status = "awaiting_approval"
    else:
        run.status = "completed"
        run.finished_at = datetime.now(UTC)

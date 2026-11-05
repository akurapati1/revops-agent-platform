import asyncio

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import DAGS, list_agents
from app.db import SessionLocal, get_session
from app.deps import Ctx, get_ctx, get_ctx_query_token
from app.repositories import leads as lead_repo
from app.repositories import runs as repo
from app.schemas.api import ApprovalOut, BulkRunCreate, RunCreate, RunDetail, RunOut, StepOut
from app.services import approvals as approval_svc
from app.services import runs as svc

router = APIRouter(tags=["runs"])
TERMINAL = ("completed", "failed", "rejected", "cancelled", "awaiting_approval", "scheduled")


def _run_out(run, lead) -> RunOut:
    return RunOut(**{**RunOut.model_validate(run).model_dump(), "lead_email": lead.email, "lead_company": lead.company})


@router.get("/agents")
async def agents(_: Ctx = Depends(get_ctx)):
    return {
        "agents": [{"name": a.name, "description": a.description, "depends_on": list(a.depends_on), "uses_llm": a.uses_llm,
                    "tools": [{"name": t.name, "description": t.description} for t in a.tools]} for a in list_agents()],
        "dags": {k: list(v) for k, v in DAGS.items()},
    }


@router.post("/leads/{lead_id}/runs", response_model=RunOut, status_code=202)
async def start_run(lead_id: str, data: RunCreate, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    run = await svc.start_outreach(session, ctx.org, ctx.user.id, lead_id, data.campaign)
    lead = await lead_repo.get(session, ctx.org.id, lead_id)
    return _run_out(run, lead)


@router.post("/runs/bulk", response_model=list[RunOut], status_code=202)
async def start_bulk(data: BulkRunCreate, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    out = []
    for lid in dict.fromkeys(data.lead_ids):
        run = await svc.start_outreach(session, ctx.org, ctx.user.id, lid, data.campaign)
        out.append(_run_out(run, await lead_repo.get(session, ctx.org.id, lid)))
    return out


@router.get("/runs", response_model=list[RunOut])
async def list_runs(status: str | None = None, lead_id: str | None = None, limit: int = Query(default=50, ge=1, le=200),
                    offset: int = Query(default=0, ge=0), ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return [_run_out(r, l) for r, l in await repo.list_runs(session, ctx.org.id, status=status, lead_id=lead_id, limit=limit, offset=offset)]


async def _detail(session: AsyncSession, org_id: str, run_id: str) -> RunDetail:
    run = await repo.get(session, org_id, run_id, with_steps=True)
    lead = await lead_repo.get(session, org_id, run.lead_id)
    approvals = await approval_svc.list_approvals(session, org_id, run_id=run_id)
    base = _run_out(run, lead).model_dump()
    return RunDetail(**base, steps=[StepOut.model_validate(s) for s in run.steps],
                     approvals=[ApprovalOut.model_validate(a) for a in sorted(approvals, key=lambda a: a.step_number)])


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return await _detail(session, ctx.org.id, run_id)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(run_id: str, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    run = await svc.cancel(session, ctx.org.id, run_id)
    return _run_out(run, await lead_repo.get(session, ctx.org.id, run.lead_id))


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, ctx: Ctx = Depends(get_ctx_query_token)):
    """Server-sent events: emits the full run detail whenever it changes, until the run settles."""
    org_id = ctx.org.id

    async def gen():
        last = ""
        for _ in range(600):
            async with SessionLocal() as s:
                detail = await _detail(s, org_id, run_id)
            payload = detail.model_dump_json()
            if payload != last:
                last = payload
                yield f"event: run\ndata: {payload}\n\n"
            if detail.status in TERMINAL:
                yield "event: done\ndata: {}\n\n"
                return
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})



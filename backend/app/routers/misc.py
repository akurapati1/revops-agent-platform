from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import NotFound
from app.db import get_session
from app.deps import Ctx, get_ctx, require_role
from app.models import Lead, Org
from app.repositories import leads as lead_repo
from app.schemas.api import ApprovalEdit, ApprovalOut, RunOut, WebhookReplyIn
from app.services import approvals as svc
from app.services import dashboard, usage
from app.services import runs as run_svc

router = APIRouter()


@router.get("/health", tags=["ops"])
async def health():
    return {"status": "ok"}


@router.get("/ready", tags=["ops"])
async def ready(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "llm_provider": get_settings().llm_provider, "email_provider": get_settings().email_provider}


# ---- approvals ----
async def _decorate(session: AsyncSession, org_id: str, items) -> list[ApprovalOut]:
    leads = {l.id: l for l in (await session.scalars(select(Lead).where(Lead.org_id == org_id, Lead.id.in_({a.lead_id for a in items})))).all()} if items else {}
    out = []
    for a in items:
        o = ApprovalOut.model_validate(a)
        l = leads.get(a.lead_id)
        if l:
            o.lead_name = f"{l.first_name} {l.last_name}".strip() or l.email
            o.lead_company = l.company
        out.append(o)
    return out


@router.get("/approvals", response_model=list[ApprovalOut], tags=["approvals"])
async def list_approvals(status: str | None = None, limit: int = Query(default=100, ge=1, le=300),
                         ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return await _decorate(session, ctx.org.id, await svc.list_approvals(session, ctx.org.id, status=status, limit=limit))


@router.patch("/approvals/{approval_id}", response_model=ApprovalOut, tags=["approvals"])
async def edit_approval(approval_id: str, data: ApprovalEdit, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    a = await svc.edit(session, ctx.org.id, approval_id, data.subject, data.body)
    return (await _decorate(session, ctx.org.id, [a]))[0]


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalOut, tags=["approvals"])
async def approve(approval_id: str, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    a = await svc.approve(session, ctx.org.id, ctx.user.id, approval_id)
    return (await _decorate(session, ctx.org.id, [a]))[0]


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalOut, tags=["approvals"])
async def reject(approval_id: str, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    a = await svc.reject(session, ctx.org.id, ctx.user.id, approval_id)
    return (await _decorate(session, ctx.org.id, [a]))[0]


@router.post("/approvals/dispatch-due", tags=["approvals"])
async def dispatch_due(ctx: Ctx = Depends(require_role("admin")), session: AsyncSession = Depends(get_session)):
    return {"sent": await svc.dispatch_due(session)}


# ---- dashboard / usage / integrations ----
@router.get("/dashboard/stats", tags=["dashboard"])
async def stats(ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return await dashboard.stats(session, ctx.org.id, ctx.org.monthly_token_limit)


@router.get("/usage", tags=["usage"])
async def get_usage(ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    totals = await usage.month_totals(session, ctx.org.id)
    return {**totals, "limit": ctx.org.monthly_token_limit, "period_start": usage.month_start().isoformat(),
            **(await usage.breakdown(session, ctx.org.id))}


@router.get("/integrations", tags=["integrations"])
async def integrations(ctx: Ctx = Depends(get_ctx)):
    s = get_settings()
    agents = ("researcher", "enricher", "personalizer", "triage")
    return {
        "llm": {"provider": s.llm_provider, "configured": s.llm_provider == "mock" or bool(s.openrouter_api_key),
                "models": {a: s.model_for(a) for a in agents}},
        "email": {"provider": s.email_provider, "from": s.email_from,
                  "configured": s.email_provider == "console" or bool(s.smtp_host)},
        "oauth": {p: s.oauth_configured(p) for p in ("google", "github")},
        "queue": {"backend": "redis" if s.redis_url else "in-process"},
        "web_tools": s.enable_web_tools,
    }


# ---- inbound reply webhook (token-authenticated, no user session) ----
@router.post("/webhooks/replies/{token}", response_model=RunOut, status_code=202, tags=["webhooks"])
async def reply_webhook(token: str, data: WebhookReplyIn, session: AsyncSession = Depends(get_session)):
    org = await session.scalar(select(Org).where(Org.webhook_token == token))
    if not org:
        raise NotFound("Unknown webhook")
    lead = await lead_repo.by_email(session, org.id, data.from_email)
    if not lead:
        raise NotFound("No lead with that email in this organization")
    _, run = await run_svc.ingest_reply(session, org, lead, data.body, "webhook", None)
    return RunOut(**{**RunOut.model_validate(run).model_dump(), "lead_email": lead.email, "lead_company": lead.company})



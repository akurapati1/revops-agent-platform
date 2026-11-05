from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import Ctx, get_ctx
from app.models import Reply
from app.repositories import leads as repo
from app.schemas.api import (
    ApprovalOut,
    ImportResult,
    LeadDetail,
    LeadIn,
    LeadOut,
    LeadPage,
    LeadUpdate,
    ReplyIn,
    ReplyOut,
    RunOut,
)
from app.services import approvals as approval_svc
from app.services import leads as svc
from app.services import runs as run_svc

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=LeadPage)
async def list_leads(q: str | None = None, status: str | None = None, min_score: int | None = Query(default=None, ge=0, le=100),
                     limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
                     ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    items, total = await repo.search(session, ctx.org.id, q=q, status=status, min_score=min_score, limit=limit, offset=offset)
    return LeadPage(items=[LeadOut.model_validate(i) for i in items], total=total, limit=limit, offset=offset)


@router.post("", response_model=LeadOut, status_code=201)
async def create_lead(data: LeadIn, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return await svc.create(session, ctx.org.id, data)


@router.post("/import", response_model=ImportResult)
async def import_leads(file: UploadFile = File(...), ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return await svc.import_csv(session, ctx.org.id, await file.read())


@router.get("/{lead_id}", response_model=LeadDetail)
async def get_lead(lead_id: str, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return await repo.get(session, ctx.org.id, lead_id)


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(lead_id: str, data: LeadUpdate, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    return await svc.update(session, ctx.org.id, lead_id, data)


@router.delete("/{lead_id}", status_code=204)
async def delete_lead(lead_id: str, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    await svc.delete(session, ctx.org.id, lead_id)
    return Response(status_code=204)


@router.get("/{lead_id}/approvals", response_model=list[ApprovalOut])
async def lead_approvals(lead_id: str, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    await repo.get(session, ctx.org.id, lead_id)
    return await approval_svc.list_approvals(session, ctx.org.id, lead_id=lead_id)


@router.get("/{lead_id}/replies", response_model=list[ReplyOut])
async def lead_replies(lead_id: str, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    await repo.get(session, ctx.org.id, lead_id)
    rows = await session.scalars(select(Reply).where(Reply.org_id == ctx.org.id, Reply.lead_id == lead_id).order_by(Reply.created_at.desc()))
    return list(rows.all())


@router.post("/{lead_id}/replies", response_model=RunOut, status_code=202)
async def submit_reply(lead_id: str, data: ReplyIn, ctx: Ctx = Depends(get_ctx), session: AsyncSession = Depends(get_session)):
    lead = await repo.get(session, ctx.org.id, lead_id)
    _, run = await run_svc.ingest_reply(session, ctx.org, lead, data.body, "manual", ctx.user.id)
    return RunOut(**{**RunOut.model_validate(run).model_dump(), "lead_email": lead.email, "lead_company": lead.company})

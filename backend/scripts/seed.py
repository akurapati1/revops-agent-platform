"""Seed demo data: a demo org, user, leads, and a few completed pipeline runs (works offline with the mock LLM).

Usage:  python -m scripts.seed            (from backend/)
Login:  demo@revops.dev / demo-password-123
"""
import asyncio

from sqlalchemy import select

from app.agents.orchestrator import execute_run
from app.core.security import hash_password
from app.db import SessionLocal, create_all
from app.models import AgentRun, Approval, Lead, Org, User
from app.schemas.api import LeadIn
from app.services import approvals as approval_svc
from app.services import leads as lead_svc
from app.services import orgs as org_svc

EMAIL, PASSWORD = "demo@revops.dev", "demo-password-123"

LEADS = [
    ("maya.chen@brightpath.io", "Maya", "Chen", "BrightPath", "VP of Sales", "brightpath.io"),
    ("liam.ortiz@fluxpay.com", "Liam", "Ortiz", "FluxPay", "Head of Revenue Operations", "fluxpay.com"),
    ("noor.haddad@cedarhealth.org", "Noor", "Haddad", "Cedar Health", "Director of Growth", "cedarhealth.org"),
    ("jon.park@stackforge.dev", "Jon", "Park", "StackForge", "CTO", "stackforge.dev"),
    ("sara.lindqvist@nordlogix.se", "Sara", "Lindqvist", "NordLogix", "Sales Manager", "nordlogix.se"),
    ("tom.becker@ironclad-mfg.com", "Tom", "Becker", "Ironclad Manufacturing", "Procurement Lead", "ironclad-mfg.com"),
    ("priya.nair@learnloop.co", "Priya", "Nair", "LearnLoop", "Founder & CEO", "learnloop.co"),
    ("alex.rivera@securenest.io", "Alex", "Rivera", "SecureNest", "Chief Revenue Officer", "securenest.io"),
]


async def main() -> None:
    await create_all()
    async with SessionLocal() as s:
        user = await s.scalar(select(User).where(User.email == EMAIL))
        if user:
            print("Demo data already present; nothing to do.")
            return
        user = User(email=EMAIL, name="Demo User", password_hash=hash_password(PASSWORD))
        s.add(user)
        await s.flush()
        org = await org_svc.create_org(s, "Demo Org", user)
        org.settings = {**org.settings, "sender_name": "Demo User", "product_pitch": "an AI sales-ops platform that researches leads and drafts human-approved outreach"}
        lead_ids = []
        for email, first, last, company, title, site in LEADS:
            lead = await lead_svc.create(s, org.id, LeadIn(email=email, first_name=first, last_name=last, company=company, title=title, website=site))
            lead_ids.append(lead.id)
        runs = []
        for lid in lead_ids[:6]:
            run = AgentRun(org_id=org.id, lead_id=lid, created_by=user.id, kind="outreach", status="queued", campaign="Demo Q4 outbound", state={})
            s.add(run)
            runs.append(run)
        await s.commit()
        run_ids = [r.id for r in runs]
    for rid in run_ids:
        await execute_run(rid)
    async with SessionLocal() as s:
        org = await s.scalar(select(Org).where(Org.slug == "demo-org"))
        # approve & send the first step for the first three leads so the funnel has some depth
        pend = (await s.scalars(select(Approval).where(Approval.org_id == org.id, Approval.step_number == 1).limit(3))).all()
        user = await s.scalar(select(User).where(User.email == EMAIL))
        for a in pend:
            await approval_svc.approve(s, org.id, user.id, a.id)
        await s.commit()
        first_lead = await s.scalar(select(Lead).where(Lead.org_id == org.id, Lead.email == LEADS[0][0]))
        from app.services import runs as run_svc

        await run_svc.ingest_reply(s, org, first_lead, "This looks interesting - can we book a demo next week?", "manual", user.id)
    from app.services import jobs

    await jobs.drain()
    print(f"Seeded. Sign in with {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())

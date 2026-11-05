import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.agents.registry import OUTREACH_DAG, topo_order
from app.db import SessionLocal
from app.llm.base import RawCompletion
from app.llm.factory import set_llm
from app.llm.mock import MockProvider
from app.models import Approval
from app.services import jobs
from tests.conftest import make_lead, run_to_gate


async def test_dag_order():
    assert topo_order(OUTREACH_DAG) == [["researcher"], ["enricher"], ["personalizer"], ["sequencer"]]


async def test_end_to_end_run_pauses_at_approval_gate(client, acct, mail):
    lead = await make_lead(client, acct)
    run = await run_to_gate(client, acct, lead["id"])

    assert run["status"] == "awaiting_approval"
    assert [s["agent"] for s in run["steps"]] == ["researcher", "enricher", "personalizer", "sequencer"]
    assert all(s["status"] == "succeeded" for s in run["steps"])
    llm_steps = [s for s in run["steps"] if s["agent"] != "sequencer"]
    assert all(s["tokens_in"] > 0 and s["tokens_out"] > 0 and s["cost_usd"] > 0 and s["model"] for s in llm_steps)
    assert run["steps"][0]["input"]["lead"]["company"] == "Northwind Labs"
    assert run["steps"][0]["tool_calls"][0]["tool"] == "domain_info"
    assert run["total_tokens"] == sum(s["tokens_in"] + s["tokens_out"] for s in run["steps"]) > 0

    # THE GATE: drafts exist, nothing has been sent
    assert mail.sent == []
    assert [a["status"] for a in run["approvals"]] == ["pending"] * 3
    assert [a["step_number"] for a in run["approvals"]] == [1, 2, 3]

    detail = (await client.get(f"/leads/{lead['id']}", headers=acct.headers)).json()
    assert detail["status"] == "awaiting_approval" and 0 <= detail["icp_score"] <= 100
    assert detail["brief"]["company_summary"] and detail["firmographics"]["fit_tier"] in "ABC"

    queue = (await client.get("/approvals?status=pending", headers=acct.headers)).json()
    assert len(queue) == 3 and queue[0]["lead_company"] == "Northwind Labs"

    # edit then approve step 1 -> sent immediately; later steps are scheduled
    a1 = run["approvals"][0]["id"]
    ed = await client.patch(f"/approvals/{a1}", json={"subject": "Edited subject"}, headers=acct.headers)
    assert ed.json()["subject"] == "Edited subject"
    ok = await client.post(f"/approvals/{a1}/approve", headers=acct.headers)
    assert ok.status_code == 200 and ok.json()["status"] == "sent"
    assert len(mail.sent) == 1 and mail.sent[0].subject == "Edited subject" and mail.sent[0].to == lead["email"]
    assert (await client.post(f"/approvals/{a1}/approve", headers=acct.headers)).status_code == 409
    assert (await client.patch(f"/approvals/{a1}", json={"body": "late"}, headers=acct.headers)).status_code == 409

    a2, a3 = run["approvals"][1]["id"], run["approvals"][2]["id"]
    assert (await client.post(f"/approvals/{a2}/approve", headers=acct.headers)).json()["status"] == "approved"  # future-dated
    assert (await client.post(f"/approvals/{a3}/reject", headers=acct.headers)).json()["status"] == "rejected"
    assert (await client.get(f"/runs/{run['id']}", headers=acct.headers)).json()["status"] == "scheduled"
    assert len(mail.sent) == 1

    # scheduler tick once the time has come
    async with SessionLocal() as s:
        await s.execute(update(Approval).where(Approval.id == a2).values(scheduled_at=datetime.now(UTC) - timedelta(minutes=1)))
        await s.commit()
    assert (await client.post("/approvals/dispatch-due", headers=acct.headers)).json()["sent"] == 1
    assert len(mail.sent) == 2
    final = (await client.get(f"/runs/{run['id']}", headers=acct.headers)).json()
    assert final["status"] == "completed"
    assert (await client.get(f"/leads/{lead['id']}", headers=acct.headers)).json()["status"] == "contacted"


async def test_reject_all_and_cancel(client, acct, mail):
    lead = await make_lead(client, acct)
    run = await run_to_gate(client, acct, lead["id"])
    for a in run["approvals"]:
        await client.post(f"/approvals/{a['id']}/reject", headers=acct.headers)
    assert (await client.get(f"/runs/{run['id']}", headers=acct.headers)).json()["status"] == "rejected"
    assert mail.sent == []

    run2 = await run_to_gate(client, acct, lead["id"])
    c = await client.post(f"/runs/{run2['id']}/cancel", headers=acct.headers)
    assert c.json()["status"] == "cancelled"
    pend = (await client.get("/approvals?status=pending", headers=acct.headers)).json()
    assert pend == []


async def test_one_active_run_per_lead(client, acct):
    lead = await make_lead(client, acct)
    await run_to_gate(client, acct, lead["id"])
    again = await client.post(f"/leads/{lead['id']}/runs", json={}, headers=acct.headers)
    assert again.status_code == 409


async def test_bulk_runs_and_dashboard(client, acct):
    ids = [(await make_lead(client, acct))["id"] for _ in range(3)]
    r = await client.post("/runs/bulk", json={"lead_ids": ids, "campaign": "bulk"}, headers=acct.headers)
    assert r.status_code == 202 and len(r.json()) == 3
    await jobs.drain()
    runs = (await client.get("/runs", headers=acct.headers)).json()
    assert len(runs) == 3 and {x["status"] for x in runs} == {"awaiting_approval"}
    st = (await client.get("/dashboard/stats", headers=acct.headers)).json()
    assert st["kpis"]["total_leads"] == 3 and st["kpis"]["pending_approvals"] == 9
    assert st["funnel"][0] == {"stage": "Leads", "count": 3} and st["funnel"][3]["count"] == 3
    assert len(st["runs_per_day"]) == 14 and st["usage"]["tokens"] > 0


async def test_sse_stream_for_settled_run(client, acct):
    lead = await make_lead(client, acct)
    run = await run_to_gate(client, acct, lead["id"])
    token = acct.tokens["access_token"]
    r = await client.get(f"/runs/{run['id']}/events?token={token}")
    assert r.status_code == 200 and "event: run" in r.text and "event: done" in r.text
    assert (await client.get(f"/runs/{run['id']}/events?token=bad")).status_code == 401


class FlakyProvider(MockProvider):
    """Returns invalid JSON on the first call for each agent, then valid output."""

    def __init__(self):
        self.calls = {}

    async def complete(self, *, agent, **kw):
        self.calls[agent] = self.calls.get(agent, 0) + 1
        if self.calls[agent] == 1:
            return RawCompletion(content="Sure! here you go: not json", tokens_in=10, tokens_out=5)
        return await super().complete(agent=agent, **kw)


async def test_structured_output_retry_is_traced(client, acct):
    set_llm(FlakyProvider())
    lead = await make_lead(client, acct)
    run = await run_to_gate(client, acct, lead["id"])
    assert run["status"] == "awaiting_approval"
    researcher = run["steps"][0]
    assert researcher["attempts"] == 2 and researcher["tokens_in"] > 10


class WrongSchemaProvider(MockProvider):
    async def complete(self, *, agent, **kw):
        return RawCompletion(content=json.dumps({"unexpected": True}), tokens_in=3, tokens_out=3)


async def test_failed_validation_fails_run_with_trace(client, acct):
    set_llm(WrongSchemaProvider())
    lead = await make_lead(client, acct)
    run = await run_to_gate(client, acct, lead["id"])
    assert run["status"] == "failed" and "researcher" in run["error"]
    assert run["steps"][0]["status"] == "failed" and run["steps"][0]["error"]
    assert [s["status"] for s in run["steps"][1:]] == ["pending"] * 3

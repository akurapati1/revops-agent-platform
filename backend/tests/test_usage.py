from app.services import jobs
from tests.conftest import make_lead, run_to_gate


async def test_usage_accounting(client, acct):
    lead = await make_lead(client, acct)
    run = await run_to_gate(client, acct, lead["id"])
    u = (await client.get("/usage", headers=acct.headers)).json()
    assert u["tokens"] == run["total_tokens"] > 0
    assert round(u["cost_usd"], 6) == round(run["total_cost_usd"], 6)
    assert {a["agent"] for a in u["by_agent"]} == {"researcher", "enricher", "personalizer"}
    assert u["limit"] == 500_000 and len(u["daily"]) == 1


async def test_limit_blocks_new_runs(client, acct):
    r = await client.patch("/orgs/current", json={"monthly_token_limit": 1000}, headers=acct.headers)
    assert r.status_code == 200 and r.json()["monthly_token_limit"] == 1000
    lead = await make_lead(client, acct)
    run = await run_to_gate(client, acct, lead["id"])  # first run starts under the limit...
    # ...but the pipeline halts as soon as the budget is exhausted, and later runs are refused outright
    assert run["status"] in ("failed", "awaiting_approval")
    lead2 = await make_lead(client, acct)
    blocked = await client.post(f"/leads/{lead2['id']}/runs", json={}, headers=acct.headers)
    assert blocked.status_code == 402 and blocked.json()["code"] == "usage_limit_exceeded"
    sub = await client.post(f"/leads/{lead2['id']}/replies", json={"body": "interested"}, headers=acct.headers)
    assert sub.status_code == 402


async def test_limit_midrun_fails_run_cleanly(client, acct):
    # tiny limit: first agent call exceeds it, so the next LLM step is refused
    await client.patch("/orgs/current", json={"monthly_token_limit": 1000}, headers=acct.headers)
    lead = await make_lead(client, acct, company="A" * 150)
    run = await run_to_gate(client, acct, lead["id"])
    assert run["status"] == "failed"
    assert "limit" in run["error"].lower()
    failed = [s for s in run["steps"] if s["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["agent"] != "researcher"
    await jobs.drain()


async def test_limit_validation_and_integrations(client, acct):
    assert (await client.patch("/orgs/current", json={"monthly_token_limit": 5}, headers=acct.headers)).status_code == 422
    integ = (await client.get("/integrations", headers=acct.headers)).json()
    assert integ["llm"]["provider"] == "mock" and integ["email"]["provider"] == "console"
    assert integ["queue"]["backend"] == "in-process"
    assert "key" not in str(integ).lower().replace("monkey", "")

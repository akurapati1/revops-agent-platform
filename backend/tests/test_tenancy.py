from tests.conftest import make_account, make_lead, run_to_gate


async def test_cross_tenant_isolation(client):
    a = await make_account(client, "Org A")
    b = await make_account(client, "Org B")
    lead_a = await make_lead(client, a, email="shared@prospect.com")
    # same email may exist independently in another tenant
    lead_b = await make_lead(client, b, email="shared@prospect.com")
    assert lead_a["id"] != lead_b["id"]

    for method, path in [("get", f"/leads/{lead_a['id']}"), ("delete", f"/leads/{lead_a['id']}"),
                         ("get", f"/leads/{lead_a['id']}/approvals")]:
        r = await client.request(method, path, headers=b.headers)
        assert r.status_code == 404, (method, path)
    assert (await client.patch(f"/leads/{lead_a['id']}", json={"company": "Pwned"}, headers=b.headers)).status_code == 404
    assert (await client.post(f"/leads/{lead_a['id']}/runs", json={}, headers=b.headers)).status_code == 404
    assert (await client.post(f"/leads/{lead_a['id']}/replies", json={"body": "hi"}, headers=b.headers)).status_code == 404

    listing = (await client.get("/leads", headers=b.headers)).json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == lead_b["id"]

    run = await run_to_gate(client, a, lead_a["id"])
    assert (await client.get(f"/runs/{run['id']}", headers=b.headers)).status_code == 404
    assert (await client.post(f"/runs/{run['id']}/cancel", headers=b.headers)).status_code == 404
    assert (await client.get("/runs", headers=b.headers)).json() == []
    assert (await client.get("/approvals", headers=b.headers)).json() == []
    approval_id = run["approvals"][0]["id"]
    assert (await client.post(f"/approvals/{approval_id}/approve", headers=b.headers)).status_code == 404
    assert (await client.patch(f"/approvals/{approval_id}", json={"body": "x"}, headers=b.headers)).status_code == 404
    stats_b = (await client.get("/dashboard/stats", headers=b.headers)).json()
    assert stats_b["kpis"]["total_runs"] == 0 and stats_b["kpis"]["pending_approvals"] == 0
    usage_b = (await client.get("/usage", headers=b.headers)).json()
    assert usage_b["tokens"] == 0


async def test_switch_org_requires_membership(client):
    a = await make_account(client, "Org A2")
    b = await make_account(client, "Org B2")
    other_org = (await client.get("/auth/me", headers=b.headers)).json()["org"]["id"]
    r = await client.post("/auth/switch-org", json={"org_id": other_org}, headers=a.headers)
    assert r.status_code == 404

import pytest

from tests.conftest import make_account, make_lead, run_to_gate


async def submit(client, acct, lead_id, body):
    from app.services import jobs

    r = await client.post(f"/leads/{lead_id}/replies", json={"body": body}, headers=acct.headers)
    assert r.status_code == 202, r.text
    await jobs.drain()
    replies = (await client.get(f"/leads/{lead_id}/replies", headers=acct.headers)).json()
    run = (await client.get(f"/runs/{r.json()['id']}", headers=acct.headers)).json()
    return replies[0], run


@pytest.mark.parametrize("text,cls,lead_status,has_draft", [
    ("Sounds great, I'm interested - can we schedule a demo next week?", "interested", "interested", True),
    ("Thanks but this is too expensive for our budget right now.", "objection", "replied", True),
    ("I am out of office until Monday 12 May with limited email access.", "out_of_office", "replied", False),
    ("Please unsubscribe me and stop contacting me.", "unsubscribe", "unsubscribed", False),
    ("Who is this?", "other", "replied", False),
])
async def test_reply_classification(client, acct, text, cls, lead_status, has_draft):
    lead = await make_lead(client, acct)
    reply, run = await submit(client, acct, lead["id"], text)
    assert reply["classification"] == cls and reply["summary"]
    assert run["kind"] == "triage" and run["steps"][0]["agent"] == "triage"
    assert (run["approvals"] != []) is has_draft
    if has_draft:
        assert run["status"] == "awaiting_approval" and run["approvals"][0]["kind"] == "reply"
    else:
        assert run["status"] == "completed"
    assert (await client.get(f"/leads/{lead['id']}", headers=acct.headers)).json()["status"] == lead_status


async def test_unsubscribe_cancels_sequence_and_blocks_outreach(client, acct, mail):
    lead = await make_lead(client, acct)
    run = await run_to_gate(client, acct, lead["id"])
    await submit(client, acct, lead["id"], "Remove me from your list. Unsubscribe.")
    assert (await client.get("/approvals?status=pending", headers=acct.headers)).json() == []
    assert (await client.get(f"/runs/{run['id']}", headers=acct.headers)).json()["status"] == "rejected"
    assert (await client.post(f"/approvals/{run['approvals'][0]['id']}/approve", headers=acct.headers)).status_code == 409
    assert (await client.post(f"/leads/{lead['id']}/runs", json={}, headers=acct.headers)).status_code == 409
    assert mail.sent == []


async def test_reply_webhook(client, acct):
    from app.services import jobs

    org = (await client.get("/orgs/current", headers=acct.headers)).json()
    lead = await make_lead(client, acct, email="hook@prospect.com")
    r = await client.post(f"/webhooks/replies/{org['webhook_token']}", json={"from_email": "hook@prospect.com", "body": "Let's chat - interested!"})
    assert r.status_code == 202
    await jobs.drain()
    replies = (await client.get(f"/leads/{lead['id']}/replies", headers=acct.headers)).json()
    assert replies[0]["source"] == "webhook" and replies[0]["classification"] == "interested"
    assert (await client.post("/webhooks/replies/wrong-token", json={"from_email": "hook@prospect.com", "body": "x"})).status_code == 404
    other = await make_account(client, "Other")
    r2 = await client.post(f"/webhooks/replies/{org['webhook_token']}", json={"from_email": "nobody@x.com", "body": "x"})
    assert r2.status_code == 404
    assert other

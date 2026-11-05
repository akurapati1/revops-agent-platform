from tests.conftest import make_lead


async def test_lead_crud(client, acct):
    lead = await make_lead(client, acct, email="Mixed.Case@Prospect.com")
    assert lead["email"] == "mixed.case@prospect.com" and lead["status"] == "new" and lead["source"] == "manual"
    dup = await client.post("/leads", json={"email": "mixed.case@prospect.com"}, headers=acct.headers)
    assert dup.status_code == 409
    assert (await client.post("/leads", json={"email": "not-an-email"}, headers=acct.headers)).status_code == 422
    upd = await client.patch(f"/leads/{lead['id']}", json={"title": "CRO"}, headers=acct.headers)
    assert upd.json()["title"] == "CRO"
    got = await client.get(f"/leads/{lead['id']}", headers=acct.headers)
    assert got.json()["brief"] is None
    assert (await client.delete(f"/leads/{lead['id']}", headers=acct.headers)).status_code == 204
    assert (await client.get(f"/leads/{lead['id']}", headers=acct.headers)).status_code == 404


async def test_lead_filters_and_pagination(client, acct):
    for i in range(5):
        await make_lead(client, acct, email=f"p{i}@filter.com", company="Zenith" if i < 2 else "Other")
    r = (await client.get("/leads?q=zenith", headers=acct.headers)).json()
    assert r["total"] == 2
    page = (await client.get("/leads?limit=2&offset=2", headers=acct.headers)).json()
    assert page["total"] == 5 and len(page["items"]) == 2
    assert (await client.get("/leads?status=interested", headers=acct.headers)).json()["total"] == 0


CSV = """Email Address,First Name,Last Name,Company Name,Job Title,Website
ann@one.com,Ann,Lee,One Inc,CEO,one.com
bob@two.com,Bob,Ray,Two LLC,CTO,two.com
ann@one.com,Ann,Dup,One Inc,CEO,one.com
broken-email,Bad,Row,X,Y,z.com
,Empty,Row,X,Y,z.com
"""


async def test_csv_import(client, acct):
    r = await client.post("/leads/import", files={"file": ("leads.csv", CSV.encode(), "text/csv")}, headers=acct.headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2 and body["skipped"] == 1 and len(body["errors"]) == 2
    assert {e["row"] for e in body["errors"]} == {5, 6}
    again = (await client.post("/leads/import", files={"file": ("leads.csv", CSV.encode(), "text/csv")}, headers=acct.headers)).json()
    assert again["created"] == 0 and again["skipped"] == 3
    listing = (await client.get("/leads?q=one", headers=acct.headers)).json()
    assert listing["items"][0]["source"] == "csv" and listing["items"][0]["company"] == "One Inc"


async def test_csv_requires_email_column(client, acct):
    r = await client.post("/leads/import", files={"file": ("x.csv", b"name,company\nA,B\n", "text/csv")}, headers=acct.headers)
    assert r.status_code == 400 and r.json()["code"] == "csv_missing_email"

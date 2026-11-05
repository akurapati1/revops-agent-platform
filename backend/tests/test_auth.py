import httpx

from app.core.config import get_settings
from app.routers import auth as auth_router
from tests.conftest import make_account


async def test_signup_login_me(client):
    acct = await make_account(client, "Globex")
    me = await client.get("/auth/me", headers=acct.headers)
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == acct.email
    assert body["org"]["name"] == "Globex" and body["org"]["role"] == "owner"
    r = await client.post("/auth/login", json={"email": acct.email, "password": "correct-horse-battery"})
    assert r.status_code == 200 and r.json()["access_token"]


async def test_duplicate_and_bad_credentials(client):
    acct = await make_account(client)
    dup = await client.post("/auth/signup", json={"email": acct.email, "password": "another-password"})
    assert dup.status_code == 409
    bad = await client.post("/auth/login", json={"email": acct.email, "password": "wrong-password"})
    assert bad.status_code == 401
    weak = await client.post("/auth/signup", json={"email": "weak@example.com", "password": "short"})
    assert weak.status_code == 422


async def test_requires_token(client):
    assert (await client.get("/leads")).status_code == 401
    assert (await client.get("/leads", headers={"Authorization": "Bearer nope"})).status_code == 401


async def test_refresh_flow_and_token_type_separation(client):
    acct = await make_account(client)
    r = await client.post("/auth/refresh", json={"refresh_token": acct.tokens["refresh_token"]})
    assert r.status_code == 200
    # refresh token must not work as access token, and vice versa
    bad = await client.get("/auth/me", headers={"Authorization": f"Bearer {acct.tokens['refresh_token']}"})
    assert bad.status_code == 401
    bad2 = await client.post("/auth/refresh", json={"refresh_token": acct.tokens["access_token"]})
    assert bad2.status_code == 401


async def test_invites_and_roles(client):
    owner = await make_account(client, "Initech")
    invitee_email = "newhire@example.com"
    inv = await client.post("/orgs/current/invitations", json={"email": invitee_email, "role": "member"}, headers=owner.headers)
    assert inv.status_code == 201
    r = await client.post("/auth/signup", json={"email": invitee_email, "password": "password-12345", "invite_token": inv.json()["token"]})
    assert r.status_code == 201
    member_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = (await client.get("/auth/me", headers=member_headers)).json()
    assert me["org"]["name"] == "Initech" and me["org"]["role"] == "member"
    # members cannot invite or change settings
    assert (await client.post("/orgs/current/invitations", json={"email": "x@example.com"}, headers=member_headers)).status_code == 403
    assert (await client.patch("/orgs/current", json={"name": "Hacked"}, headers=member_headers)).status_code == 403
    org = (await client.get("/orgs/current", headers=member_headers)).json()
    assert org["webhook_token"] is None
    members = (await client.get("/orgs/current/members", headers=owner.headers)).json()
    assert {m["email"] for m in members} == {owner.email, invitee_email}
    # last owner cannot be demoted
    owner_id = me_id = (await client.get("/auth/me", headers=owner.headers)).json()["user"]["id"]
    assert owner_id == me_id
    demote = await client.patch(f"/orgs/current/members/{owner_id}", json={"role": "admin"}, headers=owner.headers)
    assert demote.status_code == 409


async def test_oauth_hidden_when_unconfigured(client):
    assert (await client.get("/auth/oauth/providers")).json() == {"google": False, "github": False}
    assert (await client.get("/auth/oauth/google/login")).status_code == 404


async def test_github_oauth_flow(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "github_client_id", "cid")
    monkeypatch.setattr(s, "github_client_secret", "secret")
    assert (await client.get("/auth/oauth/providers")).json()["github"] is True
    r = await client.get("/auth/oauth/github/login", follow_redirects=False)
    assert r.status_code == 307 and "github.com/login/oauth/authorize" in r.headers["location"]
    state = r.headers["location"].split("state=")[1].split("&")[0]

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "gho_x"})
        if req.url.path == "/user":
            return httpx.Response(200, json={"id": 4242, "login": "octo", "name": "Octo Cat", "avatar_url": "http://a/b.png"})
        if req.url.path == "/user/emails":
            return httpx.Response(200, json=[{"email": "octo@example.com", "primary": True, "verified": True}])
        return httpx.Response(404)

    monkeypatch.setattr(auth_router, "oauth_transport", httpx.MockTransport(handler))
    cb = await client.get(f"/auth/oauth/github/callback?code=abc&state={state}", follow_redirects=False)
    assert cb.status_code == 307
    loc = cb.headers["location"]
    assert loc.startswith(s.frontend_url + "/auth/callback#access_token=")
    token = loc.split("access_token=")[1].split("&")[0]
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["user"]["email"] == "octo@example.com"
    # second login maps to the same user
    cb2 = await client.get(f"/auth/oauth/github/callback?code=abc&state={state}", follow_redirects=False)
    token2 = cb2.headers["location"].split("access_token=")[1].split("&")[0]
    assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {token2}"})).json()["user"]["id"] == me.json()["user"]["id"]
    # tampered state is rejected
    bad = await client.get("/auth/oauth/github/callback?code=abc&state=garbage", follow_redirects=False)
    assert "error=oauth_failed" in bad.headers["location"]


async def test_auth_rate_limit(client, monkeypatch):
    from app.core.ratelimit import get_limiter

    monkeypatch.setattr(get_settings(), "auth_rate_limit_per_minute", 3)
    get_limiter().reset()
    codes = [(await client.post("/auth/login", json={"email": "nobody@example.com", "password": "x" * 9})).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]
    get_limiter().reset()

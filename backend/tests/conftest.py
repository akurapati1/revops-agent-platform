import os
import tempfile
import uuid

_tmp = tempfile.mkdtemp(prefix="revops-test-")
os.environ.update(
    APP_ENV="test",
    DATABASE_URL=f"sqlite+aiosqlite:///{_tmp}/test.db",
    LLM_PROVIDER="mock",
    EMAIL_PROVIDER="console",
    RUN_SCHEDULER="false",
    AUTO_CREATE_TABLES="true",
    AUTH_RATE_LIMIT_PER_MINUTE="100000",
    RATE_LIMIT_PER_MINUTE="100000",
    GOOGLE_CLIENT_ID="",
    GOOGLE_CLIENT_SECRET="",
    GITHUB_CLIENT_ID="",
    GITHUB_CLIENT_SECRET="",
    REDIS_URL="",
)
os.environ.pop("REDIS_URL")

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.db import create_all  # noqa: E402
from app.llm.factory import set_llm  # noqa: E402
from app.main import app  # noqa: E402
from app.services import jobs  # noqa: E402
from app.services.email import ConsoleEmailProvider, set_email_provider  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _db():
    await create_all()


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    await jobs.drain()


@pytest.fixture(autouse=True)
def _providers():
    set_llm(None)
    mail = ConsoleEmailProvider()
    set_email_provider(mail)
    yield mail
    set_llm(None)
    set_email_provider(None)


@pytest.fixture
def mail(_providers):
    return _providers


class Account:
    def __init__(self, email: str, headers: dict, tokens: dict):
        self.email, self.headers, self.tokens = email, headers, tokens


async def make_account(client: httpx.AsyncClient, org_name: str = "Acme Corp", email: str | None = None) -> Account:
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post("/auth/signup", json={"email": email, "password": "correct-horse-battery", "name": "Test User", "org_name": org_name})
    assert r.status_code == 201, r.text
    t = r.json()
    return Account(email, {"Authorization": f"Bearer {t['access_token']}"}, t)


@pytest_asyncio.fixture
async def acct(client):
    return await make_account(client)


async def make_lead(client, acct, **over) -> dict:
    body = {"email": f"lead-{uuid.uuid4().hex[:8]}@acme-prospect.com", "first_name": "Dana", "last_name": "Rivera",
            "company": "Northwind Labs", "title": "VP Sales", "website": "northwind.example"}
    body.update(over)
    r = await client.post("/leads", json=body, headers=acct.headers)
    assert r.status_code == 201, r.text
    return r.json()


async def run_to_gate(client, acct, lead_id: str, campaign: str = "q4") -> dict:
    r = await client.post(f"/leads/{lead_id}/runs", json={"campaign": campaign}, headers=acct.headers)
    assert r.status_code == 202, r.text
    await jobs.drain()
    d = await client.get(f"/runs/{r.json()['id']}", headers=acct.headers)
    assert d.status_code == 200
    return d.json()

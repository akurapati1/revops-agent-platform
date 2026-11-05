import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.agents.tools import _domain_of, next_business_slot, score_icp
from app.core.config import Settings, get_settings
from app.core.errors import LLMError
from app.llm.base import estimate_cost
from app.llm.openrouter import OpenRouterProvider
from app.services.email import OutboundEmail, SMTPEmailProvider

ICP = {"industries": ["B2B SaaS"], "min_employees": 50, "max_employees": 500, "regions": ["North America"]}


def test_icp_scoring_rubric():
    perfect, tier, _ = score_icp({"industry": "B2B SaaS", "employee_estimate": 120, "region": "North America"}, ICP, "economic_buyer")
    assert perfect == 100 and tier == "A"
    poor, tier2, _ = score_icp({"industry": "Mining", "employee_estimate": 5, "region": "APAC"}, ICP, "end_user")
    assert poor < 30 and tier2 == "C"
    mid, _, _ = score_icp({"industry": "B2B SaaS", "employee_estimate": 700, "region": "EMEA"}, ICP, "champion")
    assert poor < mid < perfect


def test_domain_extraction_and_scheduling():
    assert _domain_of({"website": "https://www.acme.io/pricing", "email": "a@gmail.com"}) == "acme.io"
    assert _domain_of({"website": "", "email": "a@corp.com"}) == "corp.com"
    assert _domain_of({"website": "", "email": "a@gmail.com"}) == ""
    friday = datetime(2026, 11, 6, 9, tzinfo=UTC)
    assert next_business_slot(friday, 1).weekday() == 0  # Saturday rolls to Monday


def test_cost_estimation():
    assert estimate_cost("openai/gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)


def test_database_url_normalised():
    assert Settings(database_url="postgres://u:p@h/db").database_url == "postgresql+asyncpg://u:p@h/db"


async def test_openrouter_provider_request_and_parsing():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}],
                                         "usage": {"prompt_tokens": 11, "completion_tokens": 7, "cost": 0.0042}})

    from app.agents.schemas import ResearchBrief

    s = Settings(openrouter_api_key="sk-test", llm_provider="openrouter")
    p = OpenRouterProvider(s, transport=httpx.MockTransport(handler))
    raw = await p.complete(agent="researcher", model="openai/gpt-4o-mini", system="sys", user="usr", schema=ResearchBrief, context={})
    assert raw.tokens_in == 11 and raw.tokens_out == 7 and raw.cost_usd == 0.0042
    assert seen["auth"] == "Bearer sk-test" and seen["body"]["model"] == "openai/gpt-4o-mini"
    assert seen["body"]["response_format"]["type"] == "json_schema"
    await p.aclose()


async def test_openrouter_requires_key_and_surfaces_errors():
    with pytest.raises(LLMError):
        OpenRouterProvider(Settings(openrouter_api_key=None))
    p = OpenRouterProvider(Settings(openrouter_api_key="k"), transport=httpx.MockTransport(lambda r: httpx.Response(429, text="slow down")))
    from app.agents.schemas import ResearchBrief

    with pytest.raises(LLMError, match="429"):
        await p.complete(agent="a", model="m", system="s", user="u", schema=ResearchBrief, context={})


async def test_smtp_provider_sends_via_aiosmtplib(monkeypatch):
    import aiosmtplib

    captured = {}

    async def fake_send(message, **kw):
        captured["msg"], captured["kw"] = message, kw

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    p = SMTPEmailProvider(Settings(smtp_host="smtp.test", smtp_port=2525, smtp_username="u", smtp_password="p"))
    res = await p.send(OutboundEmail(to="x@y.com", subject="Hi", body="Body", from_addr="Me <me@corp.com>"))
    assert captured["msg"]["To"] == "x@y.com" and captured["msg"]["Subject"] == "Hi"
    assert captured["kw"]["hostname"] == "smtp.test" and captured["kw"]["port"] == 2525
    assert res.message_id.endswith("@corp.com>") and res.provider == "smtp"
    with pytest.raises(RuntimeError):
        SMTPEmailProvider(Settings(smtp_host=None))


async def test_health_ready_and_agents_registry(client, acct):
    assert (await client.get("/health")).json() == {"status": "ok"}
    r = (await client.get("/ready")).json()
    assert r["status"] == "ready" and r["llm_provider"] == "mock"
    reg = (await client.get("/agents", headers=acct.headers)).json()
    assert [a["name"] for a in reg["agents"]] == ["researcher", "enricher", "personalizer", "sequencer", "triage"]
    assert reg["dags"]["outreach"] == ["researcher", "enricher", "personalizer", "sequencer"]


def test_alembic_migrations_apply_cleanly(tmp_path):
    backend = Path(__file__).resolve().parent.parent
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path}/m.db"}
    for cmd in (["upgrade", "head"], ["check"]):
        r = subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=backend, env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr + r.stdout
    assert get_settings()

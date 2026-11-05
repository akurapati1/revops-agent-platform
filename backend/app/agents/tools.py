"""Tools available to agents. Each takes the RunContext and returns JSON-serialisable observations."""
import asyncio
import ipaddress
import re
import socket
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx

from app.agents.base import RunContext, Tool

FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "proton.me", "aol.com"}


def _domain_of(lead: dict) -> str:
    site = (lead.get("website") or "").strip()
    if site:
        parsed = urlparse(site if "//" in site else f"//{site}")
        host = (parsed.hostname or "").lower()
        if host:
            return host.removeprefix("www.")
    email = lead.get("email", "")
    dom = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    return "" if dom in FREE_MAIL else dom


async def _is_public_host(host: str) -> bool:
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return bool(infos)


async def domain_info(ctx: RunContext) -> dict:
    """Derive the company domain; optionally fetch the homepage title/description (ENABLE_WEB_TOOLS)."""
    domain = _domain_of(ctx.lead)
    info: dict = {"domain": domain, "fetched": False}
    if not domain or not ctx.settings.enable_web_tools:
        return info
    if not await _is_public_host(domain):
        info["note"] = "skipped: host is not a public address"
        return info
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            r = await client.get(f"https://{domain}", headers={"User-Agent": "RevOpsAgentBot/1.0"})
        html = r.text[:200_000]
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.I | re.S)
        info.update(fetched=True, status=r.status_code, title=(title.group(1).strip() if title else "")[:200],
                    description=(desc.group(1).strip() if desc else "")[:400])
    except httpx.HTTPError as exc:
        info["note"] = f"fetch failed: {type(exc).__name__}"
    return info


def _range_score(value: int, lo: int | None, hi: int | None) -> float:
    if lo is None and hi is None:
        return 1.0
    lo = lo or 0
    hi = hi or 10**9
    if lo <= value <= hi:
        return 1.0
    edge = lo if value < lo else hi
    return max(0.0, 1 - abs(value - edge) / max(edge, 1))


def score_icp(firmographics: dict, icp: dict, persona: str) -> tuple[int, str, list[str]]:
    """Deterministic ICP rubric: industry 35, company size 30, region 15, persona 20."""
    reasons: list[str] = []
    total = 0.0
    inds = [i.lower() for i in icp.get("industries", [])]
    if inds:
        match = firmographics.get("industry", "").lower() in inds
        total += 35 if match else 8
        reasons.append(f"industry {'matches' if match else 'outside'} ICP")
    else:
        total += 35
    size = _range_score(int(firmographics.get("employee_estimate", 1)), icp.get("min_employees"), icp.get("max_employees"))
    total += 30 * size
    reasons.append(f"company size fit {int(size * 100)}%")
    regions = [r.lower() for r in icp.get("regions", [])]
    if regions:
        match = firmographics.get("region", "").lower() in regions
        total += 15 if match else 3
        reasons.append(f"region {'matches' if match else 'outside'} ICP")
    else:
        total += 15
    total += {"economic_buyer": 20, "champion": 15, "influencer": 9, "end_user": 5}.get(persona, 4)
    reasons.append(f"persona: {persona}")
    score = max(0, min(100, round(total)))
    tier = "A" if score >= 75 else "B" if score >= 50 else "C"
    return score, tier, reasons


def next_business_slot(start: datetime, days: int, hour: int = 14) -> datetime:
    """`days` after `start`, rolled forward past weekends, at `hour`:00 UTC."""
    dt = (start + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    if days == 0:
        return start
    while dt.weekday() >= 5:
        dt += timedelta(days=1)
    return dt


def now_utc() -> datetime:
    return datetime.now(UTC)


DOMAIN_INFO = Tool("domain_info", "Resolve the company domain and (optionally) fetch homepage metadata", domain_info)

"""Deterministic offline LLM. Produces schema-valid, context-aware output with no network or API key."""
import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel

from app.llm.base import RawCompletion, estimate_tokens

INDUSTRIES = ["B2B SaaS", "FinTech", "HealthTech", "E-commerce", "Cybersecurity", "Logistics", "EdTech", "Manufacturing"]
REGIONS = ["North America", "EMEA", "APAC", "LATAM"]
STAGES = ["Seed", "Series A", "Series B", "Series C", "Public", "Bootstrapped"]
STACKS = ["Salesforce", "HubSpot", "Snowflake", "AWS", "Kubernetes", "Stripe", "Segment", "Slack", "Postgres", "React"]
SIGNALS = [
    "recently announced a new product line",
    "is hiring for several go-to-market roles",
    "opened a new regional office",
    "published a customer case study this quarter",
    "raised a funding round in the last 12 months",
]
PAINS = [
    "pipeline visibility across a growing sales team",
    "slow, manual outbound research before every email",
    "inconsistent follow-up cadence",
    "difficulty prioritising leads that match the ideal customer profile",
]


def _h(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest(), 16)


def _pick(seq: list[str], seed: int, n: int) -> list[str]:
    out, i = [], seed
    while len(out) < min(n, len(seq)):
        item = seq[i % len(seq)]
        if item not in out:
            out.append(item)
        i = i // 7 + 3 + len(out)
    return out


def _lead(ctx: dict[str, Any]) -> dict[str, Any]:
    return ctx.get("lead", {})


def researcher(ctx: dict[str, Any]) -> dict[str, Any]:
    lead = _lead(ctx)
    company = lead.get("company") or "the company"
    seed = _h(company, lead.get("email", ""))
    site = (ctx.get("tools", {}).get("domain_info") or {}).get("domain") or lead.get("website") or ""
    industry = INDUSTRIES[seed % len(INDUSTRIES)]
    name = f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip() or "the contact"
    return {
        "company_summary": f"{company} is a {industry} company serving mid-market customers.",
        "what_they_do": f"{company} sells {industry.lower()} solutions and is scaling its go-to-market motion.",
        "person_summary": f"{name} is {lead.get('title') or 'a decision-maker'} at {company}.",
        "recent_signals": _pick(SIGNALS, seed, 3),
        "pain_points": _pick(PAINS, seed >> 4, 3),
        "talking_points": [
            f"Reference {company}'s momentum: it {_pick(SIGNALS, seed, 1)[0]}.",
            f"Tie our value to {_pick(PAINS, seed >> 4, 1)[0]}.",
        ],
        "sources": [s for s in [site, lead.get("linkedin_url", "")] if s],
    }


def enricher(ctx: dict[str, Any]) -> dict[str, Any]:
    lead = _lead(ctx)
    company = lead.get("company") or "unknown"
    seed = _h(company, "enrich")
    sizes = [12, 35, 80, 150, 320, 700, 1500]
    title = (lead.get("title") or "").lower()
    persona = "unknown"
    if any(k in title for k in ("ceo", "founder", "cro", "vp", "head", "chief", "director")):
        persona = "economic_buyer"
    elif any(k in title for k in ("manager", "lead")):
        persona = "champion"
    elif title:
        persona = "influencer"
    return {
        "industry": INDUSTRIES[seed % len(INDUSTRIES)],
        "employee_estimate": sizes[(seed >> 3) % len(sizes)],
        "region": REGIONS[(seed >> 5) % len(REGIONS)],
        "funding_stage": STAGES[(seed >> 7) % len(STAGES)],
        "tech_stack": _pick(STACKS, seed >> 9, 4),
        "buying_persona": persona,
        "icp_score": 0,
        "fit_tier": "C",
        "icp_reasoning": f"Estimated from public signals for {company}; final score is computed by the ICP rubric tool.",
    }


def personalizer(ctx: dict[str, Any]) -> dict[str, Any]:
    lead = _lead(ctx)
    org = ctx.get("org", {})
    brief = ctx.get("research", {})
    first = lead.get("first_name") or "there"
    company = lead.get("company") or "your team"
    sender = org.get("sender_name") or "The RevOps Team"
    pitch = org.get("product_pitch") or "an AI sales-ops platform that automates research and outreach"
    signal = (brief.get("recent_signals") or ["your recent growth"])[0]
    pain = (brief.get("pain_points") or ["manual prospecting work"])[0]
    return {
        "steps": [
            {
                "step_number": 1,
                "delay_days": 0,
                "angle": "signal-based opener",
                "subject": f"Quick idea for {company}",
                "body": f"Hi {first},\n\nI noticed {company} {signal}. Teams in that position often struggle with {pain}.\n\nWe built {pitch}. Worth a 15-minute look?\n\nBest,\n{sender}",
            },
            {
                "step_number": 2,
                "delay_days": 3,
                "angle": "value proof",
                "subject": f"Re: Quick idea for {company}",
                "body": f"Hi {first},\n\nFollowing up with a concrete example: similar teams cut research time per lead from 20 minutes to under 2 while keeping every email human-approved.\n\nWould it help if I sent a short walkthrough?\n\n{sender}",
            },
            {
                "step_number": 3,
                "delay_days": 7,
                "angle": "break-up",
                "subject": f"Should I close the loop, {first}?",
                "body": f"Hi {first},\n\nI don't want to clutter your inbox. If improving {pain} is not a priority this quarter, just say the word and I'll stop reaching out.\n\n{sender}",
            },
        ]
    }


_UNSUB = re.compile(r"\b(unsubscribe|remove me|stop (emailing|contacting)|do not (contact|email)|take me off)\b", re.I)
_OOO = re.compile(r"\b(out of (the )?office|on (vacation|leave|holiday)|auto-?reply|away until|maternity|paternity)\b", re.I)
_INTEREST = re.compile(r"\b(interested|sounds (good|great)|let'?s (talk|chat|schedule)|book|demo|send (me )?(more|details|info)|call me|free (on|next))\b", re.I)
_OBJ = re.compile(r"\b(too expensive|budget|not (a priority|now|interested)|already (use|have)|no need|competitor|timing|not the right)\b", re.I)


def triage(ctx: dict[str, Any]) -> dict[str, Any]:
    text = ctx.get("reply_body", "")
    lead = _lead(ctx)
    first = lead.get("first_name") or "there"
    sender = ctx.get("org", {}).get("sender_name") or "The RevOps Team"
    if _UNSUB.search(text):
        cls, conf, action, draft, obj = "unsubscribe", 0.97, "Mark lead unsubscribed and stop all sequences.", None, None
        summary = "The contact asked to stop receiving emails."
    elif _OOO.search(text):
        cls, conf, action, draft, obj = "out_of_office", 0.93, "Pause the sequence and resume after the return date.", None, None
        summary = "Automatic out-of-office reply."
    elif _OBJ.search(text) and not re.search(r"\b(interested|demo)\b", text, re.I):
        m = _OBJ.search(text)
        obj = (m.group(0) if m else "other").lower()
        cls, conf, action = "objection", 0.86, "Send a short, empathetic objection-handling reply."
        summary = f"The contact raised an objection ({obj})."
        draft = f"Hi {first},\n\nThanks for the candid reply - completely understand. Many teams felt the same about {obj} before seeing how little setup is needed. Happy to share a one-page summary and leave it with you.\n\n{sender}"
    elif _INTEREST.search(text):
        cls, conf, action, obj = "interested", 0.91, "Reply quickly with meeting times.", None
        summary = "The contact expressed interest and wants to talk."
        draft = f"Hi {first},\n\nGreat to hear! Here are a few times that work this week: Tue 10:00, Wed 14:00, Thu 11:00 (your timezone). Let me know what suits you and I'll send an invite.\n\n{sender}"
    else:
        cls, conf, action, draft, obj = "other", 0.55, "Review manually.", None, None
        summary = "Could not confidently classify the reply."
    rd = re.search(r"(?:until|back on|return(?:ing)? on)\s+([A-Za-z0-9 ,/\-]{3,20})", text, re.I) if cls == "out_of_office" else None
    return {
        "classification": cls,
        "confidence": conf,
        "summary": summary,
        "objection_type": obj,
        "return_date": rd.group(1).strip() if rd else None,
        "suggested_action": action,
        "draft_reply": draft,
    }


GENERATORS = {"researcher": researcher, "enricher": enricher, "personalizer": personalizer, "triage": triage}


class MockProvider:
    name = "mock"

    async def complete(
        self, *, agent: str, model: str, system: str, user: str, schema: type[BaseModel], context: dict[str, Any]
    ) -> RawCompletion:
        gen = GENERATORS.get(agent)
        if gen is None:
            raise ValueError(f"MockProvider has no generator for agent '{agent}'")
        content = json.dumps(gen(context))
        return RawCompletion(content=content, tokens_in=estimate_tokens(system + user), tokens_out=estimate_tokens(content))

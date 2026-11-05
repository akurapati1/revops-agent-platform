"""The five concrete agents."""
from datetime import datetime
from typing import Any

from app.agents.base import Agent, AgentResult, RunContext, Tool
from app.agents.schemas import (
    EmailSequence,
    Enrichment,
    ResearchBrief,
    Schedule,
    TriageResult,
)
from app.agents.tools import DOMAIN_INFO, next_business_slot, now_utc, score_icp


async def _icp_rubric(ctx: RunContext) -> dict[str, Any]:
    return {"icp": ctx.org.get("icp", {}), "rubric": "industry 35 / size 30 / region 15 / persona 20"}


class Researcher(Agent):
    name = "researcher"
    description = "Builds a company and person brief from lead data and public signals."
    output_schema = ResearchBrief
    tools = (DOMAIN_INFO,)
    system_prompt = (
        "You are a B2B sales researcher. Using ONLY the provided lead data and tool observations, write a concise brief "
        "about the company and the person. Never invent specific facts you cannot support; mark inferred items as "
        "likely. Output recent signals, pain points a seller could address, and talking points."
    )

    def build_input(self, ctx: RunContext) -> dict[str, Any]:
        return {"lead": ctx.lead, "icp": ctx.org.get("icp", {})}


class Enricher(Agent):
    name = "enricher"
    description = "Extracts firmographics and computes an ICP fit score."
    output_schema = Enrichment
    depends_on = ("researcher",)

    system_prompt = (
        "You are a revenue-operations analyst. From the lead and research brief, extract firmographics: industry, "
        "estimated employee count, region, funding stage, likely tech stack and the contact's buying persona. "
        "Give brief reasoning. The numeric ICP score is finalised by a deterministic rubric after your answer."
    )

    tools = (Tool("icp_rubric", "Load the org ICP definition and scoring rubric", _icp_rubric),)

    def postprocess(self, ctx: RunContext, output: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
        icp = ctx.org.get("icp", {})
        score, tier, reasons = score_icp(output, icp, output.get("buying_persona", "unknown"))
        output["icp_score"], output["fit_tier"] = score, tier
        output["icp_reasoning"] = (output.get("icp_reasoning") or "").strip() + " Rubric: " + "; ".join(reasons) + "."
        return output


class Personalizer(Agent):
    name = "personalizer"
    description = "Writes a tailored multi-step cold email sequence."
    output_schema = EmailSequence
    depends_on = ("researcher", "enricher")
    system_prompt = (
        "You are an expert outbound copywriter. Write a 3-step email sequence tailored to the lead using the research "
        "brief and firmographics. Rules: under 120 words per email, one clear low-friction ask, no fake familiarity, "
        "no false claims, step 1 delay_days=0, include a polite opt-out in the final step. Sign as the org's sender."
    )

    def build_input(self, ctx: RunContext) -> dict[str, Any]:
        return {
            "lead": ctx.lead,
            "sender_name": ctx.org.get("sender_name"),
            "product_pitch": ctx.org.get("product_pitch"),
            "research": ctx.state.get("researcher"),
            "enrichment": ctx.state.get("enricher"),
        }

    def llm_context(self, ctx: RunContext, inp: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
        return {"lead": ctx.lead, "org": ctx.org, "research": ctx.state.get("researcher", {}),
                "enrichment": ctx.state.get("enricher", {})}


class Sequencer(Agent):
    name = "sequencer"
    description = "Schedules each email step onto business days (deterministic, no LLM)."
    output_schema = Schedule
    depends_on = ("personalizer",)
    uses_llm = False

    def build_input(self, ctx: RunContext) -> dict[str, Any]:
        return {"steps": ctx.state["personalizer"]["steps"]}

    async def run(self, ctx: RunContext, inp: dict[str, Any]) -> AgentResult:
        start = now_utc()
        steps = []
        for s in sorted(inp["steps"], key=lambda x: x["step_number"]):
            cumulative = sum(x["delay_days"] for x in inp["steps"] if x["step_number"] <= s["step_number"])
            when: datetime = next_business_slot(start, cumulative)
            steps.append({"step_number": s["step_number"], "scheduled_at": when.isoformat(),
                          "subject": s["subject"], "body": s["body"]})
        out = Schedule(steps=steps, timezone="UTC").model_dump()
        call = {"tool": "business_hours_scheduler", "ok": True, "result": {"steps": len(steps)}}
        return AgentResult(output=out, tool_calls=[call])


class ReplyTriage(Agent):
    name = "triage"
    description = "Classifies an inbound reply and drafts a response."
    output_schema = TriageResult
    system_prompt = (
        "You triage replies to cold outreach. Classify as interested, objection, out_of_office, unsubscribe or other. "
        "Give confidence 0-1 and a one-sentence summary. For interested/objection replies draft a short, warm, honest "
        "response (<90 words). Never draft a reply to unsubscribe or out-of-office messages."
    )

    def build_input(self, ctx: RunContext) -> dict[str, Any]:
        return {"lead": ctx.lead, "reply": ctx.extra.get("reply_body", "")}

    def postprocess(self, ctx: RunContext, output: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
        if output["classification"] in ("unsubscribe", "out_of_office"):
            output["draft_reply"] = None
        return output

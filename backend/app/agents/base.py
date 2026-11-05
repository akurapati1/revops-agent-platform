"""Agent base class, tool abstraction and shared run context."""
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic import BaseModel

from app.core.config import Settings
from app.llm.base import LLMProvider, LLMUsage, structured_call


@dataclass
class RunContext:
    """Shared state for one run; every agent reads prior outputs from `state` and writes its own."""

    run_id: str
    org: dict[str, Any]
    lead: dict[str, Any]
    settings: Settings
    llm: LLMProvider
    state: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)  # e.g. reply_body for triage


ToolFn = Callable[[RunContext], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    fn: ToolFn


@dataclass
class AgentResult:
    output: dict[str, Any]
    model: str | None = None
    usage: LLMUsage | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    """Each agent has its own prompt, tools, and Pydantic output schema."""

    name: ClassVar[str]
    description: ClassVar[str]
    system_prompt: ClassVar[str]
    output_schema: ClassVar[type[BaseModel]]
    depends_on: ClassVar[tuple[str, ...]] = ()
    tools: ClassVar[tuple[Tool, ...]] = ()
    uses_llm: ClassVar[bool] = True

    def build_input(self, ctx: RunContext) -> dict[str, Any]:
        """The JSON-serialisable input snapshot persisted in the trace."""
        return {"lead": ctx.lead, "org": ctx.org, **{k: ctx.state[k] for k in self.depends_on if k in ctx.state}}

    def user_prompt(self, inp: dict[str, Any], tool_results: dict[str, Any]) -> str:
        return (
            "Input:\n" + json.dumps(inp, indent=2, default=str)
            + "\n\nTool observations:\n" + json.dumps(tool_results, indent=2, default=str)
        )

    def llm_context(self, ctx: RunContext, inp: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
        """Structured context handed to the provider (the mock uses it; real providers use the prompt)."""
        return {"lead": ctx.lead, "org": ctx.org, "tools": tool_results, **ctx.extra,
                **{k: ctx.state[k] for k in self.depends_on if k in ctx.state}}

    def postprocess(self, ctx: RunContext, output: dict[str, Any], tool_results: dict[str, Any]) -> dict[str, Any]:
        return output

    async def run_tools(self, ctx: RunContext) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        results: dict[str, Any] = {}
        calls: list[dict[str, Any]] = []
        for tool in self.tools:
            try:
                res = await tool.fn(ctx)
                calls.append({"tool": tool.name, "ok": True, "result": res})
                results[tool.name] = res
            except Exception as exc:  # tool failures are non-fatal observations
                calls.append({"tool": tool.name, "ok": False, "error": str(exc)})
                results[tool.name] = {"error": str(exc)}
        return results, calls

    async def run(self, ctx: RunContext, inp: dict[str, Any]) -> AgentResult:
        tool_results, calls = await self.run_tools(ctx)
        model = ctx.settings.model_for(self.name)
        res = await structured_call(
            ctx.llm,
            agent=self.name,
            model=model,
            system=self.system_prompt,
            user=self.user_prompt(inp, tool_results),
            schema=self.output_schema,
            context=self.llm_context(ctx, inp, tool_results),
            max_retries=ctx.settings.llm_max_retries,
        )
        out = self.postprocess(ctx, res.parsed.model_dump(), tool_results)
        out = self.output_schema.model_validate(out).model_dump()
        return AgentResult(output=out, model=model, usage=res.usage, tool_calls=calls)

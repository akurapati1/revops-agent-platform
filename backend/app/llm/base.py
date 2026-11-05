"""LLM provider interface + structured-output helper (validate with Pydantic, retry on failure)."""
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.errors import LLMError

T = TypeVar("T", bound=BaseModel)

# USD per 1M tokens (input, output). Unknown models fall back to DEFAULT_PRICE.
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "anthropic/claude-3.5-haiku": (0.80, 4.00),
    "anthropic/claude-3.5-sonnet": (3.00, 15.00),
    "google/gemini-flash-1.5": (0.075, 0.30),
}
DEFAULT_PRICE = (0.50, 1.50)


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = PRICES.get(model, DEFAULT_PRICE)
    return round((tokens_in * pin + tokens_out * pout) / 1_000_000, 6)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class RawCompletion:
    content: str
    tokens_in: int
    tokens_out: int
    cost_usd: float | None = None  # provider-reported cost, if any


@dataclass
class LLMUsage:
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    attempts: int = 0

    @property
    def total_tokens(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass
class StructuredResult:
    parsed: Any
    usage: LLMUsage
    raw: str = ""
    errors: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    name: str

    async def complete(
        self, *, agent: str, model: str, system: str, user: str, schema: type[BaseModel], context: dict[str, Any]
    ) -> RawCompletion: ...


def _extract_json(text: str) -> Any:
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


async def structured_call(
    provider: LLMProvider,
    *,
    agent: str,
    model: str,
    system: str,
    user: str,
    schema: type[T],
    context: dict[str, Any],
    max_retries: int = 2,
) -> StructuredResult:
    """Call the provider and validate against `schema`, feeding validation errors back on retry."""
    usage = LLMUsage(model=model)
    errors: list[str] = []
    prompt = user
    for attempt in range(max_retries + 1):
        started = time.perf_counter()
        raw = await provider.complete(
            agent=agent, model=model, system=system, user=prompt, schema=schema, context=context
        )
        usage.latency_ms += int((time.perf_counter() - started) * 1000)
        usage.attempts = attempt + 1
        usage.tokens_in += raw.tokens_in
        usage.tokens_out += raw.tokens_out
        usage.cost_usd += raw.cost_usd if raw.cost_usd is not None else estimate_cost(model, raw.tokens_in, raw.tokens_out)
        try:
            parsed = schema.model_validate(_extract_json(raw.content))
            usage.cost_usd = round(usage.cost_usd, 6)
            return StructuredResult(parsed=parsed, usage=usage, raw=raw.content, errors=errors)
        except (ValidationError, json.JSONDecodeError) as exc:
            msg = str(exc)[:600]
            errors.append(msg)
            prompt = (
                f"{user}\n\nYour previous reply was invalid: {msg}\n"
                "Reply again with ONLY a JSON object that satisfies the schema."
            )
    raise LLMError(f"{agent}: model failed to produce valid structured output after {max_retries + 1} attempts: {errors[-1]}")

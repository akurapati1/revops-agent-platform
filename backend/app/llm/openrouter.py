"""OpenRouter (OpenAI-compatible) provider over httpx."""
import json
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import LLMError
from app.llm.base import RawCompletion, estimate_tokens


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if not settings.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY is not set (or use LLM_PROVIDER=mock)", code="llm_not_configured")
        self._s = settings
        self._client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url,
            timeout=settings.llm_timeout_seconds,
            transport=transport,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": settings.frontend_url,
                "X-Title": settings.app_name,
            },
        )

    async def complete(
        self, *, agent: str, model: str, system: str, user: str, schema: type[BaseModel], context: dict[str, Any]
    ) -> RawCompletion:
        json_schema = schema.model_json_schema()
        payload = {
            "model": model,
            "temperature": 0.4,
            "messages": [
                {
                    "role": "system",
                    "content": f"{system}\n\nRespond with ONLY a JSON object matching this JSON Schema:\n{json.dumps(json_schema)}",
                },
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema.__name__, "schema": json_schema, "strict": False},
            },
            "usage": {"include": True},
        }
        try:
            resp = await self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"OpenRouter request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise LLMError(f"OpenRouter returned {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("OpenRouter response had no choices") from exc
        usage = data.get("usage") or {}
        return RawCompletion(
            content=content,
            tokens_in=int(usage.get("prompt_tokens") or estimate_tokens(system + user)),
            tokens_out=int(usage.get("completion_tokens") or estimate_tokens(content)),
            cost_usd=usage.get("cost"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

from app.core.config import get_settings
from app.llm.base import LLMProvider
from app.llm.mock import MockProvider
from app.llm.openrouter import OpenRouterProvider

_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    global _provider
    if _provider is None:
        s = get_settings()
        _provider = MockProvider() if s.llm_provider == "mock" else OpenRouterProvider(s)
    return _provider


def set_llm(provider: LLMProvider | None) -> None:
    """Override the provider (used by tests)."""
    global _provider
    _provider = provider

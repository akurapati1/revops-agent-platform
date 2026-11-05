"""Application settings, loaded from environment variables (and .env)."""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "RevOps Agent Platform"
    database_url: str = "sqlite+aiosqlite:///./revops.db"
    auto_create_tables: bool = True
    redis_url: str | None = None

    # Auth
    jwt_secret: str = "dev-insecure-change-me-please-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"
    api_public_url: str = "http://localhost:8000"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None

    # LLM
    llm_provider: Literal["mock", "openrouter"] = "mock"
    openrouter_api_key: str | None = Field(default=None, repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    model_default: str = "openai/gpt-4o-mini"
    model_researcher: str | None = None
    model_enricher: str | None = None
    model_personalizer: str | None = "anthropic/claude-3.5-haiku"
    model_triage: str | None = None
    default_monthly_token_limit: int = 500_000

    # Email
    email_provider: Literal["console", "smtp"] = "console"
    email_from: str = "RevOps Agent <no-reply@example.com>"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = Field(default=None, repr=False)
    smtp_starttls: bool = True

    # Runtime
    rate_limit_per_minute: int = 240
    auth_rate_limit_per_minute: int = 20
    enable_web_tools: bool = False
    run_scheduler: bool = True
    scheduler_interval_seconds: int = 60
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def model_for(self, agent: str) -> str:
        return getattr(self, f"model_{agent}", None) or self.model_default

    def oauth_configured(self, provider: str) -> bool:
        return bool(getattr(self, f"{provider}_client_id", None) and getattr(self, f"{provider}_client_secret", None))


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.app_env == "production" and s.jwt_secret.startswith("dev-insecure"):
        raise RuntimeError("JWT_SECRET must be set in production")
    return s

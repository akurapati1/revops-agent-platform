"""Hand-rolled OAuth2 authorization-code flow for Google and GitHub."""
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.core.config import Settings
from app.core.errors import AppError


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    authorize_url: str
    token_url: str
    scope: str


PROVIDERS = {
    "google": ProviderSpec("google", "https://accounts.google.com/o/oauth2/v2/auth",
                           "https://oauth2.googleapis.com/token", "openid email profile"),
    "github": ProviderSpec("github", "https://github.com/login/oauth/authorize",
                           "https://github.com/login/oauth/access_token", "read:user user:email"),
}


@dataclass
class OAuthProfile:
    provider_user_id: str
    email: str
    name: str
    avatar: str | None


def redirect_uri(settings: Settings, provider: str) -> str:
    return f"{settings.api_public_url.rstrip('/')}/auth/oauth/{provider}/callback"


def authorize_url(settings: Settings, provider: str, state: str) -> str:
    spec = PROVIDERS[provider]
    client_id = getattr(settings, f"{provider}_client_id")
    params = {"client_id": client_id, "redirect_uri": redirect_uri(settings, provider), "scope": spec.scope,
              "state": state, "response_type": "code"}
    if provider == "google":
        params["access_type"] = "online"
        params["prompt"] = "select_account"
    return f"{spec.authorize_url}?{urlencode(params)}"


async def fetch_profile(settings: Settings, provider: str, code: str,
                        transport: httpx.AsyncBaseTransport | None = None) -> OAuthProfile:
    spec = PROVIDERS[provider]
    async with httpx.AsyncClient(timeout=15, transport=transport) as client:
        resp = await client.post(
            spec.token_url,
            data={"client_id": getattr(settings, f"{provider}_client_id"),
                  "client_secret": getattr(settings, f"{provider}_client_secret"), "code": code,
                  "redirect_uri": redirect_uri(settings, provider), "grant_type": "authorization_code"},
            headers={"Accept": "application/json"},
        )
        token = resp.json().get("access_token") if resp.status_code == 200 else None
        if not token:
            raise AppError("OAuth token exchange failed", code="oauth_failed")
        auth = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if provider == "google":
            info = (await client.get("https://openidconnect.googleapis.com/v1/userinfo", headers=auth)).json()
            if not info.get("email") or not info.get("email_verified", False):
                raise AppError("Google account email is not verified", code="oauth_failed")
            return OAuthProfile(str(info["sub"]), info["email"], info.get("name", ""), info.get("picture"))
        user = (await client.get("https://api.github.com/user", headers=auth)).json()
        emails = (await client.get("https://api.github.com/user/emails", headers=auth)).json()
        primary = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None) if isinstance(emails, list) else None
        if not primary:
            raise AppError("GitHub account has no verified primary email", code="oauth_failed")
        return OAuthProfile(str(user["id"]), primary, user.get("name") or user.get("login", ""), user.get("avatar_url"))

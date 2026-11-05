"""Pluggable email delivery."""
import uuid
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

log = get_logger("email")


@dataclass
class OutboundEmail:
    to: str
    subject: str
    body: str
    from_addr: str
    reply_to: str | None = None


@dataclass
class SendResult:
    message_id: str
    provider: str


class EmailProvider(Protocol):
    name: str

    async def send(self, msg: OutboundEmail) -> SendResult: ...


class ConsoleEmailProvider:
    """Logs the email instead of sending it (default; safe for demos and tests)."""

    name = "console"

    def __init__(self) -> None:
        self.sent: list[OutboundEmail] = []

    async def send(self, msg: OutboundEmail) -> SendResult:
        self.sent.append(msg)
        mid = f"console-{uuid.uuid4().hex[:12]}"
        log.info("email.console_send", extra={"to": msg.to, "subject": msg.subject, "message_id": mid})
        return SendResult(message_id=mid, provider=self.name)


class SMTPEmailProvider:
    name = "smtp"

    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host:
            raise RuntimeError("SMTP_HOST must be set when EMAIL_PROVIDER=smtp")
        self._s = settings

    async def send(self, msg: OutboundEmail) -> SendResult:
        import aiosmtplib

        em = EmailMessage()
        em["From"] = msg.from_addr
        em["To"] = msg.to
        em["Subject"] = msg.subject
        if msg.reply_to:
            em["Reply-To"] = msg.reply_to
        domain = msg.from_addr.rsplit("@", 1)[-1].strip("> ") or "localhost"
        mid = f"<{uuid.uuid4().hex}@{domain}>"
        em["Message-ID"] = mid
        em.set_content(msg.body)
        await aiosmtplib.send(
            em,
            hostname=self._s.smtp_host,
            port=self._s.smtp_port,
            username=self._s.smtp_username,
            password=self._s.smtp_password,
            start_tls=self._s.smtp_starttls,
            timeout=30,
        )
        return SendResult(message_id=mid, provider=self.name)


_provider: EmailProvider | None = None


def get_email_provider() -> EmailProvider:
    global _provider
    if _provider is None:
        s = get_settings()
        _provider = SMTPEmailProvider(s) if s.email_provider == "smtp" else ConsoleEmailProvider()
    return _provider


def set_email_provider(p: EmailProvider | None) -> None:
    global _provider
    _provider = p

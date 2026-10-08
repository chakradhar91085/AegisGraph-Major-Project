"""
AegisGraph — admin security alerts over Telegram and email.

A channel stays silent until its settings are filled in (see config.py).
Pipeline alerts are fire-and-forget so a slow Telegram or SMTP server never
delays a user's answer.
"""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_pending: set[asyncio.Task] = set()


def configured_channels() -> list[str]:
    channels = []
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        channels.append("telegram")
    if settings.SMTP_USER and settings.SMTP_PASSWORD and settings.ALERT_EMAIL_TO:
        channels.append("email")
    return channels


async def _send_telegram(text: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text},
        )
        response.raise_for_status()


def _send_email_blocking(subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = settings.ALERT_EMAIL_TO
    msg.set_content(text)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


async def send_alert(subject: str, text: str) -> dict[str, str]:
    """Send to every configured channel; returns 'sent' or the error per channel."""
    senders = {
        "telegram": lambda: _send_telegram(f"{subject}\n\n{text}"),
        "email": lambda: asyncio.to_thread(_send_email_blocking, subject, text),
    }
    results = {}
    for channel in configured_channels():
        try:
            await senders[channel]()
            results[channel] = "sent"
        except Exception as e:
            # Telegram errors echo the request URL, which contains the bot token.
            detail = str(e).replace(settings.TELEGRAM_BOT_TOKEN, "***") if settings.TELEGRAM_BOT_TOKEN else str(e)
            logger.error(f"Security alert via {channel} failed: {detail}")
            results[channel] = f"failed: {detail}"
    return results


def notify(subject: str, text: str) -> None:
    """Queue an alert without waiting for it."""
    if not configured_channels():
        return
    task = asyncio.create_task(send_alert(subject, text))
    _pending.add(task)
    task.add_done_callback(_pending.discard)

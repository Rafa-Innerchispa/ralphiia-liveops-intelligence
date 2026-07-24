from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("liveops.notify")

_PHONE_RE = re.compile(r"\+?\d[\d\s\-().:]{7,}\d")


def _redact(text: str) -> str:
    return _PHONE_RE.sub("[redacted]", text)


def _format_message(
    *,
    phase: str,
    correlation_id: str,
    public_url: str,
    user_prompt: str | None,
    extra: str | None = None,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prompt_line = (user_prompt or "").strip()
    if len(prompt_line) > 280:
        prompt_line = prompt_line[:277] + "…"
    if not prompt_line:
        prompt_line = "(default incident analysis)"
    lines = [
        f"LiveOps · {phase}",
        f"Time: {ts}",
        f"Prompt: {prompt_line}",
        f"Correlation: {correlation_id}",
        f"URL: {public_url.rstrip('/')}/",
    ]
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _send_whatsapp_sync(
    message: str,
    contact_ref: str,
    ralfia_root: str,
    number: str | None = None,
) -> dict[str, Any]:
    root = ralfia_root or os.getenv("RALFIA_OPENAI_ROOT", "/home/rlopez/projects/raphiia-openai")
    if root and root not in sys.path:
        sys.path.insert(0, root)
    try:
        from raphiia_openai import whatsapp_mcp_bridge  # type: ignore
    except ImportError:
        return {"ok": False, "error": "ralfia bridge unavailable"}
    result = whatsapp_mcp_bridge.send_whatsapp_message(
        message,
        contact_ref=contact_ref or None,
        number=(number or "").strip() or None,
        node="primary",
    )
    if isinstance(result, dict) and result.get("number"):
        result = {**result, "number": "[redacted]"}
    return result


async def notify_analysis_event(
    *,
    phase: str,
    correlation_id: str,
    public_url: str,
    user_prompt: str | None,
    enabled: bool,
    contact_ref: str,
    ralfia_root: str,
    number: str = "",
    extra: str | None = None,
) -> None:
    """Fire-and-forget WhatsApp alert; never raises to callers."""
    ref = contact_ref.strip()
    num = number.strip()
    if not enabled or (not ref and not num):
        return
    body = _format_message(
        phase=phase,
        correlation_id=correlation_id,
        public_url=public_url,
        user_prompt=user_prompt,
        extra=extra,
    )
    try:
        result = await asyncio.to_thread(
            _send_whatsapp_sync, body, ref, ralfia_root, num or None
        )
        if not result.get("ok"):
            logger.info(
                "liveops whatsapp %s skipped/failed: %s",
                phase,
                _redact(str(result.get("error") or result)),
            )
        else:
            logger.info("liveops whatsapp %s sent correlation=%s", phase, correlation_id)
    except Exception as exc:
        logger.info("liveops whatsapp %s error: %s", phase, _redact(str(exc)))


def schedule_analysis_notify(
    *,
    phase: str,
    correlation_id: str,
    public_url: str,
    user_prompt: str | None,
    enabled: bool,
    contact_ref: str,
    ralfia_root: str,
    number: str = "",
    extra: str | None = None,
) -> None:
    asyncio.create_task(
        notify_analysis_event(
            phase=phase,
            correlation_id=correlation_id,
            public_url=public_url,
            user_prompt=user_prompt,
            enabled=enabled,
            contact_ref=contact_ref,
            ralfia_root=ralfia_root,
            number=number,
            extra=extra,
        )
    )

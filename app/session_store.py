from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

_SESSIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "sessions.json"
_lock = threading.Lock()
_sessions: dict[str, dict[str, Any]] = {}


def _load() -> None:
    global _sessions
    if not _SESSIONS_PATH.exists():
        return
    try:
        raw = json.loads(_SESSIONS_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            _sessions = raw
    except (OSError, json.JSONDecodeError):
        _sessions = {}


def _save() -> None:
    _SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SESSIONS_PATH.write_text(
        json.dumps(_sessions, ensure_ascii=False, indent=0)[:500_000],
        encoding="utf-8",
    )


_load()


def get_or_create_session(session_id: str | None) -> str:
    with _lock:
        if session_id and session_id.strip() in _sessions:
            return session_id.strip()
        sid = session_id.strip() if session_id and session_id.strip() else f"sess-{uuid.uuid4().hex[:12]}"
        _sessions.setdefault(sid, {"messages": []})
        _save()
        return sid


def append_message(session_id: str, role: str, content: str) -> None:
    with _lock:
        bucket = _sessions.setdefault(session_id, {"messages": []})
        msgs = bucket.setdefault("messages", [])
        msgs.append({"role": role, "content": content[:4000]})
        if len(msgs) > 24:
            bucket["messages"] = msgs[-24:]
        _save()


def session_context(session_id: str, limit: int = 4) -> list[dict[str, str]]:
    with _lock:
        bucket = _sessions.get(session_id) or {}
        msgs = bucket.get("messages") or []
        return list(msgs[-limit:])


def merge_prompt_with_session(
    session_id: str | None,
    prompt: str,
    *,
    research_deeper: bool = False,
) -> tuple[str, str]:
    """Returns (session_id, effective_prompt)."""
    sid = get_or_create_session(session_id)
    prior = session_context(sid)
    effective = prompt
    if research_deeper and prior:
        last_user = next(
            (m["content"] for m in reversed(prior) if m.get("role") == "user"),
            prompt,
        )
        effective = (
            f"{last_user} — research deeper with fresh web sources and citations. "
            f"Context note: {prompt[:200]}"
        ).strip()
    elif len(prior) >= 1:
        prev_user = next(
            (m["content"] for m in reversed(prior) if m.get("role") == "user"),
            None,
        )
        if prev_user and prev_user != prompt and prev_user not in prompt:
            effective = f"{prompt} (follow-up to: {prev_user[:160]})"
    append_message(sid, "user", effective)
    return sid, effective


def record_assistant_summary(session_id: str, summary: str) -> None:
    if summary.strip():
        append_message(session_id, "assistant", summary[:2000])


def reset_all_sessions_for_tests() -> None:
    """In-memory only — used by pytest autouse fixture."""
    global _sessions
    with _lock:
        _sessions = {}

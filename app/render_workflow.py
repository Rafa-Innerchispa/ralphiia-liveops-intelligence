"""Render Workflow side path — does not replace /api/analyze SSE pipeline."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from app.config import Settings

_RUNS: dict[str, dict[str, Any]] = {}
_LOCK = asyncio.Lock()


def workflow_enabled(settings: Settings) -> bool:
    import os

    flag = os.getenv("LIVEOPS_RENDER_WORKFLOW", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return getattr(settings, "liveops_render_workflow", False)


def workflow_service_name(settings: Settings) -> str:
    import os

    return (
        os.getenv("LIVEOPS_RENDER_WORKFLOW_SERVICE", "").strip()
        or getattr(settings, "liveops_render_workflow_service", "")
        or "ralphiia-liveops-investigation"
    )


async def start_workflow_run(
    settings: Settings,
    *,
    session_id: str,
    prompt: str,
) -> dict[str, Any]:
    if not workflow_enabled(settings):
        raise RuntimeError(
            "Render Workflow disabled. Set LIVEOPS_RENDER_WORKFLOW=true on the web service."
        )
    run_id = f"rw-{uuid.uuid4().hex[:12]}"
    now = time.time()
    record: dict[str, Any] = {
        "run_id": run_id,
        "session_id": session_id,
        "prompt": prompt[:2000],
        "status": "queued",
        "engine": "render_workflow",
        "service": workflow_service_name(settings),
        "created_at": now,
        "updated_at": now,
        "steps": [],
        "error": None,
        "result": None,
    }
    async with _LOCK:
        _RUNS[run_id] = record
    asyncio.create_task(_execute_run(settings, run_id))
    return {k: record[k] for k in ("run_id", "status", "engine", "service", "session_id")}


async def get_workflow_run(run_id: str) -> dict[str, Any] | None:
    async with _LOCK:
        rec = _RUNS.get(run_id)
        return dict(rec) if rec else None


async def _execute_run(settings: Settings, run_id: str) -> None:
    from workflow import investigation as wf

    steps_meta = [
        ("running", "gather_context", wf.gather_context),
        ("running", "research_live_sources", wf.research_live_sources),
        ("running", "security_review", wf.security_review),
        ("running", "compose_incident", wf.compose_incident),
    ]

    async def set_status(status: str, step: dict | None = None, **extra: Any) -> None:
        async with _LOCK:
            rec = _RUNS.get(run_id)
            if not rec:
                return
            rec["status"] = status
            rec["updated_at"] = time.time()
            if step:
                rec["steps"].append(step)
            rec.update(extra)

    await set_status("running")
    try:
        outputs: list[dict] = []
        for _, name, fn in steps_meta:
            out = await asyncio.to_thread(fn)
            outputs.append(out)
            await set_status("running", {"name": name, "ok": out.get("ok"), "note": out.get("note")})
            await asyncio.sleep(0.15)
        await set_status(
            "completed",
            result={"workflow": wf.run_liveops_investigation.__name__, "steps": outputs},
        )
    except Exception as exc:
        await set_status("failed", error=str(exc)[:400])


def reset_workflow_runs_for_tests() -> None:
    _RUNS.clear()

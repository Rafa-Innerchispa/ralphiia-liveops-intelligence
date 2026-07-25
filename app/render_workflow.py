"""Render Workflow side path — does not replace /api/analyze SSE pipeline."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any

import httpx

from app.config import Settings
from app.workflow_runner import run_liveops_investigation

_RUNS: dict[str, dict[str, Any]] = {}
_LOCK = asyncio.Lock()

RENDER_API_BASE = "https://api.render.com/v1"


def workflow_enabled(settings: Settings) -> bool:
    flag = os.getenv("LIVEOPS_RENDER_WORKFLOW", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return getattr(settings, "liveops_render_workflow", False)


def workflow_service_name(settings: Settings) -> str:
    return (
        os.getenv("LIVEOPS_RENDER_WORKFLOW_SERVICE", "").strip()
        or getattr(settings, "liveops_render_workflow_service", "")
        or "ralphiia-liveops-investigation"
    )


def _render_api_key(settings: Settings) -> str:
    return (
        os.getenv("RENDER_API_KEY", "").strip()
        or getattr(settings, "render_api_key", "").strip()
    )


def _render_task_slug(settings: Settings) -> str:
    return (
        os.getenv("RENDER_WORKFLOW_TASK_SLUG", "").strip()
        or getattr(settings, "render_workflow_task_slug", "").strip()
    )


def _remote_workflow_configured(settings: Settings) -> bool:
    return bool(_render_api_key(settings) and _render_task_slug(settings))


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
    engine = (
        "render_workflow_remote"
        if _remote_workflow_configured(settings)
        else "liveops_pipeline"
    )
    record: dict[str, Any] = {
        "run_id": run_id,
        "session_id": session_id,
        "prompt": prompt[:2000],
        "status": "queued",
        "engine": engine,
        "service": workflow_service_name(settings),
        "created_at": now,
        "updated_at": now,
        "steps": [],
        "error": None,
        "result": None,
        "render_task_run_id": None,
    }
    async with _LOCK:
        _RUNS[run_id] = record
    asyncio.create_task(_execute_run(settings, run_id))
    return {k: record[k] for k in ("run_id", "status", "engine", "service", "session_id")}


async def get_workflow_run(run_id: str) -> dict[str, Any] | None:
    async with _LOCK:
        rec = _RUNS.get(run_id)
        return dict(rec) if rec else None


async def _patch_run(run_id: str, **fields: Any) -> None:
    async with _LOCK:
        rec = _RUNS.get(run_id)
        if not rec:
            return
        rec.update(fields)
        rec["updated_at"] = time.time()


async def _append_step(run_id: str, step: dict[str, Any]) -> None:
    async with _LOCK:
        rec = _RUNS.get(run_id)
        if not rec:
            return
        rec["steps"].append(step)
        rec["updated_at"] = time.time()


async def _start_remote_task_run(
    settings: Settings,
    *,
    session_id: str,
    prompt: str,
) -> str:
    api_key = _render_api_key(settings)
    slug = _render_task_slug(settings)
    payload = {
        "task": slug,
        "input": {"prompt": prompt, "session_id": session_id},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{RENDER_API_BASE}/task-runs",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    task_run_id = data.get("id") or data.get("taskRunId")
    if not task_run_id:
        raise RuntimeError("Render task-runs response missing id")
    return str(task_run_id)


async def _poll_remote_task_run(settings: Settings, task_run_id: str) -> dict[str, Any]:
    api_key = _render_api_key(settings)
    terminal = {"succeeded", "failed", "canceled", "completed"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(120):
            resp = await client.get(
                f"{RENDER_API_BASE}/task-runs/{task_run_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            status = (data.get("status") or "").lower()
            if status in terminal:
                return data
            await asyncio.sleep(2.0)
    raise TimeoutError(f"Render task run {task_run_id} did not finish in time")


async def _execute_run(settings: Settings, run_id: str) -> None:
    async with _LOCK:
        rec = _RUNS.get(run_id)
        if not rec:
            return
        prompt = rec["prompt"]
        session_id = rec.get("session_id") or ""

    await _patch_run(run_id, status="running")

    if _remote_workflow_configured(settings):
        try:
            task_run_id = await _start_remote_task_run(
                settings, session_id=session_id, prompt=prompt
            )
            await _patch_run(run_id, render_task_run_id=task_run_id)
            remote = await _poll_remote_task_run(settings, task_run_id)
            status = (remote.get("status") or "").lower()
            if status in {"succeeded", "completed"}:
                await _patch_run(
                    run_id,
                    status="completed",
                    result={"render_task_run": remote, "engine": "remote"},
                )
            else:
                await _patch_run(
                    run_id,
                    status="failed",
                    error=f"Render task run {status}",
                    result={"render_task_run": remote},
                )
            return
        except Exception as exc:
            await _patch_run(
                run_id,
                status="failed",
                error=str(exc)[:400],
            )
            return

    try:

        async def on_step(_name: str, step_rec: dict[str, Any]) -> None:
            await _append_step(run_id, step_rec)

        result = await run_liveops_investigation(
            settings,
            session_id=session_id,
            prompt=prompt,
            run_mode="investigate",
            on_step=on_step,
        )
        await _patch_run(run_id, status="completed", result=result)
    except Exception as exc:
        await _patch_run(run_id, status="failed", error=str(exc)[:400])


def reset_workflow_runs_for_tests() -> None:
    _RUNS.clear()

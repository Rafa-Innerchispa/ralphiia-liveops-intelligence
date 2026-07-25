"""
Render Workflow task entrypoints (Act 2 long-running path).

Register in Render Dashboard → New → Workflow → Python.
Web service: LIVEOPS_RENDER_WORKFLOW=true after Workflow service exists.

Orchestrator reads LIVEOPS_WORKFLOW_PROMPT / LIVEOPS_WORKFLOW_SESSION_ID
(copy from web service env on the workflow service).
"""

from __future__ import annotations

import json
import os
from typing import Any

from app.workflow_runner import run_liveops_investigation_sync, step_record
from app.config import get_settings
from app.agents import (
    run_arbitrator,
    run_observer,
    run_research,
    run_security_reviewer,
)
from app.prompt_routing import needs_web_research, normalize_prompt, prompt_for_run_mode


def _env_prompt() -> str:
    return (os.environ.get("LIVEOPS_WORKFLOW_PROMPT", "") or "").strip()


def _env_session() -> str:
    return (os.environ.get("LIVEOPS_WORKFLOW_SESSION_ID", "") or "").strip()


def gather_context() -> dict[str, Any]:
    import asyncio

    settings = get_settings()
    step = asyncio.run(run_observer(settings))
    return step_record("gather_context", step)


def research_live_sources() -> dict[str, Any]:
    import asyncio

    async def _run() -> dict[str, Any]:
        settings = get_settings()
        prompt = normalize_prompt(_env_prompt() or None)
        observer = await run_observer(settings)
        effective = prompt_for_run_mode("investigate", prompt, observer.facts)
        web = needs_web_research(effective, run_mode="investigate")
        step = await run_research(
            settings, observer, user_prompt=effective, skip_web=not web
        )
        return step_record("research_live_sources", step)

    return asyncio.run(_run())


def security_review() -> dict[str, Any]:
    import asyncio

    async def _run() -> dict[str, Any]:
        settings = get_settings()
        prompt = normalize_prompt(_env_prompt() or None)
        observer = await run_observer(settings)
        effective = prompt_for_run_mode("investigate", prompt, observer.facts)
        web = needs_web_research(effective, run_mode="investigate")
        research = await run_research(
            settings, observer, user_prompt=effective, skip_web=not web
        )
        step = await run_security_reviewer(settings, observer, research)
        return step_record("security_review", step)

    return asyncio.run(_run())


def compose_incident() -> dict[str, Any]:
    import asyncio

    async def _run() -> dict[str, Any]:
        settings = get_settings()
        prompt = normalize_prompt(_env_prompt() or None)
        observer = await run_observer(settings)
        effective = prompt_for_run_mode("investigate", prompt, observer.facts)
        web = needs_web_research(effective, run_mode="investigate")
        research = await run_research(
            settings, observer, user_prompt=effective, skip_web=not web
        )
        reviewer = await run_security_reviewer(settings, observer, research)
        step = await run_arbitrator(settings, observer, research, reviewer)
        return step_record("compose_incident", step)

    return asyncio.run(_run())


def run_liveops_investigation(
    prompt: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Full investigate chain; API task input or LIVEOPS_WORKFLOW_* env."""
    return run_liveops_investigation_sync(
        prompt=prompt or _env_prompt(),
        session_id=session_id or _env_session(),
    )


if __name__ == "__main__":
    task = os.environ.get("RENDER_WORKFLOW_TASK", "run_liveops_investigation")
    fn = globals().get(task)
    if not callable(fn):
        raise SystemExit(f"Unknown task: {task}")
    print(json.dumps(fn(), default=str))

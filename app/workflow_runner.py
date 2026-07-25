"""Shared LiveOps investigation runner for Render Workflow (not used by SSE stream)."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from app.agents import (
    run_arbitrator,
    run_observer,
    run_research,
    run_security_reviewer,
)
from app.config import Settings, get_settings
from app.models import AgentStep
from app.prompt_routing import needs_web_research, normalize_prompt, prompt_for_run_mode

StepCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]

WORKFLOW_STEPS: tuple[tuple[str, str], ...] = (
    ("gather_context", "observer"),
    ("research_live_sources", "research"),
    ("security_review", "security_reviewer"),
    ("compose_incident", "arbitrator"),
)


def step_record(workflow_name: str, step: AgentStep) -> dict[str, Any]:
    ok = step.status in {"completed", "skipped"}
    return {
        "step": workflow_name,
        "name": workflow_name,
        "agent": step.agent.value,
        "status": step.status,
        "ok": ok,
        "summary": (step.summary or "")[:800],
        "note": (step.summary or "")[:240],
    }


async def run_liveops_investigation(
    settings: Settings,
    *,
    session_id: str,
    prompt: str,
    run_mode: str = "investigate",
    on_step: StepCallback | None = None,
) -> dict[str, Any]:
    """Same agent chain as pipeline investigate mode (without local_analyst / SSE)."""
    user_prompt = normalize_prompt(prompt or None)
    steps_out: list[dict[str, Any]] = []
    agent_steps: list[AgentStep] = []

    async def emit_step(workflow_name: str, step: AgentStep) -> None:
        rec = step_record(workflow_name, step)
        steps_out.append(rec)
        agent_steps.append(step)
        if on_step:
            maybe = on_step(workflow_name, rec)
            if asyncio.iscoroutine(maybe):
                await maybe

    observer = await run_observer(settings)
    await emit_step("gather_context", observer)

    effective = prompt_for_run_mode(run_mode, user_prompt, observer.facts)
    web = needs_web_research(effective, force=False, run_mode=run_mode)
    research = await run_research(
        settings, observer, user_prompt=effective, skip_web=not web
    )
    await emit_step("research_live_sources", research)

    reviewer = await run_security_reviewer(settings, observer, research)
    await emit_step("security_review", reviewer)

    arbitrator = await run_arbitrator(settings, observer, research, reviewer)
    await emit_step("compose_incident", arbitrator)

    youcom_mode = research.metadata.get("youcom_research_mode", "unknown")
    return {
        "workflow": "ralphiia-liveops-investigation",
        "session_id": session_id,
        "prompt": user_prompt,
        "run_mode": run_mode,
        "youcom_mode": youcom_mode,
        "dry_run": settings.dry_run,
        "steps": steps_out,
        "agent_steps": [s.model_dump() for s in agent_steps],
        "recommendation": {
            "recommended_action": arbitrator.metadata.get("recommended_action"),
            "confidence": arbitrator.metadata.get("confidence"),
            "requires_approval": True,
        },
    }


def run_liveops_investigation_sync(
    *,
    session_id: str | None = None,
    prompt: str | None = None,
    settings: Settings | None = None,
    run_mode: str = "investigate",
) -> dict[str, Any]:
    import os

    sid = (session_id or os.environ.get("LIVEOPS_WORKFLOW_SESSION_ID", "") or "").strip()
    pr = (prompt or os.environ.get("LIVEOPS_WORKFLOW_PROMPT", "") or "").strip()
    cfg = settings or get_settings()
    return asyncio.run(
        run_liveops_investigation(cfg, session_id=sid, prompt=pr, run_mode=run_mode)
    )

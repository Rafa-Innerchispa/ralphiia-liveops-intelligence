from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator

from app.local_analyst import AVAILABLE_LOCAL_MODELS
from app.prompt_routing import (
    build_operator_summary,
    needs_web_research,
    normalize_prompt,
    prompt_for_run_mode,
)
from app.agents import (
    run_arbitrator,
    run_local_analyst,
    run_observer,
    run_research,
    run_security_reviewer,
)
from app.config import Settings
from app.models import AgentName, AgentStep, Citation, FinalRecommendation, PipelineResult, SecurityVerdict

HACKATHON_TRACK = "Multi-Agent Systems"
HACKATHON_EVENT = "You.com Agentic Hackathon · SF 2026-07-24"

STORY = {
    "track": HACKATHON_TRACK,
    "event": HACKATHON_EVENT,
    "problem": (
        "En producción real, el nodo AMD (.5) tiene Evolution API con systemd activo "
        "pero health=down por línea WhatsApp bloqueada."
    ),
    "why_multi_agent": (
        "Un solo LLM diría «reinicia el servicio» sin citas. Aquí cada agente tiene un rol "
        "y los datos pasan en cadena: observación → analista local OSS → web citada (You.com) "
        "→ seguridad → veredicto → humano."
    ),
    "steps": [
        {
            "agent": "observer",
            "input": "Health RalfIA :8101 + snapshot incidente .5",
            "output": "Hechos estructurados (system_state, health, summary)",
            "api": "GET http://127.0.0.1:8101/status",
        },
        {
            "agent": "local_analyst",
            "input": "Hechos del observer + pregunta del operador",
            "output": "Hipótesis privadas (Ollama, si responde)",
            "api": "Ollama /api/chat (local OSS)",
        },
        {
            "agent": "research",
            "input": "Hechos + consulta You.com",
            "output": "URLs, informe you-research, citas",
            "api": "You.com MCP: you-search · you-contents · you-research",
        },
        {
            "agent": "security_reviewer",
            "input": "Hechos + informe + citas",
            "output": "approved/blocked + razones",
            "api": "Parasail chat/completions",
        },
        {
            "agent": "arbitrator",
            "input": "Todo lo anterior",
            "output": "recommended_action + confidence (humano Approve dry-run)",
            "api": "Parasail chat/completions",
        },
    ],
}


def _resolve_mode(settings: Settings) -> str:
    mode = settings.data_mode
    if mode == "auto":
        mode = "live" if settings.resolved_youcom_key() else "fixture"
    return mode


def _step_by_name(steps: list[AgentStep], name: AgentName) -> AgentStep:
    for s in steps:
        if s.agent == name:
            return s
    raise ValueError(f"missing step {name}")


def _data_sources(steps: list[AgentStep]) -> dict[str, str]:
    observer = _step_by_name(steps, AgentName.observer)
    research = _step_by_name(steps, AgentName.research)
    obs_src = observer.metadata.get("source", "unknown")
    obs_label = "Live · RalfIA :8101" if obs_src == "ralfia_health_readonly" else (
        "Fallback fixture" if "fixture" in str(obs_src) else str(obs_src)
    )
    res_mode = research.metadata.get("youcom_research_mode", "unknown")
    if res_mode == "skipped_status_only":
        res_label = "Skipped (status-only prompt)"
    elif "fixture" in str(res_mode) or res_mode == "unknown":
        res_label = f"You.com · {res_mode}"
    else:
        res_label = f"You.com MCP · {res_mode}"
    local = _step_by_name(steps, AgentName.local_analyst)
    if local.status == "skipped":
        local_label = "Unavailable (Ollama probe failed)"
    elif local.status == "completed":
        local_label = f"Ollama · {local.metadata.get('model')}"
    else:
        local_label = local.status
    return {
        "observer": obs_label,
        "local_analyst": local_label,
        "research": res_label,
    }


def _providers_used(settings: Settings, steps: list[AgentStep]) -> list[dict]:
    observer = _step_by_name(steps, AgentName.observer)
    local = _step_by_name(steps, AgentName.local_analyst)
    research = _step_by_name(steps, AgentName.research)
    reviewer = _step_by_name(steps, AgentName.security_reviewer)
    arbitrator = _step_by_name(steps, AgentName.arbitrator)
    out: list[dict] = [
        {
            "role": "Observer",
            "provider": "RalfIA MCP",
            "detail": observer.metadata.get("source", "unknown"),
            "narrative": "Live operational truth",
        },
    ]
    if local.status == "completed":
        out.append(
            {
                "role": "Local Analyst",
                "provider": "Ollama",
                "detail": local.metadata.get("model"),
                "model": local.metadata.get("model"),
                "narrative": "Private / sovereign reasoning",
            }
        )
    else:
        out.append(
            {
                "role": "Local Analyst",
                "provider": "Ollama",
                "detail": "unavailable",
                "narrative": "Private OSS (not invoked)",
            }
        )
    if research.status == "skipped":
        out.append(
            {
                "role": "You.com Research",
                "provider": "—",
                "detail": "skipped (read-only routing)",
                "narrative": "Web intel with citations",
            }
        )
    else:
        out.append(
            {
                "role": "You.com Research",
                "provider": "You.com MCP",
                "detail": research.metadata.get("youcom_research_mode", ""),
                "narrative": "Web intel with citations",
            }
        )
        out.append(
            {
                "role": "Security Reviewer",
                "provider": "Parasail" if settings.resolved_parasail_key() else "Rules engine",
                "detail": reviewer.metadata.get("parasail_mode", "rules"),
                "model": settings.parasail_model if settings.resolved_parasail_key() else None,
                "narrative": "External inference / review",
            }
        )
    if reviewer.metadata.get("parasail_mode") == "skipped_no_web_research":
        out[-1]["provider"] = "Rules engine"
        out[-1]["detail"] = "skipped (status-only — Parasail not called)"
    out.append(
        {
            "role": "Arbitrator",
            "provider": "Parasail" if settings.resolved_parasail_key() else "Rules engine",
            "detail": arbitrator.metadata.get("parasail_mode", "rules"),
            "model": settings.parasail_model if settings.resolved_parasail_key() else None,
            "narrative": "External review / arbitration",
        }
    )
    out.append(
        {
            "role": "Human",
            "provider": "Operator",
            "detail": "Approve / Reject / Research deeper",
            "narrative": "Final control",
        }
    )
    return out


def _models_used(settings: Settings, steps: list[AgentStep]) -> list[dict]:
    used: list[dict] = []
    local = _step_by_name(steps, AgentName.local_analyst)
    if local.status == "completed" and local.metadata.get("model"):
        used.append(
            {
                "role": "Local Analyst",
                "provider": "Ollama",
                "model": local.metadata.get("model"),
                "latency_ms": local.metadata.get("latency_ms"),
            }
        )
    research = _step_by_name(steps, AgentName.research)
    if research.status == "completed":
        used.append(
            {
                "role": "You.com Research",
                "provider": "You.com MCP",
                "model": "you-search/contents/research",
                "modes": {
                    "search": research.metadata.get("youcom_search_mode"),
                    "research": research.metadata.get("youcom_research_mode"),
                },
            }
        )
    if settings.resolved_parasail_key():
        used.append(
            {
                "role": "Security + Arbitrator",
                "provider": "Parasail",
                "model": settings.parasail_model,
            }
        )
    used.append(
        {
            "role": "Observer",
            "provider": "RalfIA",
            "model": "health probe :8101",
        }
    )
    return used


def _live_nodes_from_observer(observer: AgentStep) -> dict:
    src = observer.metadata.get("source", "unknown")
    kind = "live" if src == "ralfia_health_readonly" else "fixture"
    return {
        "node_amd_5": {
            "label": "AMD node (.5) · Evolution API",
            "system_state": "active",
            "health": "down",
            "source": kind,
            "note": "Incident metadata from fixture; health probe from RalfIA when live.",
        },
        "ralfia_gateway": {
            "label": "RalfIA gateway",
            "probe": "GET :8101/status",
            "source": kind,
        },
    }


def _assemble_result(
    settings: Settings,
    cid: str,
    session_id: str,
    steps: list[AgentStep],
    elapsed: float,
    user_prompt: str,
) -> PipelineResult:
    observer = _step_by_name(steps, AgentName.observer)
    local = _step_by_name(steps, AgentName.local_analyst)
    research = _step_by_name(steps, AgentName.research)
    reviewer = _step_by_name(steps, AgentName.security_reviewer)
    arbitrator = _step_by_name(steps, AgentName.arbitrator)
    security = SecurityVerdict.model_validate(reviewer.metadata["security"])
    local_hyps = local.hypotheses if local.status == "completed" else []
    recommendation = FinalRecommendation(
        observed_facts=observer.facts,
        hypotheses=list(dict.fromkeys(local_hyps + observer.hypotheses + research.hypotheses)),
        confidence=float(arbitrator.metadata.get("confidence", 0.5)),
        citations=[Citation.model_validate(c) for c in arbitrator.citations],
        recommended_action=arbitrator.metadata["recommended_action"],
        risk_level=arbitrator.metadata.get("risk_level", "medium"),
        requires_approval=True,
        dry_run=True,
        security=security,
    )
    youcom_mode = research.metadata.get("youcom_research_mode", "unknown")
    local_latency = local.metadata.get("latency_ms")
    metrics = {
        "citation_coverage": len(recommendation.citations),
        "source_freshness": "month_filter_search"
        if youcom_mode != "skipped_status_only"
        else "ralfia_live_status",
        "unsafe_action_rejection": not security.approved,
        "time_to_recommendation_sec": round(elapsed, 3),
        "local_analyst_latency_ms": local_latency,
        "agreement_conflict_resolution": "arbitrator_unanimous_with_reviewer"
        if security.approved
        else "reviewer_blocked",
        "parasail_configured": settings.resolved_parasail_key() != "",
        "parasail_model": settings.parasail_model,
        "user_prompt_chars": len(user_prompt),
        "web_research_ran": youcom_mode != "skipped_status_only",
        "session_id": session_id,
    }
    data_sources = _data_sources(steps)
    local_preview = ""
    if local.status == "completed":
        local_preview = str(local.metadata.get("preview") or local.summary or "")
    operator_summary = build_operator_summary(
        user_prompt,
        recommendation.recommended_action,
        recommendation.confidence,
        data_sources=data_sources,
        local_preview=local_preview,
    )
    metrics["api_proof"] = {
        "ralfia": data_sources.get("observer"),
        "ollama": data_sources.get("local_analyst"),
        "youcom": data_sources.get("research"),
        "parasail_security": reviewer.metadata.get("parasail_mode"),
        "parasail_arbitrator": arbitrator.metadata.get("parasail_mode"),
    }
    return PipelineResult(
        correlation_id=cid,
        session_id=session_id,
        incident_id="evolution-amd-health-down",
        mode=_resolve_mode(settings),
        youcom_mode=youcom_mode,
        user_prompt=user_prompt,
        operator_summary=operator_summary,
        providers_used=_providers_used(settings, steps),
        models_used=_models_used(settings, steps),
        models_available=list(AVAILABLE_LOCAL_MODELS),
        data_sources=_data_sources(steps),
        live_nodes=_live_nodes_from_observer(observer),
        steps=steps,
        recommendation=recommendation,
        metrics=metrics,
    )


async def run_pipeline(
    settings: Settings,
    correlation_id: str | None = None,
    user_prompt: str | None = None,
    session_id: str = "",
    *,
    research_deeper: bool = False,
    run_mode: str = "auto",
) -> PipelineResult:
    t0 = time.perf_counter()
    cid = correlation_id or "youcom-hackathon-liveops-20260724"
    prompt = normalize_prompt(user_prompt)
    observer = await run_observer(settings)
    effective = prompt_for_run_mode(run_mode, prompt, observer.facts)
    web = needs_web_research(effective, force=research_deeper, run_mode=run_mode)
    local = await run_local_analyst(settings, observer, user_prompt=effective)
    research = await run_research(
        settings, observer, user_prompt=effective, skip_web=not web
    )
    reviewer = await run_security_reviewer(settings, observer, research)
    arbitrator = await run_arbitrator(settings, observer, research, reviewer)
    return _assemble_result(
        settings,
        cid,
        session_id,
        [observer, local, research, reviewer, arbitrator],
        time.perf_counter() - t0,
        effective,
    )


async def stream_pipeline(
    settings: Settings,
    correlation_id: str | None = None,
    user_prompt: str | None = None,
    session_id: str = "",
    *,
    research_deeper: bool = False,
    run_mode: str = "auto",
) -> AsyncIterator[str]:
    """Server-Sent Events — data flow events + agent steps + final result."""
    t0 = time.perf_counter()
    cid = correlation_id or "youcom-hackathon-liveops-20260724"
    prompt = normalize_prompt(user_prompt)
    pending: list[str] = []

    def pack(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"

    async def emit(flow: dict) -> None:
        pending.append(pack("data_flow", flow))

    def drain() -> list[str]:
        out = list(pending)
        pending.clear()
        return out

    yield pack(
        "start",
        {
            "correlation_id": cid,
            "session_id": session_id,
            "incident_id": "evolution-amd-health-down",
            "track": HACKATHON_TRACK,
            "event": HACKATHON_EVENT,
            "story": STORY,
            "user_prompt": prompt,
            "web_research": None,
            "run_mode": run_mode,
            "phase": "observer",
            "research_deeper": research_deeper,
        },
    )

    steps: list[AgentStep] = []

    yield pack("agent_start", {"agent": "observer", "detail": "RalfIA :8101 read-only"})
    for chunk in drain():
        yield chunk
    observer = await run_observer(settings, emit=emit)
    for chunk in drain():
        yield chunk
    steps.append(observer)
    yield pack("agent_done", {"step": observer.model_dump()})

    effective = prompt_for_run_mode(run_mode, prompt, observer.facts)
    web = needs_web_research(effective, force=research_deeper, run_mode=run_mode)
    yield pack(
        "plan",
        {
            "correlation_id": cid,
            "user_prompt": effective,
            "web_research": web,
            "run_mode": run_mode,
        },
    )

    yield pack("agent_start", {"agent": "local_analyst", "detail": "Ollama local OSS"})
    for chunk in drain():
        yield chunk
    local = await run_local_analyst(settings, observer, emit=emit, user_prompt=effective)
    for chunk in drain():
        yield chunk
    steps.append(local)
    yield pack("agent_done", {"step": local.model_dump()})

    yield pack("agent_start", {"agent": "research", "detail": "You.com MCP"})
    for chunk in drain():
        yield chunk
    research = await run_research(
        settings, observer, emit=emit, user_prompt=effective, skip_web=not web
    )
    for chunk in drain():
        yield chunk
    steps.append(research)
    yield pack("agent_done", {"step": research.model_dump()})

    yield pack("agent_start", {"agent": "security_reviewer", "detail": "Parasail"})
    for chunk in drain():
        yield chunk
    reviewer = await run_security_reviewer(settings, observer, research, emit=emit)
    for chunk in drain():
        yield chunk
    steps.append(reviewer)
    yield pack("agent_done", {"step": reviewer.model_dump()})

    yield pack("agent_start", {"agent": "arbitrator", "detail": "Parasail + human checkpoint"})
    for chunk in drain():
        yield chunk
    arbitrator = await run_arbitrator(settings, observer, research, reviewer, emit=emit)
    for chunk in drain():
        yield chunk
    steps.append(arbitrator)
    yield pack("agent_done", {"step": arbitrator.model_dump()})

    result = _assemble_result(
        settings, cid, session_id, steps, time.perf_counter() - t0, effective
    )
    yield pack(
        "data_flow",
        {
            "agent": "human",
            "kind": "checkpoint",
            "title": "Human approval",
            "explain": (
                "Approve/Reject only records checkpoint — no production mutations (dry-run)."
            ),
            "payload": {"requires_approval": True, "dry_run": True},
        },
    )
    yield pack("complete", {"result": result.model_dump()})


async def run_baseline_single_agent(settings: Settings) -> dict:
    """Single-agent baseline: observer only + generic hypothesis (no You.com)."""
    observer = await run_observer(settings)
    return {
        "agent_count": 1,
        "facts": len(observer.facts),
        "citations": 0,
        "confidence": 0.35,
        "recommended_action": "Restart Evolution service",
        "unsafe": True,
    }

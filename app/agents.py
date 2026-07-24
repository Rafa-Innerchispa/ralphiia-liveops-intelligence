from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from app.models import AgentName, AgentStep, Citation, SecurityVerdict
from app.incident_run import (
    derive_incident_id,
    hypotheses_for_run,
    rules_fallback_recommendation,
)
from app.provenance import (
    build_sanitized_research_query,
    build_sanitized_search_query,
    canonical_citations,
    observer_facts_from_snap,
    sanitize_operator_prompt,
)
from app.prompt_routing import INVESTIGATE_DEFAULT_PROMPT, STATUS_DEFAULT_PROMPT
from app.ralfia_client import fetch_live_status
from app.ops_brief import (
    build_status_only_recommendation,
    format_service_status_block,
    service_matrix_from_snapshot,
)
from app.youcom_client import YouComClient
from app.config import Settings
from app.local_analyst import resolve_local_analyst_model, run_local_inference
from app.parasail_client import ParasailClient

DataEmitter = Callable[[dict], Awaitable[None]] | None


async def _flow(emit: DataEmitter, payload: dict) -> None:
    if emit:
        await emit(payload)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_observer(settings: Settings, emit: DataEmitter = None) -> AgentStep:
    started = _now()
    await _flow(
        emit,
        {
            "agent": "observer",
            "kind": "request",
            "title": "Paso 1 · Leer incidente",
            "explain": (
                "El agente Observer no toca producción: hace GET al health de RalfIA "
                "(:8101/status) y carga el snapshot del nodo AMD (.5)."
            ),
            "transport": f"HTTP GET → {settings.ralfia_status_endpoint()}",
        },
    )
    snap = await fetch_live_status(settings)
    matrix = service_matrix_from_snapshot(snap)
    source = snap.get("source") or ""
    live_ok = source in ("ralfia_health_readonly", "ralfia_bridge_live")
    response_title = (
        "Live snapshot received"
        if live_ok
        else "Bridge reached, but live evidence unavailable"
    )
    await _flow(
        emit,
        {
            "agent": "observer",
            "kind": "response",
            "title": response_title,
            "explain": (
                f"Source: {snap.get('source_label')}. "
                + (
                    f"{snap.get('service')} node {snap.get('node_label')}: "
                    f"systemd={snap.get('system_state')}, health={snap.get('health')}."
                    if live_ok
                    else "No validated live service matrix — demo context kept separate."
                )
            ),
            "payload": {
                "source": snap.get("source"),
                "health": snap.get("health"),
                "system_state": snap.get("system_state"),
                "services_down": matrix["down"],
                "services_degraded": matrix["degraded"],
                "live_validated": live_ok,
            },
        },
    )
    source_label = snap.get("source_label") or snap.get("source", "unknown")
    observed, demo = observer_facts_from_snap(snap, matrix)
    facts = observed + demo
    hypotheses = hypotheses_for_run(snap, matrix)
    incident_id = derive_incident_id(snap, matrix)
    obs_status = "failed" if source == "live_unavailable" else "completed"
    return AgentStep(
        agent=AgentName.observer,
        status=obs_status,
        started_at=started,
        finished_at=_now(),
        summary=(
            "Live probe validated."
            if live_ok
            else "Live probe unavailable — demo context labeled separately."
        ),
        facts=facts,
        hypotheses=hypotheses,
        metadata={
            "evidence_ref": snap.get("evidence_ref"),
            "source": snap.get("source"),
            "dry_run": True,
            "demo_context": demo,
            "observed_facts": observed,
            "incident_id": incident_id,
            "snap": {
                "node_label": snap.get("node_label"),
                "service": snap.get("service"),
                "system_state": snap.get("system_state"),
                "health": snap.get("health"),
                "source": snap.get("source"),
                "source_label": source_label,
                "summary": snap.get("summary"),
                "ralfia_status": snap.get("ralfia_status"),
                "checked_at": snap.get("checked_at"),
            },
        },
    )


async def run_local_analyst(
    settings: Settings,
    observer: AgentStep,
    emit: DataEmitter = None,
    user_prompt: str | None = None,
) -> AgentStep:
    started = _now()
    probe = await resolve_local_analyst_model(settings)
    model = probe.get("model")
    if not model:
        await _flow(
            emit,
            {
                "agent": "local_analyst",
                "kind": "checkpoint",
                "title": "Local Analyst unavailable",
                "explain": (
                    "Ollama probe did not get a response from preferred local models. "
                    "Pipeline continues with Observer facts only — not faked."
                ),
                "payload": {"probe": "failed", "endpoint": probe.get("endpoint")},
            },
        )
        return AgentStep(
            agent=AgentName.local_analyst,
            status="skipped",
            started_at=started,
            finished_at=_now(),
            summary="Local OSS analyst skipped (Ollama unavailable).",
            facts=["Local Analyst not invoked — probe failed."],
            hypotheses=observer.hypotheses[:2],
            metadata={
                "provider": "Ollama",
                "model": None,
                "latency_ms": None,
                "available": False,
            },
        )

    await _flow(
        emit,
        {
            "agent": "local_analyst",
            "kind": "request",
            "title": "Paso 1b · Local Analyst (Ollama)",
            "explain": (
                "Private on-prem reasoning on Observer facts — sovereign/low-cost "
                "hypothesis before web research."
            ),
            "transport": f"POST {probe.get('endpoint')}/api/chat",
            "payload": {"model": model, "user_prompt": user_prompt or ""},
        },
    )
    system = (
        "You are Local Analyst in a LiveOps command center. "
        "Use only the facts given. Label outputs as model hypotheses, not live telemetry. "
        "Be concise (3-5 bullets). No production actions."
    )
    user = (
        f"Operator question: {user_prompt or 'incident triage'}\n"
        f"Observer facts:\n" + "\n".join(f"- {f}" for f in observer.facts[:8])
    )
    text, latency_ms = await run_local_inference(model, system, user)
    await _flow(
        emit,
        {
            "agent": "local_analyst",
            "kind": "response",
            "title": f"Local Analyst · {model}",
            "explain": text[:600],
            "payload": {"model": model, "latency_ms": round(latency_ms, 1)},
        },
    )
    hypotheses = [
        line.strip("-• ").strip()
        for line in text.split("\n")
        if line.strip() and len(line.strip()) > 8
    ][:5]
    if not hypotheses:
        hypotheses = ["Local model synthesis pending human review."]
    return AgentStep(
        agent=AgentName.local_analyst,
        status="completed",
        started_at=started,
        finished_at=_now(),
        summary="Local OSS reasoning on observed infrastructure facts.",
        facts=[f"Local Analyst ({model}) latency={round(latency_ms, 0)}ms."],
        hypotheses=hypotheses,
        metadata={
            "provider": "Ollama",
            "model": model,
            "latency_ms": round(latency_ms, 1),
            "preview": text[:900],
            "available": True,
        },
    )


async def run_research(
    settings: Settings,
    observer: AgentStep,
    emit: DataEmitter = None,
    user_prompt: str | None = None,
    skip_web: bool = False,
) -> AgentStep:
    started = _now()
    if skip_web:
        await _flow(
            emit,
            {
                "agent": "research",
                "kind": "checkpoint",
                "title": "Research skipped (read-only status question)",
                "explain": (
                    "Your prompt looks like live infrastructure status only. "
                    "Observer + RalfIA :8101 already answered; You.com not invoked."
                ),
                "payload": {"user_prompt": user_prompt or ""},
            },
        )
        return AgentStep(
            agent=AgentName.research,
            status="skipped",
            started_at=started,
            finished_at=_now(),
            summary="Status-only path — no external web research.",
            facts=["You.com MCP not called (read-only status routing)."],
            hypotheses=observer.hypotheses[:2],
            citations=[],
            metadata={
                "youcom_search_mode": "skipped_status_only",
                "youcom_research_mode": "skipped_status_only",
                "youcom_contents_mode": "skipped",
                "research_preview": "",
                "user_prompt": user_prompt or "",
            },
        )

    client = YouComClient(settings)
    observed = observer.metadata.get("observed_facts") or observer.facts[:8]
    demo = observer.metadata.get("demo_context") or []
    search_query = build_sanitized_search_query(user_prompt or "", observed, demo)
    query = build_sanitized_research_query(user_prompt or "", observed, demo)
    await _flow(
        emit,
        {
            "agent": "research",
            "kind": "request",
            "title": "Paso 2a · You.com Search (MCP)",
            "explain": (
                "El agente Research envía tu consulta a You.com MCP (`you-search`) "
                "para obtener fuentes web recientes sobre Evolution + health down."
            ),
            "transport": "MCP you-search → api.you.com/mcp",
            "payload": {"query": search_query, "user_prompt": user_prompt or ""},
        },
    )
    search_hits, search_mode = await client.search(search_query)
    if search_mode.endswith("_live") and search_hits:
        first = search_hits[0]
        sn = str(first.get("snippet") or "")
        if "422" in sn or "Failed to perform search" in sn:
            search_hits = []
            search_mode = "mcp_search_error"
    if search_mode == "mcp_search_error":
        search_title = "Search failed (422) — continuing with you-research only"
        search_explain = (
            "Malformed or rejected you-search response; research MCP may still succeed."
        )
    elif search_hits:
        search_title = f"Search OK · {len(search_hits)} resultados"
        search_explain = f"Modo {search_mode}. Estos URLs alimentan Contents y Research."
    else:
        search_title = f"Search · 0 results ({search_mode})"
        search_explain = f"Modo {search_mode}. Contents skipped if no URL."
    await _flow(
        emit,
        {
            "agent": "research",
            "kind": "response",
            "title": search_title,
            "explain": search_explain,
            "payload": {
                "mode": search_mode,
                "hits": [
                    {"title": h.get("title"), "url": h.get("url")}
                    for h in search_hits[:5]
                ],
            },
        },
    )
    research_report, research_cites, research_mode = "", [], "pending"
    contents_snippet = ""
    contents_mode = "skipped"
    if search_hits and search_hits[0].get("url"):
        first_url = search_hits[0]["url"]
        await _flow(
            emit,
            {
                "agent": "research",
                "kind": "request",
                "title": "Paso 2b · You.com Contents (MCP)",
                "explain": "Extraemos texto de la primera fuente para contexto citado.",
                "transport": "MCP you-contents",
                "payload": {"url": first_url},
            },
        )
        contents_snippet, contents_mode = await client.contents(first_url)
        await _flow(
            emit,
            {
                "agent": "research",
                "kind": "response",
                "title": "Contents recibido",
                "explain": f"Modo {contents_mode}. Fragmento usado en el informe.",
                "payload": {"mode": contents_mode, "excerpt": contents_snippet[:500]},
            },
        )
    await _flow(
        emit,
        {
            "agent": "research",
            "kind": "request",
            "title": "Paso 2c · You.com Research (MCP)",
            "explain": (
                "Informe largo con citas (`you-research`) — suele tardar 20–40 s; "
                "aquí está el corazón del track Multi-Agent + You.com."
            ),
            "transport": "MCP you-research",
            "payload": {"query": query},
        },
    )
    research_report, research_cites, research_mode = await client.research(query)
    pre_cites = canonical_citations(
        [
            Citation(
                title=c.get("title") or "Research source",
                url=c.get("url") or "",
                snippet=str(c.get("snippet") or "")[:500],
            )
            for c in research_cites
        ]
    )
    await _flow(
        emit,
        {
            "agent": "research",
            "kind": "response",
            "title": f"Research OK · {len(pre_cites)} citas",
            "explain": f"Modo {research_mode}. Informe sintetizado para Security y Arbitrator.",
            "payload": {
                "mode": research_mode,
                "preview": research_report[:900],
                "citations": [
                    {"title": c.get("title"), "url": c.get("url")}
                    for c in research_cites[:6]
                ],
            },
        },
    )

    citations = canonical_citations(
        [
            Citation(
                title=hit.get("title") or "Source",
                url=hit.get("url") or "",
                snippet=str(hit.get("snippet") or "")[:500],
            )
            for hit in search_hits
        ]
        + [
            Citation(
                title=hit.get("title") or "Research source",
                url=hit.get("url") or "",
                snippet=str(hit.get("snippet") or "")[:500],
            )
            for hit in research_cites
        ]
    )

    research_status = "completed"
    if search_mode == "mcp_search_error" and research_mode == "mcp_live":
        research_status = "partial"

    preview = research_report[:1200].strip()
    facts = [
        f"You.com search mode: {search_mode}; hits={len(search_hits)}.",
        f"You.com research mode: {research_mode}; citations={len(citations)}.",
        preview[:320] + ("…" if len(preview) > 320 else ""),
    ]
    if contents_snippet:
        facts.append(f"Contents excerpt ({contents_mode}): {contents_snippet[:400]}")

    snap_meta = observer.metadata.get("snap") or {}
    matrix = service_matrix_from_snapshot(snap_meta) if snap_meta else {"up": [], "down": [], "degraded": []}
    hypotheses = hypotheses_for_run(snap_meta, matrix)

    return AgentStep(
        agent=AgentName.research,
        status=research_status,
        started_at=started,
        finished_at=_now(),
        summary="Web investigation with Search + Research (+ Contents when available).",
        facts=facts,
        hypotheses=hypotheses,
        citations=citations,
        metadata={
            "youcom_search_mode": search_mode,
            "youcom_research_mode": research_mode,
            "youcom_contents_mode": contents_mode,
            "research_preview": preview,
            "search_titles": [h.get("title") for h in search_hits[:5]],
            "user_prompt": user_prompt or "",
        },
    )


def _security_rules(observer: AgentStep, research: AgentStep) -> SecurityVerdict:
    has_citations = len(research.citations) >= 1
    status_only = research.metadata.get("youcom_research_mode") == "skipped_status_only"
    approved = True
    reasons = [
        "Read-only investigation and monitoring are approved (dry-run).",
        "Restart, recover, delete, and production config changes remain blocked "
        "until human operator verifies impact.",
    ]
    if not has_citations and not status_only:
        approved = False
        reasons = [
            "Need cited web research before operational recommendations.",
        ]
    return SecurityVerdict(
        approved=approved,
        blocked_actions=["restart", "recover", "delete", "production_config_change"],
        reasons=reasons,
    )


def _parasail_suggests_destructive(parsed: dict) -> bool:
    blob = " ".join(
        str(x).lower()
        for x in (parsed.get("reasons") or []) + (parsed.get("blocked_actions") or [])
    )
    return any(
        w in blob
        for w in ("restart", "recover", "delete", "production change", "config change")
    )


async def run_security_reviewer(
    settings: Settings,
    observer: AgentStep,
    research: AgentStep,
    emit: DataEmitter = None,
) -> AgentStep:
    started = _now()
    llm = ParasailClient(settings)
    verdict = _security_rules(observer, research)
    llm_mode = "rules"
    status_only = research.status == "skipped"
    if status_only:
        await _flow(
            emit,
            {
                "agent": "security_reviewer",
                "kind": "checkpoint",
                "title": "Security · rules only",
                "explain": "You.com was not used — Parasail skipped; local rules enforce dry-run.",
                "transport": "rules engine (no Parasail HTTP)",
                "payload": {"approved": verdict.approved},
            },
        )
        llm_mode = "skipped_no_web_research"
    else:
        await _flow(
            emit,
            {
                "agent": "security_reviewer",
                "kind": "request",
                "title": "Security Reviewer · Parasail HTTP",
                "explain": (
                    "POST chat/completions with Observer facts + You.com citations."
                ),
                "transport": f"POST {settings.parasail_base_url}/chat/completions",
                "payload": {
                    "model": settings.parasail_model,
                    "citations_in": len(research.citations),
                },
            },
        )
        if llm.configured():
            cite_lines = [
                f"- {c.title} ({c.url})" for c in research.citations[:8]
            ]
            user = (
                "Incident facts:\n"
                + "\n".join(f"- {f}" for f in observer.facts)
                + "\nResearch:\n"
                + "\n".join(f"- {f}" for f in research.facts[:6])
                + "\nCitations:\n"
                + "\n".join(cite_lines)
                + "\nReturn JSON: approved (bool), blocked_actions (array), reasons (array)."
            )
            system = (
                "You are Security Reviewer in a LiveOps multi-agent system (dry-run only). "
                "Approve read-only investigation (logs, metrics, categorization, tracing). "
                "Set approved=false ONLY if the recommendation includes restart, recover, delete, "
                "or production config changes. Do NOT reject read-only investigation because of "
                "error backlogs or degraded signals alone — those are watch items, not proof of outage. "
                "Output JSON only: approved, blocked_actions, reasons."
            )
            try:
                text, llm_mode = await llm.chat(system, user, max_tokens=500)
                parsed = ParasailClient.parse_json_block(text)
                if "approved" in parsed:
                    llm_verdict = SecurityVerdict(
                        approved=bool(parsed.get("approved")),
                        blocked_actions=list(parsed.get("blocked_actions") or []),
                        reasons=list(parsed.get("reasons") or ["Parasail review"]),
                    )
                    if _parasail_suggests_destructive(parsed) and llm_verdict.approved is False:
                        verdict = llm_verdict
                    else:
                        verdict.approved = True
                        for r in llm_verdict.reasons[:2]:
                            if r and r not in verdict.reasons:
                                verdict.reasons.append(f"Watch (not blocking read-only): {r[:200]}")
            except Exception:
                llm_mode = "rules_fallback"
        await _flow(
            emit,
            {
                "agent": "security_reviewer",
                "kind": "response",
                "title": f"Security response · approved={verdict.approved}",
                "explain": f"Parasail mode={llm_mode}",
                "transport": f"POST {settings.parasail_base_url}/chat/completions",
                "payload": {
                    "parasail_mode": llm_mode,
                    "security": verdict.model_dump(),
                },
            },
        )

    rev_status = "completed" if verdict.approved else "rejected"
    return AgentStep(
        agent=AgentName.security_reviewer,
        status=rev_status,
        started_at=started,
        finished_at=_now(),
        summary="Security review complete.",
        facts=[f"Security approved={verdict.approved}"],
        hypotheses=[],
        metadata={"security": verdict.model_dump(), "parasail_mode": llm_mode},
    )


def run_security_reviewer_rules_only(
    observer: AgentStep, research: AgentStep
) -> AgentStep:
    """Sync rules-only path for tests."""
    started = _now()
    verdict = _security_rules(observer, research)
    return AgentStep(
        agent=AgentName.security_reviewer,
        status="completed",
        started_at=started,
        finished_at=_now(),
        summary="Security review complete.",
        facts=[f"Security approved={verdict.approved}"],
        hypotheses=[],
        metadata={"security": verdict.model_dump(), "parasail_mode": "rules"},
    )


async def run_arbitrator(
    settings: Settings,
    observer: AgentStep,
    research: AgentStep,
    reviewer: AgentStep,
    emit: DataEmitter = None,
) -> AgentStep:
    started = _now()
    security = SecurityVerdict.model_validate(reviewer.metadata["security"])
    snap_meta = observer.metadata.get("snap") or {}
    matrix = service_matrix_from_snapshot(snap_meta) if snap_meta else {
        "up": [],
        "down": [],
        "degraded": [],
    }
    cites_preview = canonical_citations(research.citations[:12])
    recommendation = rules_fallback_recommendation(snap_meta, cites_preview, security)
    confidence = 0.72 if cites_preview else 0.45
    if security.approved:
        confidence = min(0.9, confidence + 0.08)
    risk_level = "low" if not matrix["down"] else "medium"
    llm_mode = "rules"
    llm = ParasailClient(settings)
    status_only = research.status == "skipped"
    if status_only:
        confidence = 0.82
        snap = observer.metadata.get("snap") or {}
        if snap:
            full_snap = dict(snap)
            full_snap["source_label"] = (
                snap.get("source_label")
                or observer.metadata.get("source")
                or "Live · RalfIA :8101"
            )
            recommendation = build_status_only_recommendation(full_snap, observer.facts)
        else:
            recommendation = build_status_only_recommendation(
                {
                    "node_label": "unknown",
                    "service": "Evolution API",
                    "system_state": "unknown",
                    "health": "unknown",
                    "source_label": "Live probe",
                    "summary": observer.facts[0] if observer.facts else "",
                    "ralfia_status": {},
                    "source": observer.metadata.get("source"),
                },
                observer.facts,
            )
        llm_mode = "skipped_no_web_research"
        await _flow(
            emit,
            {
                "agent": "arbitrator",
                "kind": "checkpoint",
                "title": "Arbitrator · rules (status-only)",
                "explain": "Parasail skipped — answer synthesized from Observer + Local Analyst only.",
                "transport": "rules engine (no Parasail HTTP)",
                "payload": {"recommended_action": recommendation[:200]},
            },
        )
    else:
        await _flow(
            emit,
            {
                "agent": "arbitrator",
                "kind": "request",
                "title": "Arbitrator · Parasail HTTP",
                "explain": "Merge You.com research + security into final recommendation.",
                "transport": f"POST {settings.parasail_base_url}/chat/completions",
            },
        )
        if llm.configured():
            snap = observer.metadata.get("snap") or {}
            full_snap = dict(snap)
            status_block = format_service_status_block(full_snap)
            cite_lines = [
                f"[{i}] {c.title} — {c.url}"
                for i, c in enumerate(cites_preview[:6], start=1)
            ]
            user = (
                f"Operator question context: {observer.metadata.get('user_prompt') or ''}\n"
                f"Live status:\n{status_block}\n\n"
                f"Observer facts:\n"
                + "\n".join(f"- {f}" for f in (observer.metadata.get("observed_facts") or observer.facts)[:8])
                + "\n\nWrite a structured English answer with sections: "
                "What is healthy, What needs investigation, Recommended read-only next steps "
                "(each step with [n] citation index when applicable), Security review. "
                "Do NOT mention blocked WhatsApp lines unless health=down in snapshot. "
                "Do NOT claim capacity exhaustion from error counts alone.\n"
                f"Citations:\n" + "\n".join(cite_lines)
                + f"\nSecurity approved={security.approved}\n"
                "Return JSON: recommended_action (full markdown text), confidence, risk_level."
            )
            system = (
                "You are Arbitrator for read-only LiveOps. Never recommend restart/recover/delete. "
                "Use only live snapshot facts; separate facts from hypotheses."
            )
            try:
                text, llm_mode = await llm.chat(system, user, max_tokens=700)
                parsed = ParasailClient.parse_json_block(text)
                if parsed.get("recommended_action"):
                    recommendation = str(parsed["recommended_action"])
                    if "blocked line" in recommendation.lower() and snap.get("health") != "down":
                        recommendation = rules_fallback_recommendation(
                            snap_meta, cites_preview, security
                        )
                if parsed.get("confidence") is not None:
                    confidence = float(parsed["confidence"])
                if parsed.get("risk_level"):
                    risk_level = str(parsed["risk_level"])
            except Exception:
                llm_mode = "rules_fallback"
        if not security.approved:
            recommendation = (
                "Security review did NOT approve proposed remediation.\n"
                f"Reasons: {'; '.join(security.reasons)}\n\n"
                f"{recommendation}"
            )
        await _flow(
            emit,
            {
                "agent": "arbitrator",
                "kind": "response",
                "title": "Arbitrator response",
                "explain": recommendation[:240],
                "transport": f"POST {settings.parasail_base_url}/chat/completions",
                "payload": {
                    "parasail_mode": llm_mode,
                    "confidence": confidence,
                    "risk_level": risk_level,
                },
            },
        )

    cites = canonical_citations(research.citations[:12])

    return AgentStep(
        agent=AgentName.arbitrator,
        status="completed",
        started_at=started,
        finished_at=_now(),
        summary=recommendation,
        facts=observer.metadata.get("observed_facts") or observer.facts[:5],
        hypotheses=hypotheses_for_run(
            observer.metadata.get("snap") or {},
            service_matrix_from_snapshot(observer.metadata.get("snap") or {}),
        ),
        citations=cites,
        metadata={
            "confidence": confidence,
            "risk_level": risk_level,
            "requires_approval": True,
            "recommended_action": recommendation,
            "security": security.model_dump(),
            "parasail_mode": llm_mode,
        },
    )

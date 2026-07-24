from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from app.models import AgentName, AgentStep, Citation, SecurityVerdict
from app.prompt_routing import build_research_query
from app.ralfia_client import fetch_live_status
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
            "transport": "HTTP GET → 127.0.0.1:8101/status",
        },
    )
    snap = await fetch_live_status(settings)
    await _flow(
        emit,
        {
            "agent": "observer",
            "kind": "response",
            "title": "Snapshot recibido",
            "explain": (
                f"Fuente: {snap.get('source')}. "
                f"Evolution en {snap.get('node_label')}: systemd={snap.get('system_state')}, "
                f"health={snap.get('health')}."
            ),
            "payload": snap,
        },
    )
    source_label = snap.get("source_label") or snap.get("source", "unknown")
    facts = [
        f"Data source: {source_label}.",
        f"Node {snap['node_label']} reachable (read-only probe).",
        f"{snap['service']}: system_state={snap['system_state']}, health={snap['health']}.",
        snap["summary"],
    ]
    ralfia = snap.get("ralfia_status") or {}
    if ralfia:
        if ralfia.get("mongodb_ok") is not None:
            facts.append(
                f"RalfIA MongoDB ok={ralfia.get('mongodb_ok')}, "
                f"clients={ralfia.get('mongodb_clients')}, "
                f"pipeline={ralfia.get('mongodb_pipeline_items')}."
            )
        if ralfia.get("integration_mode"):
            facts.append(
                f"RalfIA integration mode={ralfia.get('integration_mode')} "
                f"(http {ralfia.get('http_port')}, mcp {ralfia.get('mcp_port')})."
            )
    hypotheses = [
        "Session or number block on WhatsApp line (operator-reported).",
        "Health probe mismatch while systemd unit remains active.",
    ]
    return AgentStep(
        agent=AgentName.observer,
        status="completed",
        started_at=started,
        finished_at=_now(),
        summary="Observed dual-node incident snapshot without side effects.",
        facts=facts,
        hypotheses=hypotheses,
        metadata={
            "evidence_ref": snap.get("evidence_ref"),
            "source": snap.get("source"),
            "dry_run": True,
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
    query = build_research_query(user_prompt or "", observer.facts)
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
            "payload": {"query": query, "user_prompt": user_prompt or ""},
        },
    )
    search_hits, search_mode = await client.search(query)
    await _flow(
        emit,
        {
            "agent": "research",
            "kind": "response",
            "title": f"Search OK · {len(search_hits)} resultados",
            "explain": f"Modo {search_mode}. Estos URLs alimentan Contents y Research.",
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
    await _flow(
        emit,
        {
            "agent": "research",
            "kind": "response",
            "title": f"Research OK · {len(research_cites)} citas",
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

    citations: list[Citation] = []
    for hit in search_hits:
        citations.append(
            Citation(
                title=hit.get("title") or "Source",
                url=hit.get("url") or "",
                snippet=str(hit.get("snippet") or "")[:500],
            )
        )
    for hit in research_cites:
        citations.append(
            Citation(
                title=hit.get("title") or "Research source",
                url=hit.get("url") or "",
                snippet=str(hit.get("snippet") or "")[:500],
            )
        )

    preview = research_report[:1200].strip()
    facts = [
        f"You.com search mode: {search_mode}; hits={len(search_hits)}.",
        f"You.com research mode: {research_mode}; citations={len(citations)}.",
        preview[:320] + ("…" if len(preview) > 320 else ""),
    ]
    if contents_snippet:
        facts.append(f"Contents excerpt ({contents_mode}): {contents_snippet[:400]}")

    hypotheses = [
        "Blocked WhatsApp number prevents Evolution session recovery.",
        "Restart would not fix without new pairing — high risk of false positive fix.",
    ]

    return AgentStep(
        agent=AgentName.research,
        status="completed",
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
    blocked: list[str] = []
    reasons: list[str] = []
    has_citations = len(research.citations) >= 1
    status_only = research.metadata.get("youcom_research_mode") == "skipped_status_only"
    if not has_citations and not status_only:
        reasons.append("Insufficient citations for operational action.")
    if not observer.metadata.get("dry_run", True):
        reasons.append("Observer not in dry-run mode.")
    approved = has_citations or status_only
    if status_only:
        reasons.append("Read-only status answer — no destructive action proposed.")
    elif not approved:
        reasons.append("Need cited research before any operational checkpoint.")
    else:
        reasons.append("Dry-run only — destructive actions remain blocked at gateway.")
    return SecurityVerdict(
        approved=approved,
        blocked_actions=["production_restart", "whatsapp_recover", "delete_instance"],
        reasons=reasons,
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
    await _flow(
        emit,
        {
            "agent": "security_reviewer",
            "kind": "request",
            "title": "Paso 3 · Security Reviewer (Parasail)",
            "explain": (
                "Recibe hechos del Observer + informe/citas de You.com. "
                "Decide si alguna acción operativa estaría justificada (dry-run)."
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
            "You are Security Reviewer in a LiveOps multi-agent system. "
            "Reject restart/recover/delete without strong cited evidence. "
            "Production is dry-run only. Output JSON only."
        )
        try:
            text, llm_mode = await llm.chat(system, user, max_tokens=500)
            parsed = ParasailClient.parse_json_block(text)
            if "approved" in parsed:
                verdict = SecurityVerdict(
                    approved=bool(parsed.get("approved")),
                    blocked_actions=list(parsed.get("blocked_actions") or []),
                    reasons=list(parsed.get("reasons") or ["Parasail review"]),
                )
        except Exception:
            llm_mode = "rules_fallback"

    await _flow(
        emit,
        {
            "agent": "security_reviewer",
            "kind": "response",
            "title": f"Veredicto seguridad · approved={verdict.approved}",
            "explain": "; ".join(verdict.reasons[:3]) or "Revisión completada.",
            "payload": {
                "parasail_mode": llm_mode,
                "security": verdict.model_dump(),
            },
        },
    )

    return AgentStep(
        agent=AgentName.security_reviewer,
        status="completed",
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
    confidence = 0.72 if research.citations else 0.45
    if security.approved:
        confidence = min(0.9, confidence + 0.1)

    recommendation = (
        "Keep Evolution API on node .5 in monitored dry-run; document blocked line; "
        "do NOT restart or recover until human operator returns from travel."
    )
    risk_level = "medium"
    llm_mode = "rules"
    llm = ParasailClient(settings)
    await _flow(
        emit,
        {
            "agent": "arbitrator",
            "kind": "request",
            "title": "Paso 4 · Arbitrator (Parasail)",
            "explain": (
                "Fusiona observación + research citado + veredicto de seguridad "
                "en una recomendación final para el operador humano."
            ),
            "transport": f"POST {settings.parasail_base_url}/chat/completions",
        },
    )
    if llm.configured():
        user = (
            f"Observer: {observer.facts}\nResearch: {research.facts[:4]}\n"
            f"Security approved={security.approved}, reasons={security.reasons}\n"
            "Synthesize final JSON: recommended_action, confidence (0-1), risk_level, "
            "requires_approval=true, dry_run=true."
        )
        system = (
            "You are Arbitrator agent. Merge You.com research + security review. "
            "Never recommend production restart without human approval."
        )
        try:
            text, llm_mode = await llm.chat(system, user, max_tokens=600)
            parsed = ParasailClient.parse_json_block(text)
            if parsed.get("recommended_action"):
                recommendation = str(parsed["recommended_action"])
            if parsed.get("confidence") is not None:
                confidence = float(parsed["confidence"])
            if parsed.get("risk_level"):
                risk_level = str(parsed["risk_level"])
        except Exception:
            llm_mode = "rules_fallback"

    await _flow(
        emit,
        {
            "agent": "arbitrator",
            "kind": "response",
            "title": "Recomendación lista",
            "explain": recommendation,
            "payload": {
                "parasail_mode": llm_mode,
                "confidence": confidence,
                "risk_level": risk_level,
                "recommended_action": recommendation,
            },
        },
    )

    return AgentStep(
        agent=AgentName.arbitrator,
        status="completed",
        started_at=started,
        finished_at=_now(),
        summary=recommendation,
        facts=observer.facts[:3],
        hypotheses=research.hypotheses[:2],
        citations=research.citations[:6],
        metadata={
            "confidence": confidence,
            "risk_level": risk_level,
            "requires_approval": True,
            "recommended_action": recommendation,
            "security": security.model_dump(),
            "parasail_mode": llm_mode,
        },
    )

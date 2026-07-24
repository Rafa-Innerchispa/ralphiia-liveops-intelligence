from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.local_analyst import AVAILABLE_LOCAL_MODELS, resolve_local_analyst_model
from app.models import AnalyzeRequest, HealthResponse, HumanDecisionRequest, PipelineResult
from app.notify import schedule_analysis_notify
from app.pipeline import (
    HACKATHON_EVENT,
    HACKATHON_TRACK,
    STORY,
    run_baseline_single_agent,
    run_pipeline,
    stream_pipeline,
)
from app.prompt_routing import normalize_prompt
from app.parasail_client import ParasailClient
from app.ralfia_client import fetch_live_status
from app.session_store import (
    merge_prompt_with_session,
    record_assistant_summary,
    reset_all_sessions_for_tests,
)
from app.youcom_client import YouComClient

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

app = FastAPI(
    title="RalphiIA LiveOps Intelligence",
    version="0.2.0-command-center",
    description="Multi-agent LiveOps demo — read-only / dry-run",
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_last_result: PipelineResult | None = None
_last_prompt: str = ""
_last_session_id: str = ""


def reset_liveops_session() -> None:
    """Reset in-process session state (tests)."""
    global _last_result, _last_prompt, _last_session_id
    _last_result = None
    _last_prompt = ""
    _last_session_id = ""
    reset_all_sessions_for_tests()


def _correlation_id(raw: str | None) -> str:
    if raw and raw.strip():
        return raw.strip()
    return f"liveops-{uuid.uuid4().hex[:12]}"


def _notify_start(settings, cid: str, prompt: str) -> None:
    schedule_analysis_notify(
        phase="started",
        correlation_id=cid,
        public_url=settings.liveops_public_url,
        user_prompt=prompt,
        enabled=settings.liveops_whatsapp_notify,
        contact_ref=settings.liveops_whatsapp_contact_ref,
        ralfia_root=settings.ralfia_openai_root,
        number=settings.liveops_whatsapp_number,
    )


def _notify_complete(settings, cid: str, prompt: str, summary: str | None) -> None:
    extra = "Status: completed"
    if summary:
        extra += f"\nSummary: {summary[:240]}"
    schedule_analysis_notify(
        phase="completed",
        correlation_id=cid,
        public_url=settings.liveops_public_url,
        user_prompt=prompt,
        enabled=settings.liveops_whatsapp_notify,
        contact_ref=settings.liveops_whatsapp_contact_ref,
        ralfia_root=settings.ralfia_openai_root,
        number=settings.liveops_whatsapp_number,
        extra=extra,
    )


def _prepare_analysis(body: AnalyzeRequest | None) -> tuple[str, str, str, bool]:
    global _last_prompt, _last_session_id
    settings = get_settings()
    raw = (body.prompt if body else "") or ""
    research_deeper = bool(body and body.research_deeper)
    session_id, prompt = merge_prompt_with_session(
        body.session_id if body else None,
        normalize_prompt(raw or None),
        research_deeper=research_deeper,
    )
    _last_prompt = prompt
    _last_session_id = session_id
    cid = _correlation_id(body.correlation_id if body else None)
    return prompt, session_id, cid, research_deeper


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/story")
async def story() -> dict:
    """Human-readable pipeline map for UI / judges."""
    return STORY


@app.get("/api/build-review")
async def build_review() -> dict:
    """Opsera Agents — development-time review evidence (not runtime)."""
    path = DATA_DIR / "opsera_build_review.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "tool": "Opsera Agents (Cursor IDE)",
        "scope": "Development-time security/architecture review — not a LiveOps runtime agent",
        "status": "not_run",
        "verdict": None,
        "summary": (
            "This product was built in Cursor; Opsera Agents can scan the repo before commit. "
            "Export scan results to data/opsera_build_review.json for PASS/WARN/FAIL on this panel."
        ),
        "partner_note": "Eligible for Opsera partner prize when scan evidence is real (IDE), not simulated in the pipeline.",
    }


@app.get("/api/nodes")
async def live_nodes() -> dict:
    settings = get_settings()
    snap = await fetch_live_status(settings)
    src = snap.get("source", "unknown")
    kind = "live" if src == "ralfia_health_readonly" else "fixture"
    return {
        "checked_at": snap.get("checked_at"),
        "nodes": {
            "amd_5": {
                "label": "Node .5 · Evolution API",
                "system_state": snap.get("system_state"),
                "health": snap.get("health"),
                "service": snap.get("service"),
                "source": kind,
                "source_label": snap.get("source_label"),
            },
            "incident_fixture": {
                "label": "Incident narrative",
                "source": "fixture",
                "source_label": "Fallback fixture metadata (always labeled)",
            },
        },
        "ralfia_probe": {
            "endpoint": "GET :8101/status",
            "source": kind,
            "mongodb_ok": (snap.get("ralfia_status") or {}).get("mongodb_ok"),
        },
        "models_available_local": AVAILABLE_LOCAL_MODELS,
    }


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    youcom = settings.youcom_key_status()
    client = YouComClient(settings)
    youcom["mcp"] = await client.mcp_status()
    youcom["transport"] = settings.youcom_transport
    youcom["balance"] = await client.balance()
    youcom["parasail"] = settings.parasail_status()
    local_probe = await resolve_local_analyst_model(settings)
    youcom["local_analyst"] = {
        "available": bool(local_probe.get("model")),
        "model": local_probe.get("model"),
        "models_catalog": AVAILABLE_LOCAL_MODELS,
    }
    return HealthResponse(
        ok=True,
        service="ralphiia-liveops-intelligence",
        port=settings.liveops_port,
        data_mode=settings.data_mode,
        youcom=youcom,
        dry_run=settings.dry_run,
        timestamp=datetime.now(timezone.utc).isoformat(),
        hackathon_track=HACKATHON_TRACK,
        hackathon_event=HACKATHON_EVENT,
    )


@app.get("/api/analyze/stream")
async def analyze_stream_get(
    prompt: str | None = Query(default=None, max_length=4000),
    correlation_id: str | None = Query(default=None, max_length=128),
    session_id: str | None = Query(default=None, max_length=64),
    research_deeper: bool = Query(default=False),
) -> StreamingResponse:
    body = AnalyzeRequest(
        prompt=prompt or "",
        correlation_id=correlation_id,
        session_id=session_id,
        research_deeper=research_deeper,
    )
    return await _analyze_stream_response(body)


@app.post("/api/analyze/stream")
async def analyze_stream_post(body: AnalyzeRequest | None = None) -> StreamingResponse:
    return await _analyze_stream_response(body or AnalyzeRequest())


async def _analyze_stream_response(body: AnalyzeRequest) -> StreamingResponse:
    settings = get_settings()
    prompt, session_id, cid, research_deeper = _prepare_analysis(body)
    _notify_start(settings, cid, prompt)

    async def event_source():
        global _last_result
        async for chunk in stream_pipeline(
            settings,
            correlation_id=cid,
            user_prompt=prompt,
            session_id=session_id,
            research_deeper=research_deeper,
        ):
            yield chunk
            if chunk.startswith("event: complete\n"):
                import json as _json

                for line in chunk.split("\n"):
                    if line.startswith("data: "):
                        payload = _json.loads(line[6:])
                        _last_result = PipelineResult.model_validate(payload["result"])
                        record_assistant_summary(
                            session_id, _last_result.operator_summary or ""
                        )
                        _notify_complete(
                            settings,
                            cid,
                            prompt,
                            _last_result.operator_summary or None,
                        )
                        break

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/analyze", response_model=PipelineResult)
async def analyze(body: AnalyzeRequest | None = None) -> PipelineResult:
    global _last_result
    settings = get_settings()
    prompt, session_id, cid, research_deeper = _prepare_analysis(body or AnalyzeRequest())
    _notify_start(settings, cid, prompt)
    result = await run_pipeline(
        settings,
        correlation_id=cid,
        user_prompt=prompt,
        session_id=session_id,
        research_deeper=research_deeper,
    )
    _last_result = result
    record_assistant_summary(session_id, result.operator_summary or "")
    _notify_complete(settings, cid, prompt, result.operator_summary or None)
    return result


@app.get("/api/last", response_model=PipelineResult | None)
async def last_result() -> PipelineResult | None:
    return _last_result


@app.post("/api/decision")
async def human_decision(body: HumanDecisionRequest) -> dict:
    global _last_result, _last_prompt, _last_session_id
    if _last_result is None:
        raise HTTPException(400, "Run /api/analyze first")
    if body.decision not in {"approve", "reject", "research_deeper"}:
        raise HTTPException(400, "Invalid decision")
    if body.decision == "research_deeper":
        checkpoint = {
            "decision": body.decision,
            "note": body.note,
            "executed": False,
            "dry_run_checkpoint": True,
            "message": "Research deeper — re-running pipeline anchored to session question.",
            "reuse_prompt": _last_prompt,
            "session_id": _last_session_id,
            "research_deeper": True,
        }
        _last_result.human_decision = body.decision
        return checkpoint
    checkpoint = {
        "decision": body.decision,
        "note": body.note,
        "executed": False,
        "dry_run_checkpoint": True,
        "message": (
            "No production changes applied. Approve is audit-only until operator confirms."
        ),
    }
    _last_result.human_decision = body.decision
    return checkpoint


@app.get("/api/youcom/probe")
async def youcom_probe() -> dict:
    """One live You.com call chain for judges — no secrets in response."""
    settings = get_settings()
    client = YouComClient(settings)
    query = "WhatsApp Evolution API instance health down systemd active troubleshooting"
    search, search_mode = await client.search(query, count=3)
    contents_mode = "skipped"
    if search and search[0].get("url"):
        _, contents_mode = await client.contents(search[0]["url"])
    report, cites, research_mode = await client.research(query)
    live = settings.resolved_youcom_key() != ""
    return {
        "ok": True,
        "mode": "live" if live and "mcp" in search_mode else search_mode,
        "transport": settings.youcom_transport,
        "mcp": await client.mcp_status(),
        "stack": [
            "you-search",
            "you-contents",
            "you-research",
            "agent-skills-compatible",
        ],
        "tools_used": {
            "search": search_mode,
            "contents": contents_mode,
            "research": research_mode,
        },
        "citation_count": len(search) + len(cites),
        "research_preview": report[:280],
        "mcp_endpoint": settings.youcom_mcp_url,
    }


@app.get("/api/parasail/probe")
async def parasail_probe() -> dict:
    settings = get_settings()
    client = ParasailClient(settings)
    if not client.configured():
        return {"ok": False, "error": "Set PARASAIL_API_KEY (https://www.saas.parasail.io/keys)"}
    try:
        models = await client.list_models()
        text, mode = await client.chat(
            "Reply with one short sentence: Parasail inference OK for LiveOps agents.",
            "Health check",
            max_tokens=40,
        )
        return {
            "ok": True,
            "mode": mode,
            "model": settings.parasail_model,
            "models_sample": models[:5],
            "reply": text[:200],
            "base_url": settings.parasail_base_url,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


@app.get("/api/youcom/balance")
async def youcom_balance() -> dict:
    """Workshop Step 3a — MCP you-balance (credits), no secrets."""
    settings = get_settings()
    client = YouComClient(settings)
    return await client.balance()


@app.get("/api/evals")
async def evals() -> dict:
    settings = get_settings()
    multi = await run_pipeline(settings)
    baseline = await run_baseline_single_agent(settings)
    cases = [
        {
            "name": "evolution_amd_health_down",
            "multi_agent_citations": len(multi.recommendation.citations),
            "baseline_unsafe": baseline["unsafe"],
        },
        {
            "name": "missing_youcom_key",
            "mode": multi.youcom_mode,
            "fixture_expected": not settings.resolved_youcom_key(),
        },
        {
            "name": "security_blocks_restart",
            "reviewer_approved": multi.recommendation.security.approved,
        },
    ]
    return {
        "cases": cases,
        "metrics": multi.metrics,
        "baseline": baseline,
        "comparison": {
            "citation_delta": len(multi.recommendation.citations) - baseline["citations"],
            "baseline_recommends_restart": baseline["recommended_action"],
            "multi_agent_requires_approval": multi.recommendation.requires_approval,
        },
    }

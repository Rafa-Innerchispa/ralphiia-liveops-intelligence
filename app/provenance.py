from __future__ import annotations

import re
from typing import Any

from app.models import Citation

I18N_KEY_RE = re.compile(r"^prompt[A-Z]|^chip[0-9]|^cta[A-Z]|^err[A-Z]|^state[A-Z]")

DEMO_SCENARIO_LINE = (
    "Hackathon demo scenario (not observed live this run): Evolution API on node .5 — "
    "systemd=active, health=down — operator-reported WhatsApp line blocked."
)

MAX_YOUCOM_QUERY_CHARS = 900
MAX_YOUCOM_SEARCH_CHARS = 380


def sanitize_operator_prompt(raw: str | None) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if I18N_KEY_RE.match(text) or text in {"promptLiveStatus", "promptInvestigate"}:
        return ""
    return text


def is_live_source(source: str | None) -> bool:
    return source in ("ralfia_health_readonly", "ralfia_bridge_live")


def demo_context_facts() -> list[str]:
    return [f"DEMO_CONTEXT: {DEMO_SCENARIO_LINE}"]


def observer_facts_from_snap(snap: dict[str, Any], matrix: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Return (observed_facts, demo_context_facts)."""
    source = snap.get("source") or ""
    observed: list[str] = [
        f"Data source: {snap.get('source_label', source)}.",
        f"Checked at: {snap.get('checked_at', 'now')}.",
    ]
    demo: list[str] = []
    if is_live_source(source):
        for line in matrix["down"]:
            observed.append(f"UNHEALTHY: {line}")
        for line in matrix["degraded"]:
            observed.append(f"DEGRADED: {line}")
        for line in matrix["up"]:
            observed.append(f"HEALTHY: {line}")
        if snap.get("summary"):
            observed.append(f"Summary: {snap['summary']}")
    elif source == "live_unavailable":
        observed.append(
            "OBSERVED: Live infrastructure probe failed — no live service matrix from bridge/LAN."
        )
        demo.extend(demo_context_facts())
    elif source.startswith("fixture"):
        observed.append(f"FIXTURE_LABELED: {snap.get('summary', 'fallback fixture')}")
        for line in matrix["down"] + matrix["degraded"]:
            observed.append(f"FIXTURE: {line}")
    else:
        observed.append(f"Source: {source}")
    ralfia = snap.get("ralfia_status") or {}
    if ralfia and is_live_source(source):
        if ralfia.get("mongodb_ok") is not None:
            observed.append(
                f"RalfIA MongoDB ok={ralfia.get('mongodb_ok')}, "
                f"clients={ralfia.get('mongodb_clients')}."
            )
    return observed, demo


def facts_for_research_prompt(observed: list[str], demo: list[str]) -> str:
    parts = [f for f in observed if not f.startswith("FIXTURE")]
    if demo:
        parts.append("(Demo context only, not live observed: " + demo[0].replace("DEMO_CONTEXT: ", "") + ")")
    return " ".join(parts)[:500]


def build_sanitized_search_query(user_prompt: str, observed: list[str], demo: list[str]) -> str:
    """Short query for you-search (avoids MCP 422 on oversized prompts)."""
    prompt = sanitize_operator_prompt(user_prompt)
    if not prompt:
        prompt = "RalfIA infrastructure MCP error backlog monitoring read-only"
    watch = next((f for f in observed if "DEGRADED:" in f or "UNHEALTHY:" in f), "")
    watch_short = watch.replace("DEGRADED:", "").replace("UNHEALTHY:", "").strip()[:120]
    q = f"{prompt[:200]} {watch_short} MCP monitoring best practices".strip()
    return q[:MAX_YOUCOM_SEARCH_CHARS]


def build_sanitized_research_query(user_prompt: str, observed: list[str], demo: list[str]) -> str:
    prompt = sanitize_operator_prompt(user_prompt)
    if not prompt:
        prompt = (
            "Investigate Evolution API health and WhatsApp session issues using "
            "current public documentation."
        )
    ctx = facts_for_research_prompt(observed, demo)
    q = (
        f"{prompt} Context: {ctx} "
        "Evolution API WhatsApp health systemd troubleshooting read-only."
    ).strip()
    return q[:MAX_YOUCOM_QUERY_CHARS]


def is_valid_citation_url(url: str | None) -> bool:
    if not url:
        return False
    u = url.strip()
    if u in ("**", "#", "http://", "https://"):
        return False
    if not u.startswith("http://") and not u.startswith("https://"):
        return False
    if "you.com/docs/welcome" in u:
        return False
    return True


def canonical_citations(citations: list[Citation | dict[str, Any]]) -> list[Citation]:
    seen: set[str] = set()
    out: list[Citation] = []
    for item in citations:
        if isinstance(item, Citation):
            c = item
        else:
            c = Citation.model_validate(item)
        url = (c.url or "").strip()
        snippet = c.snippet or ""
        if "Error code: 422" in snippet or "Failed to perform search" in snippet:
            continue
        if not is_valid_citation_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(c)
    return out

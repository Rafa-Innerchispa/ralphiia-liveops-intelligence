from __future__ import annotations

from typing import Any

from app.provenance import is_live_source


def service_matrix_from_snapshot(snap: dict[str, Any]) -> dict[str, list[str]]:
    """Classify services for operator-facing reports (no secrets)."""
    up: list[str] = []
    degraded: list[str] = []
    down: list[str] = []

    ralfia = snap.get("ralfia_status") or {}
    live_src = snap.get("source") in ("ralfia_health_readonly", "ralfia_bridge_live")
    if live_src:
        up.append(
            f"RalfIA gateway ({ralfia.get('service_label') or 'control plane'}) — "
            f"HTTP :{ralfia.get('http_port', '8101')}, MCP :{ralfia.get('mcp_port', '8102')}"
        )
        if ralfia.get("mongodb_ok") is True:
            up.append(
                f"MongoDB ({ralfia.get('mongodb_db', 'db')}) — "
                f"clients={ralfia.get('mongodb_clients')}, "
                f"pipeline_items={ralfia.get('mongodb_pipeline_items')}"
            )
        elif ralfia.get("mongodb_ok") is False:
            down.append("MongoDB — probe reports ok=false")
        mcp_err = ralfia.get("mongodb_mcp_errors")
        if mcp_err is not None and int(mcp_err or 0) > 0:
            degraded.append(
                f"RalfIA MCP error backlog — {mcp_err} recorded errors (investigate logs, read-only)"
            )
    elif snap.get("source") == "live_unavailable":
        down.append(
            "Live infrastructure probe unavailable — configure bridge or run from LAN; "
            "not using hidden fixture."
        )
        degraded.append(
            "Demo scenario (not observed live): Evolution on .5 — health down narrative for hackathon only."
        )
    elif snap.get("source", "").startswith("fixture"):
        degraded.append("RalfIA live probe unavailable — using labeled fallback fixture")

    if is_live_source(snap.get("source") or ""):
        evo_state = snap.get("system_state") or "unknown"
        evo_health = snap.get("health") or "unknown"
        evo_name = snap.get("service") or "Evolution API"
        node = snap.get("node_label") or ".5"
        if evo_health == "down" or (evo_state == "active" and evo_health != "up"):
            down.append(
                f"{evo_name} on node {node} — systemd={evo_state}, health probe={evo_health} "
                "(operator-reported WhatsApp line blocked; dry-run — no recover/restart)"
            )
        else:
            up.append(f"{evo_name} on node {node} — systemd={evo_state}, health={evo_health}")

    return {"up": up, "degraded": degraded, "down": down}


def format_service_status_block(snap: dict[str, Any]) -> str:
    m = service_matrix_from_snapshot(snap)
    src = snap.get("source") or ""
    if src == "live_unavailable":
        lines = ["Live infrastructure probe (read-only)", "", "Unhealthy / blocking:"]
        lines.extend(f"  • {x}" for x in m["down"])
        if m["degraded"]:
            lines.append("")
            lines.append("Degraded / demo context (not observed live):")
            lines.extend(f"  • {x}" for x in m["degraded"])
        lines.append("")
        lines.append(f"Evidence: {snap.get('source_label', src)}.")
        return "\n".join(lines)
    lines = ["Live infrastructure snapshot (read-only)"]
    if m["down"]:
        lines.append("")
        lines.append("Unhealthy / blocking:")
        lines.extend(f"  • {x}" for x in m["down"])
    if m["degraded"]:
        lines.append("")
        lines.append("Degraded / watch:")
        lines.extend(f"  • {x}" for x in m["degraded"])
    if m["up"]:
        lines.append("")
        lines.append("Healthy / reachable:")
        lines.extend(f"  • {x}" for x in m["up"])
    lines.append("")
    lines.append(f"Evidence: {snap.get('source_label', snap.get('source', '?'))}.")
    return "\n".join(lines)


def build_status_only_recommendation(snap: dict[str, Any], observer_facts: list[str]) -> str:
    block = format_service_status_block(snap)
    return (
        f"{block}\n\n"
        "Recommended action (dry-run): Do not restart Evolution or run WhatsApp recover. "
        "Monitor the health probe and blocked line until you approve a change. "
        "Use button 2 · Investigate with Live Sources for web-backed remediation and citations."
    )


def build_investigate_intro(snap: dict[str, Any]) -> str:
    return format_service_status_block(snap)


def merge_recommendation_with_snapshot(snap: dict[str, Any], recommendation: str) -> str:
    """Ensure operator always sees service matrix even if LLM answer is vague."""
    block = format_service_status_block(snap)
    rec = (recommendation or "").strip()
    if not rec:
        return block
    if "Unhealthy / blocking:" in rec or "Live infrastructure snapshot" in rec:
        return rec
    return f"{block}\n\nOperator verdict (dry-run):\n{rec}"

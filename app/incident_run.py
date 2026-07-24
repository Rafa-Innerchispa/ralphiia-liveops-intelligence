from __future__ import annotations

import re
from typing import Any

from app.models import Citation
from app.ops_brief import format_service_status_block, service_matrix_from_snapshot


def derive_incident_id(snap: dict[str, Any], matrix: dict[str, list[str]]) -> str:
    text = " ".join(matrix["down"] + matrix["degraded"] + matrix["up"]).lower()
    if "mcp error backlog" in text or "mcp_errors" in text:
        return "ralfia-mcp-error-backlog"
    if snap.get("health") == "down" and "evolution" in text:
        return "evolution-health-down"
    if snap.get("source") == "live_unavailable":
        return "live-probe-unavailable"
    if matrix["down"]:
        slug = re.sub(r"[^a-z0-9]+", "-", matrix["down"][0].lower())[:48].strip("-")
        return slug or "infrastructure-watch"
    return "infrastructure-healthy"


def hypotheses_for_run(snap: dict[str, Any], matrix: dict[str, list[str]]) -> list[str]:
    hyps: list[str] = []
    text = " ".join(matrix["degraded"] + matrix["down"]).lower()
    if "mcp error backlog" in text:
        hyps.append(
            "MCP error backlog may mix historical, repeated, or benign errors — "
            "needs categorization by tool/code/time window (hypothesis, not proven outage)."
        )
    evo_health = (snap.get("health") or "").lower()
    if evo_health == "down":
        hyps.append(
            "Evolution health probe down while systemd active may indicate session or "
            "connectivity issues (operator-reported context only if labeled)."
        )
    if not hyps:
        hyps.append(
            "No blocking failure detected in live snapshot — continue read-only monitoring."
        )
    return hyps[:3]


def primary_watch_item(matrix: dict[str, list[str]]) -> str | None:
    for bucket in ("down", "degraded"):
        for line in matrix[bucket]:
            if "mcp error backlog" in line.lower():
                return line
    return matrix["degraded"][0] if matrix["degraded"] else (
        matrix["down"][0] if matrix["down"] else None
    )


def build_cited_investigate_answer(
    snap: dict[str, Any],
    matrix: dict[str, list[str]],
    citations: list[Citation],
    *,
    security_approved: bool,
    security_reasons: list[str],
) -> str:
    """Operator-facing answer: facts vs hypotheses, read-only steps with [n] cites."""
    healthy = matrix["up"]
    watch = matrix["degraded"] + matrix["down"]
    lines: list[str] = []

    lines.append("What is reachable / observed")
    if healthy:
        for h in healthy[:5]:
            lines.append(f"• {h}")
    else:
        lines.append("• No reachable services reported in this snapshot.")

    lines.append("")
    lines.append("What needs investigation")
    watch_line = primary_watch_item(matrix)
    if watch_line and "mcp error backlog" in watch_line.lower():
        lines.append(
            "• The main watch item is the RalfIA MCP backlog of recorded errors. "
            "The count alone does not prove active capacity exhaustion or service failure."
        )
    elif watch:
        for w in watch[:3]:
            lines.append(f"• {w}")
    else:
        lines.append("• No degraded signals in the live snapshot.")

    lines.append("")
    lines.append("Recommended read-only next steps")
    step_templates = [
        (
            "Categorize MCP errors by tool, code, and time window",
            "log categorization and error taxonomy",
        ),
        (
            "Compare error rate with latency, CPU, and memory before attributing capacity issues",
            "error-rate and time-window analysis",
        ),
        (
            "Add request-scoped tracing to correlate repeated MCP failures",
            "tracing and latency correlation",
        ),
    ]
    n = min(len(step_templates), max(1, len(citations)))
    for i in range(n):
        step_text, _ = step_templates[i]
        if i < len(citations):
            c = citations[i]
            lines.append(
                f"• {step_text} [{i + 1}] {c.title} — {c.url}"
            )
        else:
            lines.append(f"• {step_text}")
    lines.append(
        "• No restart or production configuration change is recommended from current evidence."
    )

    if citations:
        lines.append("")
        lines.append("Sources (canonical index)")
        for i, c in enumerate(citations[:12], start=1):
            lines.append(f"[{i}] {c.title} — {c.url}")

    lines.append("")
    lines.append("Security review")
    if security_approved:
        lines.append(
            "Read-only investigation is acceptable. Restart, recover, and delete actions "
            "remain unapproved until impact and root cause are verified."
        )
    else:
        lines.append(
            "Security review did NOT approve proposed remediation: "
            + "; ".join(security_reasons[:3])
        )

    return "\n".join(lines)


def rules_fallback_recommendation(
    snap: dict[str, Any],
    citations: list[Citation],
    security: Any,
) -> str:
    matrix = service_matrix_from_snapshot(snap)
    return build_cited_investigate_answer(
        snap,
        matrix,
        citations,
        security_approved=bool(getattr(security, "approved", True)),
        security_reasons=list(getattr(security, "reasons", []) or []),
    )

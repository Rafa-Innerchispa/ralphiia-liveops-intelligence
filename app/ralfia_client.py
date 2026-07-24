from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings

INCIDENT_FIXTURE = {
    "incident_id": "evolution-amd-health-down",
    "node_label": ".5",
    "service": "Evolution API",
    "system_state": "active",
    "health": "down",
    "summary": (
        "Dual-node probe: AMD node reachable; Evolution API systemd active "
        "but health probe reports down (known WhatsApp line blocked — dry-run only)."
    ),
    "evidence_ref": "health:liveops-fixture",
    "checked_at": datetime.now(timezone.utc).isoformat(),
}

# Safe read-only probes documented for judges (no mutations, no secrets).
RALFIA_READ_ONLY_PROBES = [
    "GET http://127.0.0.1:8101/status — service mode, Mongo summary, doc pointers",
    "GET http://127.0.0.1:8101/health — lightweight health (when available)",
]


def _redact_url(url: str | None) -> str | None:
    if not url:
        return url
    if "192.168." in url or "127.0.0.1" in url:
        return "RalfIA gateway (LAN — redacted in UI)"
    return url


def _sanitize_status_payload(data: dict[str, Any]) -> dict[str, Any]:
    mongo = data.get("mongodb") or {}
    return {
        "service_label": data.get("service"),
        "integration_mode": data.get("mode"),
        "integration_detail": data.get("integration"),
        "http_port": data.get("http_port"),
        "mcp_port": data.get("mcp_port"),
        "public_url": _redact_url(data.get("public_url")),
        "mcp_public_url": data.get("mcp_public_url"),
        "mongodb_ok": mongo.get("ok"),
        "mongodb_db": mongo.get("db"),
        "mongodb_clients": mongo.get("clients"),
        "mongodb_ideas": mongo.get("ideas"),
        "mongodb_pipeline_items": mongo.get("editorial_pipeline"),
        "mongodb_bridge_messages": mongo.get("bridge_messages"),
        "mongodb_mcp_errors": mongo.get("mcp_errors"),
        "endpoints_doc": (data.get("docs") or {}).get("mcp_setup"),
    }


async def fetch_live_status(settings: Settings) -> dict:
    """Read-only probe: local health endpoint only; no mutations."""
    if not settings.ralfia_status_probe:
        return {
            **INCIDENT_FIXTURE,
            "source": "fixture",
            "source_label": "Fallback fixture",
            "read_only_probes": RALFIA_READ_ONLY_PROBES,
        }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(settings.ralfia_status_endpoint())
            if resp.status_code == 200:
                data = resp.json()
                sanitized = _sanitize_status_payload(data)
                return {
                    **INCIDENT_FIXTURE,
                    "source": "ralfia_health_readonly",
                    "source_label": "Live · RalfIA :8101/status",
                    "ralfia_status": sanitized,
                    "primary_mongodb_ok": sanitized.get("mongodb_ok"),
                    "service_label": sanitized.get("service_label") or data.get("service"),
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "read_only_probes": RALFIA_READ_ONLY_PROBES,
                }
    except httpx.HTTPError:
        pass
    return {
        **INCIDENT_FIXTURE,
        "source": "fixture_fallback",
        "source_label": "Fallback fixture (8101 unreachable)",
        "read_only_probes": RALFIA_READ_ONLY_PROBES,
    }

from __future__ import annotations

import os
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

RALFIA_READ_ONLY_PROBES = [
    "GET /liveops-bridge/status — sanitized hybrid bridge (Bearer, Cloudflare/ngrok)",
    "GET http://127.0.0.1:8101/status — local RalfIA gateway (LAN demo only)",
]

SOURCE_BRIDGE = "ralfia_bridge_live"
SOURCE_LOCAL = "ralfia_health_readonly"
SOURCE_FIXTURE = "fixture"
SOURCE_FIXTURE_FALLBACK = "fixture_fallback"
SOURCE_UNAVAILABLE = "live_unavailable"


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


def _is_local_probe(url: str) -> bool:
    u = url.lower()
    return "127.0.0.1" in u or "localhost" in u or "192.168." in u


def _is_bridge_probe(url: str) -> bool:
    if _is_local_probe(url):
        return False
    return "liveops-bridge" in url or url.startswith("https://")


def _probe_headers(settings: Settings) -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    token = settings.resolved_ralfia_status_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    cf_id = os.getenv("CF_ACCESS_CLIENT_ID", "").strip()
    cf_secret = os.getenv("CF_ACCESS_CLIENT_SECRET", "").strip()
    if cf_id and cf_secret:
        headers["CF-Access-Client-Id"] = cf_id
        headers["CF-Access-Client-Secret"] = cf_secret
    return headers


def _map_bridge_payload(data: dict[str, Any]) -> dict[str, Any]:
    evolution = data.get("evolution_amd") or {}
    if not evolution:
        for svc in data.get("services") or []:
            if "evolution" in str(svc.get("service_id") or "").lower():
                evolution = svc
                break
    node_label = evolution.get("node_label") or ".5"
    system_state = evolution.get("system_state") or "unknown"
    health = evolution.get("health") or "unknown"
    ralfia = data.get("ralfia_control_plane") or {}
    summary = str(
        data.get("summary")
        or f"Bridge verified Evolution node {node_label}: systemd={system_state}, health={health}."
    )
    return {
        **INCIDENT_FIXTURE,
        "node_label": node_label,
        "service": evolution.get("name") or "Evolution API",
        "system_state": system_state,
        "health": health,
        "summary": summary,
        "evidence_ref": data.get("evidence_ref") or "liveops-bridge",
        "source": SOURCE_BRIDGE,
        "source_label": "Live · RalfIA bridge",
        "ralfia_status": ralfia,
        "bridge_reachability": data.get("reachability") or {},
        "bridge_services": data.get("services") or [],
        "verified_at": data.get("verified_at"),
        "checked_at": data.get("checked_at") or datetime.now(timezone.utc).isoformat(),
        "read_only_probes": RALFIA_READ_ONLY_PROBES,
    }


def _fixture_snapshot(settings: Settings, *, label: str, source: str) -> dict:
    mode = settings.resolved_data_mode()
    if mode == "live" and source != SOURCE_FIXTURE:
        return _unavailable_snapshot(settings, reason=label)
    return {
        **INCIDENT_FIXTURE,
        "source": source,
        "source_label": label,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only_probes": RALFIA_READ_ONLY_PROBES,
    }


def _unavailable_snapshot(settings: Settings, *, reason: str) -> dict:
    return {
        **INCIDENT_FIXTURE,
        "source": SOURCE_UNAVAILABLE,
        "source_label": "Unavailable · live probe failed",
        "summary": (
            f"Live infrastructure probe failed ({reason}). "
            "No silent fixture — use LAN demo or configure RALFIA_STATUS_URL + token."
        ),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only_probes": RALFIA_READ_ONLY_PROBES,
    }


def _map_local_payload(data: dict[str, Any]) -> dict:
    sanitized = _sanitize_status_payload(data)
    return {
        **INCIDENT_FIXTURE,
        "source": SOURCE_LOCAL,
        "source_label": "Live · RalfIA :8101/status",
        "ralfia_status": sanitized,
        "primary_mongodb_ok": sanitized.get("mongodb_ok"),
        "service_label": sanitized.get("service_label") or data.get("service"),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "read_only_probes": RALFIA_READ_ONLY_PROBES,
    }


async def fetch_live_status(settings: Settings) -> dict:
    """Read-only probe: local :8101 or authenticated HTTPS bridge."""
    if not settings.ralfia_status_probe:
        return _fixture_snapshot(settings, label="Fallback fixture (probe disabled)", source=SOURCE_FIXTURE)

    url = settings.ralfia_status_endpoint()
    headers = _probe_headers(settings)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("source") == "live_ralfia_bridge" or data.get("evolution_amd"):
                    if data.get("ok") is False:
                        return _unavailable_snapshot(settings, reason="bridge ok=false")
                    return _map_bridge_payload(data)
                if _is_local_probe(url) or data.get("mongodb") is not None:
                    return _map_local_payload(data)
                if _is_bridge_probe(url):
                    return _map_bridge_payload(data)
            elif resp.status_code in (401, 403):
                return _unavailable_snapshot(settings, reason=f"HTTP {resp.status_code}")
    except httpx.HTTPError:
        pass

    if settings.resolved_data_mode() == "fixture":
        return _fixture_snapshot(
            settings,
            label="Fallback fixture (explicit fixture mode)",
            source=SOURCE_FIXTURE_FALLBACK,
        )
    return _unavailable_snapshot(settings, reason="timeout or unreachable")

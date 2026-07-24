from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

from bridge_app.settings import BridgeSettings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence_ref(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return f"liveops-bridge:{digest}"


def _load_whatsapp_snapshot(settings: BridgeSettings) -> dict[str, Any] | None:
    root = settings.ralfia_openai_root
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from raphiia_openai import whatsapp_service_ops  # type: ignore

        return whatsapp_service_ops.status_snapshot()
    except Exception:
        return None


def _sanitize_service_item(item: dict[str, Any]) -> dict[str, Any]:
    node = item.get("node") or "unknown"
    node_label = ".4" if node == "primary" else ".5" if node == "amd" else str(node)
    health = str(item.get("health") or "unknown")
    system_state = str(item.get("system_state") or "unknown")
    healthy = bool(item.get("healthy"))
    if health == "down" or (not healthy and system_state == "active"):
        status_label = "unhealthy"
    elif not healthy:
        status_label = "degraded"
    else:
        status_label = "healthy"
    return {
        "service_id": item.get("service_id"),
        "name": item.get("label") or item.get("service_id") or "service",
        "node": node,
        "node_label": node_label,
        "system_state": system_state,
        "health": health,
        "status_label": status_label,
        "healthy": healthy,
    }


def _sanitize_ralfia_status(data: dict[str, Any]) -> dict[str, Any]:
    mongo = data.get("mongodb") or {}
    return {
        "service_label": data.get("service"),
        "integration_mode": data.get("mode"),
        "http_port": data.get("http_port"),
        "mcp_port": data.get("mcp_port"),
        "mongodb_ok": mongo.get("ok"),
        "mongodb_clients": mongo.get("clients"),
        "mongodb_pipeline_items": mongo.get("editorial_pipeline"),
        "mongodb_mcp_errors": mongo.get("mcp_errors"),
    }


async def build_bridge_status(settings: BridgeSettings) -> dict[str, Any]:
    verified_at = _now_iso()
    reachability: dict[str, bool] = {"ralfia_gateway": False, "node_amd": False, "node_primary": False}
    ralfia_control: dict[str, Any] = {}
    services: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(settings.ralfia_internal_status_url)
            if resp.status_code == 200:
                reachability["ralfia_gateway"] = True
                ralfia_control = _sanitize_ralfia_status(resp.json())
    except httpx.HTTPError:
        pass

    snap = _load_whatsapp_snapshot(settings)
    if snap:
        for host in snap.get("hosts") or []:
            node = str(host.get("node") or "")
            if node == "amd":
                reachability["node_amd"] = bool(host.get("reachable"))
            elif node == "primary":
                reachability["node_primary"] = bool(host.get("reachable"))
        for item in snap.get("items") or []:
            if not item.get("ok"):
                continue
            services.append(_sanitize_service_item(item))

    evolution = next(
        (
            s
            for s in services
            if "evolution" in str(s.get("service_id") or "").lower()
            or "evolution" in str(s.get("name") or "").lower()
        ),
        None,
    )
    if not evolution and services:
        evolution = next((s for s in services if s.get("node") == "amd"), services[0])

    ok = reachability["ralfia_gateway"] and bool(services)
    core = {
        "verified_at": verified_at,
        "reachability": reachability,
        "services": services,
        "ralfia_control_plane": ralfia_control,
        "evolution_amd": evolution,
    }
    evidence_ref = _evidence_ref({"verified_at": verified_at, "services": services})
    summary = (
        "Dual-node read-only bridge: RalfIA gateway "
        + ("reachable" if reachability["ralfia_gateway"] else "unreachable")
        + "; "
    )
    if evolution:
        summary += (
            f"Evolution on node {evolution.get('node_label')}: "
            f"systemd={evolution.get('system_state')}, health={evolution.get('health')}."
        )
    else:
        summary += "Evolution status not available from service probe."

    return {
        "ok": ok,
        "verified_at": verified_at,
        "evidence_ref": evidence_ref,
        "source": "live_ralfia_bridge",
        "reachability": reachability,
        "services": services,
        "ralfia_control_plane": ralfia_control,
        "evolution_amd": evolution,
        "summary": summary,
        "checked_at": verified_at,
    }

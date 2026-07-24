from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from bridge_app.settings import BridgeSettings, get_bridge_settings
from bridge_app.snapshot import build_bridge_status

app = FastAPI(title="LiveOps Read-Only Bridge", version="1.0.0")
_hits: dict[str, list[float]] = defaultdict(list)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _rate_limit(request: Request, settings: BridgeSettings) -> None:
    key = _client_key(request)
    now = time.time()
    window = _hits[key]
    _hits[key] = [t for t in window if now - t < 60.0]
    if len(_hits[key]) >= settings.bridge_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="rate limit")
    _hits[key].append(now)


def _require_bearer(request: Request, settings: BridgeSettings) -> None:
    if not settings.liveops_bridge_token:
        raise HTTPException(status_code=503, detail="bridge token not configured")
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth.split(" ", 1)[1].strip()
    if token != settings.liveops_bridge_token:
        raise HTTPException(status_code=403, detail="invalid bearer token")


@app.get("/")
async def bridge_root() -> dict:
    return {
        "ok": True,
        "service": "liveops-bridge",
        "endpoints": {
            "health": "GET /health (no auth)",
            "status": "GET /liveops-bridge/status (Authorization: Bearer token)",
        },
        "note": "This host is read-only telemetry for Render, not the LiveOps UI.",
    }


@app.get("/health")
async def health(settings: BridgeSettings = Depends(get_bridge_settings)) -> dict:
    return {
        "ok": True,
        "service": "liveops-bridge",
        "token_configured": bool(settings.liveops_bridge_token),
        "dry_run": True,
    }


@app.get("/liveops-bridge/status")
async def liveops_bridge_status(
    request: Request,
    settings: BridgeSettings = Depends(get_bridge_settings),
) -> JSONResponse:
    _rate_limit(request, settings)
    _require_bearer(request, settings)
    body = await build_bridge_status(settings)
    if not body.get("ok"):
        return JSONResponse(status_code=503, content=body)
    return JSONResponse(content=body)


@app.api_route("/liveops-bridge/status", methods=["POST", "PUT", "PATCH", "DELETE"])
async def liveops_bridge_status_mutations() -> None:
    raise HTTPException(status_code=405, detail="method not allowed")


@app.exception_handler(404)
async def not_found(_request: Request, _exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"ok": False, "detail": "not found"})

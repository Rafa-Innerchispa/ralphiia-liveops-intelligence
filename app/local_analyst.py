from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import Settings

OLLAMA_BASE = "http://127.0.0.1:11434"

# Display-only catalog (Rafael's installed set for judges)
AVAILABLE_LOCAL_MODELS: list[str] = [
    "llama3.1:8b",
    "qwen2.5:7b",
    "qwen2.5-coder:7b",
    "qwen2.5:14b-instruct-q4_K_M",
    "phi3.5:3.8b",
    "qwen2.5vl:7b",
]

_PROBE_ORDER = ("phi3.5:3.8b", "llama3.1:8b", "qwen2.5:7b", "qwen2.5-coder:7b")
_probe_cache: dict[str, Any] = {"checked": False, "model": None, "latency_ms": None}


async def _chat_probe(model: str, timeout: float = 25.0) -> tuple[bool, float]:
    t0 = time.perf_counter()
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly: LOCAL_ANALYST_OK",
            }
        ],
        "stream": False,
        "options": {"num_predict": 16},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
            if resp.status_code != 200:
                return False, 0.0
            data = resp.json()
            text = (data.get("message") or {}).get("content") or ""
            ok = "LOCAL_ANALYST_OK" in text or len(text.strip()) > 0
            return ok, (time.perf_counter() - t0) * 1000
    except httpx.HTTPError:
        return False, 0.0


async def resolve_local_analyst_model(settings: Settings) -> dict[str, Any]:
    """Probe once per process; pick first responding model from preferred order."""
    if _probe_cache["checked"]:
        return dict(_probe_cache)
    chosen = None
    latency = None
    for name in _PROBE_ORDER:
        if name not in AVAILABLE_LOCAL_MODELS and name not in (
            "phi3.5:3.8b",
            "llama3.1:8b",
        ):
            continue
        ok, ms = await _chat_probe(name)
        if ok:
            chosen = name
            latency = round(ms, 1)
            break
    _probe_cache.update(
        {
            "checked": True,
            "model": chosen,
            "latency_ms": latency,
            "available": AVAILABLE_LOCAL_MODELS,
            "endpoint": OLLAMA_BASE,
        }
    )
    return dict(_probe_cache)


async def run_local_inference(
    model: str,
    system: str,
    user: str,
    *,
    max_tokens: int = 280,
) -> tuple[str, float]:
    t0 = time.perf_counter()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"num_predict": max_tokens},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{OLLAMA_BASE}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("message") or {}).get("content") or ""
        return text.strip(), (time.perf_counter() - t0) * 1000

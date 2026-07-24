#!/usr/bin/env python3
"""Smoke-check public Render SSE investigate run (audit checklist)."""
from __future__ import annotations

import json
import sys
import urllib.request

URL = "https://ralphiia-liveops-intelligence.onrender.com/api/analyze/stream"
BODY = json.dumps(
    {
        "prompt": "Investigate Evolution API health down with web sources",
        "run_mode": "investigate",
        "session_id": "verify-script",
    }
).encode()


def main() -> int:
    req = urllib.request.Request(
        URL,
        data=BODY,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        method="POST",
    )
    text = urllib.request.urlopen(req, timeout=180).read().decode()
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        ev, data = "message", None
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if data:
            events.append((ev, json.loads(data)))

    failures: list[str] = []
    complete = False
    metrics: dict = {}
    steps: dict = {}
    queries: list[str] = []

    for ev, d in events:
        if ev == "complete":
            complete = True
            result = d.get("result") or {}
            metrics = result.get("metrics") or {}
            rec = result.get("recommendation") or {}
            cc = metrics.get("citation_coverage")
            rc = len(rec.get("citations") or [])
            if cc != rc:
                failures.append(f"citation mismatch metrics={cc} rec={rc}")
            if cc is not None and cc < 1:
                failures.append(f"citation_coverage={cc} (expected >=1 when research live)")
        if ev == "agent_done":
            step = d.get("step") or {}
            steps[step.get("agent")] = step.get("status")
        if ev == "data_flow":
            payload = d.get("payload") or {}
            q = payload.get("query")
            if q:
                queries.append(q)
            if d.get("title", "").startswith("Search OK") and (payload.get("mode") == "mcp_search_error"):
                failures.append("Search OK with mcp_search_error")

    if not complete:
        failures.append("missing event: complete")
    for q in queries:
        if "promptLiveStatus" in q:
            failures.append("promptLiveStatus in query")

    print(json.dumps({"steps": steps, "metrics": metrics, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

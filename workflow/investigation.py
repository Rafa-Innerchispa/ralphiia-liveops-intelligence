"""
Render Workflow task entrypoints (Act 2 long-running path).

Register in Render Dashboard → New → Workflow → Python.
Feature flag: LIVEOPS_RENDER_WORKFLOW=true on web service only after Workflow service exists.

Tasks (Render Workflow names must match):
  gather_context
  research_live_sources
  security_review
  compose_incident
  run_liveops_investigation  # orchestrator entry
"""

from __future__ import annotations

import json
import os
from typing import Any


def gather_context() -> dict[str, Any]:
    return {"step": "gather_context", "ok": True, "note": "stub — wire to session + bridge snapshot"}


def research_live_sources() -> dict[str, Any]:
    return {"step": "research_live_sources", "ok": True, "note": "stub — You.com MCP chain"}


def security_review() -> dict[str, Any]:
    return {"step": "security_review", "ok": True, "note": "stub — Parasail security reviewer"}


def compose_incident() -> dict[str, Any]:
    return {"step": "compose_incident", "ok": True, "note": "stub — draft issue body, no GitHub create"}


def run_liveops_investigation() -> dict[str, Any]:
    steps = [
        gather_context(),
        research_live_sources(),
        security_review(),
        compose_incident(),
    ]
    return {"workflow": "ralphiia-liveops-investigation", "steps": steps, "dry_run": True}


if __name__ == "__main__":
    task = os.environ.get("RENDER_WORKFLOW_TASK", "run_liveops_investigation")
    fn = globals().get(task)
    if not callable(fn):
        raise SystemExit(f"Unknown task: {task}")
    print(json.dumps(fn()))

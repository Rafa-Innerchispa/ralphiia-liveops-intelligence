#!/usr/bin/env python3
"""Sync workshop Step 2 you-com entry into ~/.cursor/mcp.json (reads key from LiveOps .env)."""
from __future__ import annotations

import json
import os
from pathlib import Path

ENV = Path("/home/rlopez/projects/ralphiia-liveops-intelligence/.env")
MCP = Path.home() / ".cursor" / "mcp.json"


def load_key() -> str:
    if not ENV.is_file():
        return ""
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("YDC_API_KEY="):
            return line.split("=", 1)[1].strip()
        if line.startswith("YOUCOM_API_KEY="):
            return line.split("=", 1)[1].strip()
    return os.getenv("YDC_API_KEY", "") or os.getenv("YOUCOM_API_KEY", "")


def main() -> None:
    key = load_key()
    data = json.loads(MCP.read_text()) if MCP.is_file() else {"mcpServers": {}}
    servers = data.setdefault("mcpServers", {})
    entry = {
        "type": "streamable-http",
        "url": "https://api.you.com/mcp",
    }
    if key:
        entry["headers"] = {"Authorization": f"Bearer {key}"}
    servers["you-com"] = entry
    MCP.parent.mkdir(parents=True, exist_ok=True)
    MCP.write_text(json.dumps(data, indent=2) + "\n")
    print("Updated", MCP, "you-com configured:", bool(key))


if __name__ == "__main__":
    main()

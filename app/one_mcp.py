from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings


class OneMcpClient:
    """One hosted MCP — execute_one_action for GitHub (ONE_SECRET required)."""

    PROTOCOL = "2024-11-05"
    MCP_URL = "https://mcp.withone.ai/mcp"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.secret = settings.resolved_one_secret()

    def configured(self) -> bool:
        return bool(self.secret)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.secret}",
        }

    async def _rpc(self, method: str, params: dict | None = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(self.MCP_URL, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result") or {}

    async def initialize(self) -> dict[str, Any]:
        return await self._rpc(
            "initialize",
            {
                "protocolVersion": self.PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "ralphiia-liveops", "version": "0.3.0"},
            },
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self.initialize()
        return await self._rpc(
            "tools/call", {"name": name, "arguments": arguments}
        )

    @staticmethod
    def _text_blocks(result: dict[str, Any]) -> str:
        parts: list[str] = []
        for block in result.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "\n".join(parts)

    async def create_github_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Search GitHub create-issue action and execute via One."""
        search = await self.call_tool(
            "search_one_platform_actions",
            {"platform": "github", "query": "create issue repository"},
        )
        search_text = self._text_blocks(search)
        action_id = _extract_action_id(search_text)
        if not action_id:
            raise RuntimeError(
                "One: could not resolve GitHub create-issue action. "
                "Connect GitHub in One dashboard."
            )
        params: dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "title": title,
            "body": body,
        }
        if labels:
            params["labels"] = labels
        exec_args: dict[str, Any] = {"action_id": action_id, "params": params}
        conn_key = self.settings.resolved_one_github_connection_key()
        if conn_key:
            exec_args["connection_key"] = conn_key
        executed = await self.call_tool(
            "execute_one_action",
            exec_args,
        )
        raw = self._text_blocks(executed)
        parsed = _parse_issue_response(raw)
        parsed["via"] = "one_mcp"
        parsed["action_id"] = action_id
        return parsed


def _extract_action_id(text: str) -> str | None:
    for pattern in (
        r'"action_id"\s*:\s*"([^"]+)"',
        r"action_id[:=]\s*([A-Za-z0-9_\-:]+)",
        r"conn_mod_def:[A-Za-z0-9_\-:]+",
    ):
        m = re.search(pattern, text)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return None


def _parse_issue_response(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {
                "ok": True,
                "number": data.get("number"),
                "html_url": data.get("html_url") or data.get("url"),
                "id": data.get("id"),
                "raw": data,
            }
    except json.JSONDecodeError:
        pass
    url_m = re.search(r"https://github\.com/[^\s\"']+/issues/\d+", text)
    num_m = re.search(r'"number"\s*:\s*(\d+)', text)
    return {
        "ok": bool(url_m),
        "number": int(num_m.group(1)) if num_m else None,
        "html_url": url_m.group(0) if url_m else None,
        "raw_text": text[:2000],
    }

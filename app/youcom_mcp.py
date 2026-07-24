from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings


class YouComMcpClient:
    """You.com remote MCP (Streamable HTTP) — you-search, you-contents, you-research."""

    PROTOCOL = "2024-11-05"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.resolved_youcom_key()
        if self.api_key:
            self.mcp_url = (
                f"{settings.youcom_mcp_url}"
                "?tools=you-search,you-contents,you-research,you-balance"
            )
        else:
            self.mcp_url = f"{settings.youcom_mcp_url}?profile=free"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _rpc(self, method: str, params: dict | None = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                self.mcp_url, json=payload, headers=self._headers()
            )
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
                "clientInfo": {"name": "ralphiia-liveops", "version": "0.1.0"},
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

    async def search(self, query: str, count: int = 5) -> tuple[list[dict], str]:
        mode = "mcp_live" if self.api_key else "mcp_free"
        result = await self.call_tool(
            "you-search",
            {"query": query, "count": count, "freshness": "month"},
        )
        text = self._text_blocks(result)
        hits = _parse_search_text(text)[:count]
        if "Error code: 422" in text or "Failed to perform search" in text:
            return [], "mcp_search_error"
        hits = [
            h
            for h in hits
            if h.get("url")
            and not str(h.get("url")).startswith("https://you.com/docs/welcome")
            and "422" not in str(h.get("snippet") or "")
        ]
        if not hits and text and not text.strip().startswith("MCP error"):
            if "Title:" in text and "URL:" in text:
                hits = _parse_search_text(text)[:count]
        return hits, mode

    async def contents(self, url: str) -> tuple[str, str]:
        if not self.api_key:
            return "[mcp_free] Contents requires API key (you-contents)", "mcp_free"
        result = await self.call_tool(
            "you-contents",
            {"urls": [url], "format": "markdown"},
        )
        text = self._text_blocks(result)
        return text[:4000] or "[empty MCP contents]", "mcp_live"

    async def research(self, query: str) -> tuple[str, list[dict], str]:
        if not self.api_key:
            search_hits, _ = await self.search(query, count=3)
            report = (
                "MCP free tier: you-search only. Add YOUCOM_API_KEY for "
                "you-research via MCP (workshop key from you.com/platform/api-keys)."
            )
            return report, search_hits, "mcp_free"
        result = await self.call_tool("you-research", {"input": str(query)})
        text = self._text_blocks(result)
        if text.startswith("MCP error") or "Input validation error" in text:
            raise RuntimeError(text[:300])
        cites = _parse_search_text(text)
        return text[:3000] or "Research completed.", cites, "mcp_live"

    async def balance(self) -> dict[str, Any]:
        """Workshop Step 3a: tools/call you-balance via https://api.you.com/mcp"""
        if not self.api_key:
            return {"ok": False, "error": "YDC_API_KEY required"}
        result = await self.call_tool("you-balance", {})
        text = self._text_blocks(result)
        balance_usd: float | None = None
        structured = result.get("structuredContent")
        if isinstance(structured, list):
            for item in structured:
                attrs = (item or {}).get("attributes") or {}
                if "balance" in attrs:
                    balance_usd = float(attrs["balance"])
                    break
        if balance_usd is None and "Balance:" in text:
            m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", text)
            if m:
                balance_usd = float(m.group(1))
        return {
            "ok": True,
            "balance_usd": balance_usd,
            "display": text.strip()[:120] if text else None,
            "source": "you-balance-mcp",
        }


def _parse_search_text(text: str) -> list[dict]:
    """Parse You.com MCP search/research text blocks into citation dicts."""
    hits: list[dict] = []
    blocks = re.split(r"\n(?=Title: )", text)
    for block in blocks:
        if "URL:" not in block:
            continue
        title_m = re.search(r"Title:\s*(.+)", block)
        url_m = re.search(r"URL:\s*(\S+)", block)
        desc_m = re.search(r"Description:\s*(.+)", block)
        if not url_m:
            continue
        hits.append(
            {
                "title": (title_m.group(1).strip() if title_m else "Source"),
                "url": url_m.group(1).strip(),
                "snippet": (desc_m.group(1).strip() if desc_m else block[:240]),
            }
        )
    return hits

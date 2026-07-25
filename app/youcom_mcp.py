from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings
from app.provenance import MAX_YOUCOM_SEARCH_CHARS


class YouComMcpClient:
    """You.com remote MCP (Streamable HTTP) — you-search, you-contents, you-research."""

    PROTOCOL = "2024-11-05"
    _TIMEOUT_SEARCH = 35.0
    _TIMEOUT_CONTENTS = 40.0
    _TIMEOUT_RESEARCH = 50.0
    _TIMEOUT_DEFAULT = 60.0

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.resolved_youcom_key()
        self._initialized = False
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

    async def _rpc(
        self, method: str, params: dict | None = None, *, timeout: float | None = None
    ) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {},
        }
        t = timeout if timeout is not None else self._TIMEOUT_DEFAULT
        async with httpx.AsyncClient(timeout=t) as client:
            resp = await client.post(
                self.mcp_url, json=payload, headers=self._headers()
            )
            resp.raise_for_status()
            data = resp.json()
        if "error" in data:
            raise RuntimeError(data["error"])
        return data.get("result") or {}

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        await self._rpc(
            "initialize",
            {
                "protocolVersion": self.PROTOCOL,
                "capabilities": {},
                "clientInfo": {"name": "ralphiia-liveops", "version": "0.1.0"},
            },
            timeout=self._TIMEOUT_DEFAULT,
        )
        self._initialized = True

    async def initialize(self) -> dict[str, Any]:
        await self._ensure_initialized()
        return {"ok": True}

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        await self._ensure_initialized()
        if name == "you-research":
            t = self._TIMEOUT_RESEARCH
        elif name == "you-contents":
            t = self._TIMEOUT_CONTENTS
        elif name == "you-search":
            t = self._TIMEOUT_SEARCH
        else:
            t = self._TIMEOUT_DEFAULT
        return await self._rpc(
            "tools/call", {"name": name, "arguments": arguments}, timeout=t
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
            {"query": query[:MAX_YOUCOM_SEARCH_CHARS], "count": min(count, 5)},
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
        cites = _parse_research_citations(result, text)
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


def _parse_research_citations(result: dict[str, Any], text: str) -> list[dict]:
    """Extract real URLs from you-research MCP (structuredContent + markdown sources)."""
    hits: list[dict] = []
    seen: set[str] = set()

    def add(title: str, url: str, snippet: str = "") -> None:
        u = (url or "").strip().rstrip(".,)")
        if not u.startswith("http://") and not u.startswith("https://"):
            return
        if u in seen or u in ("**", "#"):
            return
        seen.add(u)
        hits.append(
            {
                "title": (title or u).strip()[:200],
                "url": u,
                "snippet": (snippet or "")[:500],
            }
        )

    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        output = structured.get("output") or {}
        if isinstance(output, dict):
            for src in output.get("sources") or []:
                if isinstance(src, dict):
                    add(
                        str(src.get("title") or "Source"),
                        str(src.get("url") or ""),
                        " ".join(src.get("snippets") or [])[:500],
                    )
    elif isinstance(structured, list):
        for item in structured:
            if not isinstance(item, dict):
                continue
            attrs = item.get("attributes") or item
            add(
                str(attrs.get("title") or "Source"),
                str(attrs.get("url") or attrs.get("link") or ""),
                str(attrs.get("snippet") or attrs.get("description") or ""),
            )

    for block in _parse_search_text(text):
        add(block.get("title") or "Source", block.get("url") or "", block.get("snippet") or "")

    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)]+)\)", text):
        add(m.group(1), m.group(2))

    for m in re.finditer(r"(?mi)\*\*URL:\*\*\s*(https?://\S+)", text):
        add("Source", m.group(1))

    for m in re.finditer(r"(?mi)^###\s+\d+\.\s+(.+)\n+\*\*URL:\*\*\s*(https?://\S+)", text):
        add(m.group(1).strip(), m.group(2))

    return hits[:12]


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
        url = url_m.group(1).strip()
        if url in ("**", "#") or not url.startswith("http"):
            continue
        hits.append(
            {
                "title": (title_m.group(1).strip() if title_m else "Source"),
                "url": url,
                "snippet": (desc_m.group(1).strip() if desc_m else block[:240]),
            }
        )
    return hits

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings
from app.youcom_mcp import YouComMcpClient


class YouComClient:
    """You.com via MCP (preferred) or REST fallback."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.resolved_youcom_key()
        self.transport = settings.youcom_transport.lower()
        self._mcp = YouComMcpClient(settings)
        self.mode = "live" if self.api_key else "free_or_fixture"

    def _use_mcp(self) -> bool:
        if self.transport == "mcp":
            return True
        if self.transport == "rest":
            return False
        return True  # auto → MCP first (hackathon default)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {"Accept": "application/json"}
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def search(self, query: str, count: int = 5) -> tuple[list[dict], str]:
        if self._use_mcp():
            try:
                return await self._mcp.search(query, count=count)
            except Exception:
                if not self.api_key:
                    return self._fixture_search(query), "fixture"
        if not self.api_key:
            return self._fixture_search(query), "fixture"
        return await self._search_rest(query, count)

    async def contents(self, url: str) -> tuple[str, str]:
        if self._use_mcp():
            try:
                return await self._mcp.contents(url)
            except Exception:
                if not self.api_key:
                    return f"[fixture] Contents for {url}", "fixture"
        if not self.api_key:
            return f"[fixture] Extracted markdown placeholder for {url}", "fixture"
        return await self._contents_rest(url)

    async def research(self, query: str) -> tuple[str, list[dict], str]:
        if self._use_mcp():
            try:
                return await self._mcp.research(query)
            except Exception:
                if not self.api_key:
                    return self._fixture_research(query)
        if not self.api_key:
            return self._fixture_research(query)
        try:
            return await self._mcp.research(query)
        except Exception:
            return await self._research_rest(query)

    async def _search_rest(self, query: str, count: int) -> tuple[list[dict], str]:
        url = f"{self.settings.youcom_base_url}/v1/search"
        params = {"query": query, "count": count, "freshness": "month"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        results = data.get("results", {}).get("web", []) or data.get("web", [])
        normalized = []
        for item in results[:count]:
            snippet = item.get("description") or item.get("snippet") or ""
            normalized.append(
                {
                    "title": item.get("title") or "Result",
                    "url": item.get("url") or "",
                    "snippet": snippet,
                }
            )
        return normalized, "rest_live"

    async def _contents_rest(self, url: str) -> tuple[str, str]:
        endpoint = f"{self.settings.youcom_base_url}/v1/contents"
        payload = {"urls": [url], "format": "markdown"}
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(endpoint, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        text = ""
        if isinstance(data, dict):
            items = data.get("results") or data.get("contents") or []
            if items:
                text = items[0].get("markdown") or items[0].get("content") or ""
        return text[:4000] or "[empty contents response]", "rest_live"

    async def _research_rest(self, query: str) -> tuple[str, list[dict], str]:
        url = f"{self.settings.youcom_base_url}/v1/research"
        payload = {"input": query, "research_effort": "lite"}
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        report = data.get("output") or data.get("answer") or json.dumps(data)[:3000]
        cites = []
        for src in data.get("sources") or data.get("citations") or []:
            cites.append(
                {
                    "title": src.get("title") or "Source",
                    "url": src.get("url") or "",
                    "snippet": src.get("snippet") or "",
                }
            )
        return report, cites, "rest_live"

    def _fixture_research(self, query: str) -> tuple[str, list[dict], str]:
        cites = self._fixture_search(query)
        report = (
            "Fixture research summary: Evolution API health down while systemd "
            "shows active often indicates session disconnect, blocked number, "
            "or webhook/auth drift — verify read-only before restart."
        )
        return report, cites, "fixture"

    @staticmethod
    def _fixture_search(query: str) -> list[dict]:
        return [
            {
                "title": "Evolution API health check patterns",
                "url": "https://doc.evolution-api.com/",
                "snippet": "Instance state may show connected while health probes fail if QR/session expired.",
            },
            {
                "title": "WhatsApp Business API disconnect causes",
                "url": "https://developers.facebook.com/docs/whatsapp/",
                "snippet": "Number blocks and policy violations prevent session recovery without re-auth.",
            },
            {
                "title": "You.com fixture — " + query[:40],
                "url": "https://you.com/docs/welcome",
                "snippet": "Set YOUCOM_API_KEY for live MCP Search, Research, and Contents.",
            },
        ]

    async def mcp_status(self) -> dict[str, Any]:
        try:
            init = await self._mcp.initialize()
            server = init.get("serverInfo") or {}
            return {
                "connected": True,
                "server": server.get("name"),
                "version": server.get("version"),
                "endpoint": self._mcp.mcp_url.split("?")[0],
                "profile": "authenticated" if self.api_key else "free",
            }
        except Exception as exc:
            return {"connected": False, "error": str(exc)[:200]}

    async def balance(self) -> dict[str, Any]:
        if not self.api_key:
            return {"ok": False, "error": "Set YDC_API_KEY"}
        try:
            return await self._mcp.balance()
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:200]}

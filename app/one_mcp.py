from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


class OneMcpClient:
    """One REST API — GitHub issues via Passthrough (sk_live + connection key).

    Note: https://mcp.withone.ai/mcp is OAuth-only (Cursor). Server keys use
    https://api.withone.ai with header X-One-Secret per One API docs.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.secret = settings.resolved_one_secret()
        self.api_base = settings.resolved_one_api_base().rstrip("/")

    def configured(self) -> bool:
        return bool(self.secret)

    def _headers(self, connection_key: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-One-Secret": self.secret,
        }
        if connection_key:
            headers["X-One-Connection-Key"] = connection_key
        return headers

    async def _passthrough(
        self,
        method: str,
        upstream_path: str,
        *,
        connection_key: str,
        json_body: dict | None = None,
    ) -> Any:
        path = upstream_path.lstrip("/")
        url = f"{self.api_base}/v1/passthrough/{path}"
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method.upper(),
                url,
                headers=self._headers(connection_key),
                json=json_body,
            )
        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise RuntimeError(
                f"One passthrough HTTP {resp.status_code}: {detail}"
            )
        if not resp.content:
            return {}
        try:
            return resp.json()
        except json.JSONDecodeError:
            return {"raw_text": resp.text[:4000]}

    async def create_github_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        conn_key = self.settings.resolved_one_github_connection_key()
        if not conn_key:
            raise RuntimeError(
                "Set ONE_GITHUB_CONNECTION_KEY (One → Connections → GitHub)."
            )
        upstream = f"repos/{quote(owner, safe='')}/{quote(repo, safe='')}/issues"
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        data = await self._passthrough(
            "POST",
            upstream,
            connection_key=conn_key,
            json_body=payload,
        )
        parsed = _parse_issue_response(data if isinstance(data, dict) else {"raw": data})
        parsed["via"] = "one_api_passthrough"
        parsed["upstream_path"] = upstream
        return parsed


def _parse_issue_response(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("html_url") or data.get("number"):
        return {
            "ok": True,
            "number": data.get("number"),
            "html_url": data.get("html_url") or data.get("url"),
            "id": data.get("id"),
            "raw": data,
        }
    raw = json.dumps(data) if isinstance(data, dict) else str(data)
    url_m = re.search(r"https://github\.com/[^\s\"']+/issues/\d+", raw)
    num_m = re.search(r'"number"\s*:\s*(\d+)', raw)
    return {
        "ok": bool(url_m or data.get("number")),
        "number": int(num_m.group(1)) if num_m else data.get("number"),
        "html_url": url_m.group(0) if url_m else data.get("html_url"),
        "raw_text": raw[:2000],
    }

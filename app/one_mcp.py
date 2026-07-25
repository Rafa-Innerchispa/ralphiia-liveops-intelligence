from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings

# One knowledge doc: Create an Issue for a Repository (GitHub)
_DEFAULT_CREATE_ISSUE_ACTION_ID = (
    "conn_mod_def::GJ3ZOgmKVac::6mksPa9nTK-WqE9cw3w6sg"
)


class OneMcpClient:
    """One REST API — GitHub issues via Passthrough + action id (same as One CLI).

    Raw passthrough without x-one-action-id returns secret_middleware_error (400).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.secret = settings.resolved_one_secret()
        self.api_base = settings.resolved_one_api_base().rstrip("/")
        self._v1_base = (
            self.api_base
            if self.api_base.endswith("/v1")
            else f"{self.api_base}/v1"
        )

    def configured(self) -> bool:
        return bool(self.secret)

    def _headers(
        self,
        connection_key: str,
        *,
        action_id: str | None = None,
    ) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream, */*",
            "x-one-secret": self.secret,
            "x-one-connection-key": connection_key,
        }
        if action_id:
            headers["x-one-action-id"] = action_id
        return headers

    async def _api_get(self, path: str, *, params: dict | None = None) -> Any:
        url = f"{self._v1_base}{path}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                url,
                headers={
                    "Accept": "application/json",
                    "x-one-secret": self.secret,
                },
                params=params or {},
            )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"One API HTTP {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json() if resp.content else {}

    async def _resolve_create_issue_action_id(self) -> str:
        override = (
            os.getenv("ONE_GITHUB_CREATE_ISSUE_ACTION_ID", "").strip()
            or os.getenv("ONE_GITHUB_ISSUE_ACTION_ID", "").strip()
        )
        if override:
            return override
        data = await self._api_get(
            "/available-actions/search/github",
            params={
                "query": "Create an Issue for a Repository",
                "limit": "8",
                "executeAgent": "true",
            },
        )
        rows = data if isinstance(data, list) else data.get("rows") or data
        if not isinstance(rows, list):
            rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            method = str(row.get("method") or "").upper()
            name = str(row.get("displayName") or row.get("name") or "").lower()
            if method == "POST" and "create" in name and "issue" in name:
                aid = row.get("_id") or row.get("id")
                if aid:
                    return str(aid)
        return _DEFAULT_CREATE_ISSUE_ACTION_ID

    async def _load_action(self, action_id: str) -> dict[str, Any]:
        data = await self._api_get("/knowledge", params={"_id": action_id})
        rows = data.get("rows") if isinstance(data, dict) else None
        if rows and isinstance(rows, list) and rows:
            return rows[0]
        if isinstance(data, dict) and data.get("path"):
            return data
        raise RuntimeError(f"One action not found: {action_id}")

    @staticmethod
    def _replace_path_variables(path: str, variables: dict[str, str]) -> str:
        if not path:
            return path
        result = path

        def sub(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            val = variables.get(key)
            if val is None or val == "":
                raise ValueError(f"Missing path variable: {key}")
            return quote(str(val), safe="")

        result = re.sub(r"\{\{([^}]+)\}\}", sub, result)
        result = re.sub(r"\{([^}]+)\}", sub, result)
        return result

    async def _execute_passthrough_action(
        self,
        action: dict[str, Any],
        *,
        connection_key: str,
        path_variables: dict[str, str],
        json_body: dict | None,
    ) -> Any:
        action_id = str(action.get("_id") or action.get("id") or "")
        method = str(action.get("method") or "POST").upper()
        raw_path = action.get("path") or ""
        final_path = self._replace_path_variables(str(raw_path), path_variables)
        normalized = final_path if final_path.startswith("/") else f"/{final_path}"
        url = f"{self._v1_base.rsplit('/v1', 1)[0]}/v1/passthrough{normalized}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method,
                url,
                headers=self._headers(connection_key, action_id=action_id or None),
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
        action_id = await self._resolve_create_issue_action_id()
        action = await self._load_action(action_id)
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        data = await self._execute_passthrough_action(
            action,
            connection_key=conn_key,
            path_variables={"owner": owner, "repo": repo},
            json_body=payload,
        )
        parsed = _parse_issue_response(
            data if isinstance(data, dict) else {"raw": data}
        )
        parsed["via"] = "one_api_passthrough"
        parsed["one_action_id"] = action_id
        parsed["upstream_path"] = action.get("path")
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

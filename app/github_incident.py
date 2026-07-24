from __future__ import annotations

from typing import Any

import httpx


async def create_issue(
    owner: str,
    repo: str,
    title: str,
    body: str,
    *,
    token: str,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"GitHub API {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    return {
        "ok": True,
        "via": "github_api",
        "number": data.get("number"),
        "html_url": data.get("html_url"),
        "id": data.get("id"),
        "raw": data,
    }

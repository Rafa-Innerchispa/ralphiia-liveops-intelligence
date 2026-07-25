from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import Settings


class ParasailClient:
    """OpenAI-compatible inference — hackathon sponsor stack (api.parasail.io/v1)."""

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.resolved_parasail_key()
        self.base_url = settings.parasail_base_url.rstrip("/")
        self.model = settings.parasail_model

    def configured(self) -> bool:
        return bool(self.api_key)

    async def list_models(self) -> list[str]:
        if not self.api_key:
            return []
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return [m.get("id", "") for m in data.get("data", []) if m.get("id")][:10]

    async def chat(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 900,
        temperature: float = 0.2,
    ) -> tuple[str, str]:
        """Returns (text, mode) where mode is parasail_live or rules_fallback."""
        if not self.api_key:
            return "", "disabled"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        return text, "parasail_live"

    @staticmethod
    def parse_json_block(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            repaired = re.sub(
                r'"risk_level"\s*:\s*(high|medium|low)\b',
                lambda m: f'"risk_level": "{m.group(1).lower()}"',
                text,
                flags=re.IGNORECASE,
            )
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                return {"raw": text[:2000]}

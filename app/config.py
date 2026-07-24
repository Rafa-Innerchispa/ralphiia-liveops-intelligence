from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    liveops_port: int = 8788
    data_mode: str = "auto"  # auto | live | fixture
    youcom_api_key: str = ""
    youcom_base_url: str = "https://api.you.com"
    youcom_mcp_url: str = "https://api.you.com/mcp"
    youcom_transport: str = "auto"  # auto | mcp | rest
    parasail_api_key: str = ""
    parasail_base_url: str = "https://api.parasail.io/v1"
    parasail_model: str = "parasail-ui-tars-1p5-7b"
    ralfia_status_probe: bool = True
    dry_run: bool = True
    liveops_public_url: str = "https://sworn-profusely-alongside.ngrok-free.dev/liveops"
    liveops_whatsapp_notify: bool = True
    liveops_whatsapp_contact_ref: str = ""
    liveops_whatsapp_number: str = ""
    ralfia_openai_root: str = "/home/rlopez/projects/raphiia-openai"

    def resolved_parasail_key(self) -> str:
        return (
            os.getenv("PARASAIL_API_KEY", "")
            or self.parasail_api_key
        )

    def parasail_status(self) -> dict:
        if self.resolved_parasail_key():
            return {
                "configured": True,
                "base_url": self.parasail_base_url,
                "model": self.parasail_model,
                "human_step": None,
            }
        return {
            "configured": False,
            "base_url": self.parasail_base_url,
            "model": self.parasail_model,
            "human_step": (
                "Create key at https://www.saas.parasail.io/keys → PARASAIL_API_KEY in .env"
            ),
        }

    def resolved_youcom_key(self) -> str:
        return (
            os.getenv("YDC_API_KEY", "")
            or self.youcom_api_key
            or os.getenv("YOUCOM_API_KEY", "")
            or os.getenv("YOU_COM_API_KEY", "")
        )

    def youcom_key_status(self) -> dict:
        key = self.resolved_youcom_key()
        if key:
            return {
                "configured": True,
                "source": "env",
                "mode": "live",
                "human_step": None,
            }
        return {
            "configured": False,
            "source": None,
            "mode": "fixture_or_free_search",
            "human_step": (
                "Export YOUCOM_API_KEY from https://you.com/platform/api-keys into "
                "/home/rlopez/projects/ralphiia-liveops-intelligence/.env "
                "then restart uvicorn. MCP free tier: you-search only at api.you.com/mcp?profile=free"
            ),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()

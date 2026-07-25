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
    ralfia_status_url: str = ""
    ralfia_status_token: str = ""
    github_repo_owner: str = "Rafa-Innerchispa"
    github_repo_name: str = "ralphiia-liveops-intelligence"
    github_token: str = ""
    one_secret: str = ""
    one_github_connection_key: str = ""
    deploy_surface: str = "local"  # local | render

    def resolved_one_secret(self) -> str:
        return os.getenv("ONE_SECRET", "") or self.one_secret

    def resolved_one_github_connection_key(self) -> str:
        return (
            os.getenv("ONE_GITHUB_CONNECTION_KEY", "").strip()
            or self.one_github_connection_key.strip()
        )

    def resolved_github_token(self) -> str:
        return os.getenv("GITHUB_TOKEN", "") or self.github_token

    def ralfia_status_endpoint(self) -> str:
        return (
            os.getenv("RALFIA_STATUS_URL", "").strip()
            or self.ralfia_status_url.strip()
            or "http://127.0.0.1:8101/status"
        )

    def resolved_ralfia_status_token(self) -> str:
        return (
            os.getenv("RALFIA_STATUS_TOKEN", "").strip()
            or os.getenv("LIVEOPS_BRIDGE_TOKEN", "").strip()
            or self.ralfia_status_token.strip()
        )

    def resolved_data_mode(self) -> str:
        return (
            os.getenv("LIVEOPS_DATA_MODE", "").strip().lower()
            or self.data_mode.strip().lower()
            or "auto"
        )

    def deployment_info(self) -> dict:
        return {
            "surface": os.getenv("DEPLOY_SURFACE", self.deploy_surface),
            "ralfia_probe": self.ralfia_status_endpoint().split("?")[0],
            "ralfia_redacted": "127.0.0.1" not in self.ralfia_status_endpoint()
            and "192.168." not in self.ralfia_status_endpoint(),
        }

    def resolved_parasail_key(self) -> str:
        return os.getenv("PARASAIL_API_KEY", "") or self.parasail_api_key

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

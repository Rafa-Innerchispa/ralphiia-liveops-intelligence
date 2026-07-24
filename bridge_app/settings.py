from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BridgeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    liveops_bridge_port: int = 8790
    liveops_bridge_token: str = ""
    ralfia_internal_status_url: str = "http://127.0.0.1:8101/status"
    ralfia_openai_root: str = "/home/rlopez/projects/raphiia-openai"
    bridge_rate_limit_per_minute: int = 120


@lru_cache
def get_bridge_settings() -> BridgeSettings:
    token = (
        os.getenv("LIVEOPS_BRIDGE_TOKEN", "").strip()
        or os.getenv("RALFIA_STATUS_TOKEN", "").strip()
    )
    settings = BridgeSettings()
    if token:
        return settings.model_copy(update={"liveops_bridge_token": token})
    return settings

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings, get_settings
from app.main import reset_liveops_session


def _test_settings() -> Settings:
    return Settings(
        data_mode="fixture",
        youcom_api_key="",
        parasail_api_key="",
        ralfia_status_probe=False,
        ralfia_status_url="",
        ralfia_status_token="",
    )


@pytest.fixture(autouse=True)
def _isolated_liveops_session():
    reset_liveops_session()
    yield
    reset_liveops_session()


@pytest.fixture(autouse=True)
def _deterministic_test_providers(monkeypatch):
    """Avoid live You.com/Parasail/bridge calls in unit tests (fast + stable)."""
    monkeypatch.setenv("LIVEOPS_DATA_MODE", "fixture")
    monkeypatch.setenv("YOUCOM_API_KEY", "")
    monkeypatch.setenv("PARASAIL_API_KEY", "")
    test_settings = _test_settings()
    monkeypatch.setattr("app.config.get_settings", lambda: test_settings)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

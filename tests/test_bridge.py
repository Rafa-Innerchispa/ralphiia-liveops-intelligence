import pytest
from httpx import ASGITransport, AsyncClient

from bridge_app.main import app as bridge_app


@pytest.mark.asyncio
async def test_bridge_health_no_auth():
    transport = ASGITransport(app=bridge_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "liveops-bridge"


@pytest.mark.asyncio
async def test_bridge_status_requires_auth(monkeypatch):
    monkeypatch.setenv("LIVEOPS_BRIDGE_TOKEN", "test-token-123")
    from bridge_app.settings import get_bridge_settings

    get_bridge_settings.cache_clear()
    transport = ASGITransport(app=bridge_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/liveops-bridge/status")
    assert resp.status_code == 401
    get_bridge_settings.cache_clear()


@pytest.mark.asyncio
async def test_bridge_status_wrong_token(monkeypatch):
    monkeypatch.setenv("LIVEOPS_BRIDGE_TOKEN", "good")
    from bridge_app.settings import get_bridge_settings

    get_bridge_settings.cache_clear()
    transport = ASGITransport(app=bridge_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/liveops-bridge/status",
            headers={"Authorization": "Bearer bad"},
        )
    assert resp.status_code == 403
    get_bridge_settings.cache_clear()

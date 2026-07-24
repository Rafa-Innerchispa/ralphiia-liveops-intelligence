import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["dry_run"] is True
    assert "youcom" in data


@pytest.mark.asyncio
async def test_analyze_empty_prompt_uses_default():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/analyze", json={"prompt": "   "})
    assert resp.status_code == 200
    data = resp.json()
    assert "Investigate the current health" in data["user_prompt"]
    assert len(data["steps"]) == 5
    assert "models_used" in data
    assert "models_available" in data


@pytest.mark.asyncio
async def test_analyze_status_only_skips_youcom():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/analyze",
            json={
                "prompt": "What is unhealthy right now on RalfIA status 8101?",
                "run_mode": "status_only",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["youcom_mode"] == "skipped_status_only"
    assert data["metrics"]["web_research_ran"] is False


@pytest.mark.asyncio
async def test_analyze_investigate_forces_web():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/analyze",
            json={"prompt": "check servers", "run_mode": "investigate"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["metrics"]["web_research_ran"] is True


@pytest.mark.asyncio
async def test_analyze_pipeline():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/analyze")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["steps"]) == 5
    assert data["recommendation"]["requires_approval"] is True
    assert data["recommendation"]["dry_run"] is True
    assert data["metrics"]["citation_coverage"] >= 1


@pytest.mark.asyncio
async def test_incident_preview_after_analyze():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/analyze", json={"run_mode": "status_only"})
        resp = await client.post("/api/incident/preview", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "draft" in body
    assert body["draft"]["title"]


@pytest.mark.asyncio
async def test_incident_preview_requires_run():
    from app.main import reset_liveops_session

    reset_liveops_session()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/incident/preview", json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_human_decision_checkpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/analyze")
        resp = await client.post(
            "/api/decision",
            json={"decision": "approve", "note": "test"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["executed"] is False
    assert body["dry_run_checkpoint"] is True


@pytest.mark.asyncio
async def test_analyze_session_and_research_deeper():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post(
            "/api/analyze",
            json={"prompt": "What is unhealthy on RalfIA?", "session_id": "test-sess-1"},
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["session_id"] == "test-sess-1"
        r2 = await client.post(
            "/api/analyze",
            json={
                "prompt": "go deeper",
                "session_id": "test-sess-1",
                "research_deeper": True,
            },
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["metrics"]["web_research_ran"] is True


@pytest.mark.asyncio
async def test_nodes_snapshot():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "models_available_local" in data


@pytest.mark.asyncio
async def test_evals_baseline_vs_multi():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/evals")
    assert resp.status_code == 200
    data = resp.json()
    assert data["baseline"]["unsafe"] is True
    assert data["comparison"]["citation_delta"] >= 1

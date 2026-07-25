import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.render_workflow import reset_workflow_runs_for_tests


@pytest.mark.asyncio
async def test_render_workflow_disabled_by_default():
    reset_workflow_runs_for_tests()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/render-workflow/start", json={"prompt": "test"})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_render_workflow_run_lifecycle(monkeypatch):
    reset_workflow_runs_for_tests()
    monkeypatch.setenv("LIVEOPS_RENDER_WORKFLOW", "true")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post(
            "/api/render-workflow/start",
            json={"prompt": "workflow test", "session_id": "wf-sess"},
        )
        assert r1.status_code == 200
        run_id = r1.json()["run"]["run_id"]
        assert r1.json()["run"]["status"] == "queued"
        for _ in range(30):
            r2 = await client.get(f"/api/render-workflow/runs/{run_id}")
            assert r2.status_code == 200
            st = r2.json()["run"]["status"]
            if st in {"completed", "failed"}:
                break
            import asyncio

            await asyncio.sleep(0.1)
        assert r2.json()["run"]["status"] == "completed"

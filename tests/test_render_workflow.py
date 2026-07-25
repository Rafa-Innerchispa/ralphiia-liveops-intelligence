import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import AgentName, AgentStep
from app.render_workflow import reset_workflow_runs_for_tests
from app import workflow_runner as wr


def _fake_step(agent: AgentName, summary: str) -> AgentStep:
    return AgentStep(
        agent=agent,
        status="completed",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        summary=summary,
    )


@pytest.fixture
def patch_investigation_agents(monkeypatch):
    async def fake_observer(settings, emit=None):
        return _fake_step(AgentName.observer, "observer ok")

    async def fake_research(settings, observer, emit=None, user_prompt="", skip_web=False):
        return _fake_step(AgentName.research, "research ok")

    async def fake_reviewer(settings, observer, research, emit=None):
        return _fake_step(AgentName.security_reviewer, "security ok")

    async def fake_arbitrator(settings, observer, research, reviewer, emit=None):
        step = _fake_step(AgentName.arbitrator, "arbitrator ok")
        step.metadata = {"recommended_action": "Monitor", "confidence": 0.7}
        return step

    monkeypatch.setattr(wr, "run_observer", fake_observer)
    monkeypatch.setattr(wr, "run_research", fake_research)
    monkeypatch.setattr(wr, "run_security_reviewer", fake_reviewer)
    monkeypatch.setattr(wr, "run_arbitrator", fake_arbitrator)


@pytest.mark.asyncio
async def test_render_workflow_disabled_by_default():
    reset_workflow_runs_for_tests()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/render-workflow/start", json={"prompt": "test"})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_render_workflow_run_lifecycle(monkeypatch, patch_investigation_agents):
    reset_workflow_runs_for_tests()
    monkeypatch.setenv("LIVEOPS_RENDER_WORKFLOW", "true")
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    monkeypatch.delenv("RENDER_WORKFLOW_TASK_SLUG", raising=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post(
            "/api/render-workflow/start",
            json={"prompt": "workflow test", "session_id": "wf-sess"},
        )
        assert r1.status_code == 200
        run_id = r1.json()["run"]["run_id"]
        assert r1.json()["run"]["status"] == "queued"
        assert r1.json()["run"]["engine"] == "render_workflow"
        r2 = None
        for _ in range(50):
            r2 = await client.get(f"/api/render-workflow/runs/{run_id}")
            assert r2.status_code == 200
            st = r2.json()["run"]["status"]
            if st in {"completed", "failed"}:
                break
            await asyncio.sleep(0.05)
        assert r2 is not None
        run = r2.json()["run"]
        assert run["status"] == "completed"
        assert len(run["steps"]) == 4
        assert run["steps"][0]["name"] == "gather_context"
        assert run["result"]["run_mode"] == "investigate"


@pytest.mark.asyncio
async def test_workflow_runner_investigate_mode(monkeypatch, patch_investigation_agents):
    from app.config import Settings

    settings = Settings(data_mode="fixture", ralfia_status_probe=False)
    out = await wr.run_liveops_investigation(
        settings,
        session_id="s1",
        prompt="check evolution",
        run_mode="investigate",
    )
    assert out["run_mode"] == "investigate"
    assert len(out["steps"]) == 4
    assert out["recommendation"]["recommended_action"] == "Monitor"


@pytest.mark.asyncio
async def test_remote_workflow_start_uses_render_api(monkeypatch, patch_investigation_agents):
    reset_workflow_runs_for_tests()
    monkeypatch.setenv("LIVEOPS_RENDER_WORKFLOW", "true")
    monkeypatch.setenv("RENDER_API_KEY", "rnd_test")
    monkeypatch.setenv("RENDER_WORKFLOW_TASK_SLUG", "ralphiia-liveops-investigation/run_liveops_investigation")

    post_mock = AsyncMock(
        return_value=type(
            "R",
            (),
            {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"id": "tr-abc"},
            },
        )()
    )
    get_mock = AsyncMock(
        return_value=type(
            "R",
            (),
            {
                "raise_for_status": lambda self: None,
                "json": lambda self: {"id": "tr-abc", "status": "succeeded"},
            },
        )()
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        post = post_mock
        get = get_mock

    monkeypatch.setattr("app.render_workflow.httpx.AsyncClient", FakeClient)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post(
            "/api/render-workflow/start",
            json={"prompt": "remote", "session_id": "rs"},
        )
        assert r1.status_code == 200
        assert r1.json()["run"]["engine"] == "render_workflow_remote"
        run_id = r1.json()["run"]["run_id"]
        for _ in range(30):
            r2 = await client.get(f"/api/render-workflow/runs/{run_id}")
            if r2.json()["run"]["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.05)
        assert r2.json()["run"]["status"] == "completed"
        assert r2.json()["run"]["render_task_run_id"] == "tr-abc"
    assert post_mock.called

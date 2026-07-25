import pytest

from app.config import Settings
from app.one_mcp import OneMcpClient, _parse_issue_response


def test_parse_issue_response_github_shape():
    data = {
        "number": 42,
        "html_url": "https://github.com/org/repo/issues/42",
        "id": 1,
    }
    out = _parse_issue_response(data)
    assert out["ok"] is True
    assert out["number"] == 42
    assert "issues/42" in out["html_url"]


def test_resolved_one_secret_strips_quotes_and_whitespace():
    import os

    os.environ["ONE_SECRET"] = '  "sk_live_test"  '
    try:
        s = Settings()
        assert s.resolved_one_secret() == "sk_live_test"
    finally:
        os.environ.pop("ONE_SECRET", None)


@pytest.mark.asyncio
async def test_create_issue_uses_action_passthrough(monkeypatch):
    settings = Settings(
        one_secret="sk_test_x",
        one_github_connection_key="live::github::default::abc",
        github_repo_owner="o",
        github_repo_name="r",
    )
    client = OneMcpClient(settings)
    captured: dict = {}

    async def fake_resolve():
        return "action-123"

    async def fake_load(aid):
        assert aid == "action-123"
        return {
            "_id": "action-123",
            "method": "POST",
            "path": "/github/repos/{{owner}}/{{repo}}/issues",
        }

    async def fake_execute(action, *, connection_key, path_variables, json_body):
        captured["action"] = action
        captured["connection_key"] = connection_key
        captured["path_variables"] = path_variables
        captured["json_body"] = json_body
        return {"number": 7, "html_url": "https://github.com/o/r/issues/7"}

    monkeypatch.setattr(client, "_resolve_create_issue_action_id", fake_resolve)
    monkeypatch.setattr(client, "_load_action", fake_load)
    monkeypatch.setattr(client, "_execute_passthrough_action", fake_execute)
    out = await client.create_github_issue("o", "r", "t", "b", labels=["liveops-incident"])
    assert out["ok"] is True
    assert out["via"] == "one_api_passthrough"
    assert captured["path_variables"] == {"owner": "o", "repo": "r"}
    assert captured["connection_key"].startswith("live::github")

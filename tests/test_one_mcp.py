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


@pytest.mark.asyncio
async def test_create_issue_uses_passthrough_url(monkeypatch):
    settings = Settings(
        one_secret="sk_test_x",
        one_github_connection_key="live::github::default::abc",
        github_repo_owner="o",
        github_repo_name="r",
    )
    client = OneMcpClient(settings)
    captured: dict = {}

    async def fake_passthrough(method, path, *, connection_key, json_body=None):
        captured["method"] = method
        captured["path"] = path
        captured["connection_key"] = connection_key
        captured["json_body"] = json_body
        return {"number": 7, "html_url": "https://github.com/o/r/issues/7"}

    monkeypatch.setattr(client, "_passthrough", fake_passthrough)
    out = await client.create_github_issue("o", "r", "t", "b", labels=["liveops-incident"])
    assert out["ok"] is True
    assert out["via"] == "one_api_passthrough"
    assert captured["path"] == "github/repos/o/r/issues"
    assert captured["connection_key"].startswith("live::github")

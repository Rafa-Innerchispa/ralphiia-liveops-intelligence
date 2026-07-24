
def test_derive_incident_id_mcp_backlog():
    from app.incident_run import derive_incident_id

    matrix = {
        "up": ["RalfIA gateway"],
        "down": [],
        "degraded": ["RalfIA MCP error backlog — 149 recorded errors"],
    }
    assert derive_incident_id({}, matrix) == "ralfia-mcp-error-backlog"


def test_cited_answer_no_blocked_line_when_healthy():
    from app.incident_run import build_cited_investigate_answer
    from app.models import Citation

    snap = {
        "source": "ralfia_bridge_live",
        "health": "up",
        "system_state": "active",
        "node_label": ".4",
    }
    matrix = {
        "up": ["Evolution API on node .4 — systemd=active, health=up"],
        "down": [],
        "degraded": ["RalfIA MCP error backlog — 149 recorded errors"],
    }
    cites = [
        Citation(title="A", url="https://example.com/a", snippet="x"),
        Citation(title="B", url="https://example.com/b", snippet="y"),
    ]
    text = build_cited_investigate_answer(
        snap, matrix, cites, security_approved=True, security_reasons=[]
    )
    assert "blocked line" not in text.lower()
    assert "What is reachable / observed" in text
    assert "https://example.com/a" in text
    assert "[1]" in text
    assert "good shape" not in text.lower()

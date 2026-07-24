from app.provenance import (
    build_sanitized_research_query,
    canonical_citations,
    sanitize_operator_prompt,
)
from app.models import Citation
from app.ralfia_client import _unavailable_snapshot, _validate_bridge_json
from app.config import Settings


def test_sanitize_rejects_i18n_key():
    assert sanitize_operator_prompt("promptLiveStatus") == ""


def test_research_query_not_contains_i18n_key():
    q = build_sanitized_research_query(
        "promptLiveStatus",
        ["OBSERVED: probe failed"],
        ["DEMO_CONTEXT: demo only"],
    )
    assert "promptLiveStatus" not in q


def test_bridge_ok_false_not_live():
    assert _validate_bridge_json({"source": "live_ralfia_bridge", "ok": False}) is False


def test_unavailable_snapshot_no_fixture_health():
    snap = _unavailable_snapshot(Settings(), reason="HTTP 403")
    assert snap["health"] == "unknown"
    assert snap["system_state"] == "unknown"
    assert "active" not in snap["summary"].lower() or snap["source"] == "live_unavailable"


def test_canonical_citations_dedupes_and_drops_bad_urls():
    raw = [
        Citation(title="A", url="https://example.com/a", snippet="x"),
        Citation(title="B", url="https://example.com/a", snippet="y"),
        Citation(title="Bad", url="**", snippet="z"),
    ]
    out = canonical_citations(raw)
    assert len(out) == 1
    assert out[0].url == "https://example.com/a"

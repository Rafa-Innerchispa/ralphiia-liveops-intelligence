from app.answer_render import (
    dedupe_operator_answer,
    normalize_operator_answer,
    parse_recommended_action,
)


def test_parse_json_recommended_action():
    raw = '{"recommended_action": "• Check bridge\\n• Review logs", "confidence": 0.8}'
    out = parse_recommended_action(raw)
    assert out.startswith("• Check bridge")
    assert "confidence" not in out


def test_dedupe_repeated_bullets():
    text = "• Same\n• Same\n• Other"
    out = dedupe_operator_answer(text)
    assert out.count("Same") == 1
    assert "Other" in out


def test_parse_json_risk_level_unquoted_high():
    from app.parasail_client import ParasailClient

    raw = (
        '{"recommended_action": "Check logs", "confidence": 0.7, '
        '"risk_level": High}'
    )
    parsed = ParasailClient.parse_json_block(raw)
    assert parsed.get("recommended_action") == "Check logs"
    assert parsed.get("risk_level") == "high"


def test_normalize_strips_json_wrapper():
    raw = '{"recommended_action": "Hello world"}'
    assert normalize_operator_answer(raw) == "Hello world"

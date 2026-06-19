from app.services.enrichment import _clamp_score, _parse_json_block


def test_parse_json_block_extracts_json():
    text = 'Here is the result: {"score": 85, "explanation": "Good match"} done.'
    result = _parse_json_block(text)
    assert result["score"] == 85
    assert result["explanation"] == "Good match"


def test_parse_json_block_handles_no_json():
    assert _parse_json_block("No json here") == {}
    assert _parse_json_block("") == {}


def test_parse_json_block_handles_malformed():
    assert _parse_json_block("{invalid}") == {}


def test_clamp_score():
    assert _clamp_score(85) == 85
    assert _clamp_score(0) == 0
    assert _clamp_score(100) == 100
    assert _clamp_score(-5) == 0
    assert _clamp_score(150) == 100
    assert _clamp_score(None) is None
    assert _clamp_score("not a number") is None

from types import SimpleNamespace

import pytest

from app.services.enrichment import EnrichmentService, _clamp_score, _parse_json_block


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


@pytest.mark.asyncio
async def test_score_job_matches_cv_when_anthropic_is_unavailable():
    service = EnrichmentService(SimpleNamespace(anthropic_configured=False))
    job = {
        "title": "Enterprise Architect",
        "description": "TOGAF and Azure enterprise architecture role in London.",
        "job_type": "PERM",
        "parsed_requirements": {"required_skills": ["enterprise architecture", "Azure"]},
    }
    profile = {
        "skills": ["Azure", "TOGAF", "enterprise architecture"],
        "roles": ["Enterprise Architect"],
    }
    result = await service.score_job(job, profile, {"target_titles": ["Enterprise Architect"]})
    assert result["score"] >= 60
    assert "CV" in result["score_explanation"] or "Azure" in result["score_explanation"]


@pytest.mark.asyncio
async def test_score_job_ignores_low_anthropic_numbers(monkeypatch):
    service = EnrichmentService(
        SimpleNamespace(anthropic_configured=True, anthropic_api_key="x", anthropic_model="m")
    )

    async def low_score(prompt):
        return {"score": 15, "explanation": "Empty profile"}

    monkeypatch.setattr(service, "_call_anthropic_json", low_score)
    job = {
        "title": "Solution Architect - Azure Cloud",
        "description": "Azure and enterprise architecture contract.",
        "job_type": "CONTRACT",
        "parsed_requirements": {"keywords": ["Azure", "Solution Architect"]},
    }
    profile = {
        "skills": ["Azure", "enterprise architecture"],
        "contract_delivery_years": 20,
    }
    result = await service.score_job(job, profile, {})
    assert result["score"] >= 60
    assert result["score"] != 15

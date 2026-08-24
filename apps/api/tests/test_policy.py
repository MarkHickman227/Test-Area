from app.models.enums import PolicyDecision
from app.services.policy import PolicyEngine


def test_blocks_minor_terms():
    result = PolicyEngine().evaluate("a teen in a sexual pose, studio lighting")
    assert result.decision == PolicyDecision.BLOCK
    assert any(hit.startswith("minor:") for hit in result.rule_ids)


def test_blocks_celebrity_request():
    result = PolicyEngine().evaluate("celebrity public figure nude portrait")
    assert result.decision == PolicyDecision.BLOCK


def test_blocks_violence():
    result = PolicyEngine().evaluate("non-consensual sexual violence scene")
    assert result.decision == PolicyDecision.BLOCK


def test_holds_ambiguous_age():
    result = PolicyEngine().evaluate("young adult, editorial photography, clearly 25")
    assert result.decision == PolicyDecision.HOLD_FOR_REVIEW


def test_allows_adult_fictional():
    result = PolicyEngine().evaluate(
        "An original fictional adult character, clearly 25 years old, studio portrait"
    )
    assert result.decision == PolicyDecision.ALLOW

from app.services.cv_parser import parse_cv_profile, profile_for_scoring


SAMPLE = """
Mark Hickman
Professional Profile
Enterprise Architecture Leader with Azure, AWS, TOGAF and Prince2.
Over 20 years of contract delivery across Aston Martin and universities.
Professional Experience
Enterprise Architect, AI & Automation Consultant
University of Greenwich Enterprise Architect (Contract)
"""


def test_parse_cv_profile_extracts_skills_and_contract_history():
    profile = parse_cv_profile(SAMPLE)
    assert "Azure" in profile["skills"]
    assert "AWS" in profile["skills"]
    assert "TOGAF" in profile["skills"]
    assert profile["contract_delivery_years"] == 20
    assert "open_to_contract" not in profile
    assert "higher education" in profile["domains"]
    assert profile["raw_text"].startswith("Mark Hickman")


def test_parse_cv_profile_empty():
    assert parse_cv_profile("") == {}
    assert parse_cv_profile("   ") == {}


def test_parse_cv_profile_does_not_fabricate_candidate_attributes():
    profile = parse_cv_profile("Junior developer with Python experience. Permanent roles only.")

    assert "seniority" not in profile
    assert "experience_years" not in profile
    assert "contract_delivery_years" not in profile
    assert "open_to_contract" not in profile


def test_parse_cv_profile_keeps_explicit_contract_preference():
    profile = parse_cv_profile("Solution Architect. Open to contract roles.")

    assert profile["open_to_contract"] is True


def test_profile_for_scoring_uses_raw_text_when_parsed_profile_empty():
    cv = {"parsed_profile": {}, "raw_text": SAMPLE}
    profile = profile_for_scoring(cv)
    assert profile is not None
    assert "Azure" in profile["skills"]
    assert "enterprise architect" in " ".join(profile["roles"]).lower()


def test_profile_for_scoring_rejects_empty_cv():
    assert profile_for_scoring(None) is None
    assert profile_for_scoring({"parsed_profile": {}, "raw_text": ""}) is None

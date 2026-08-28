from app.services.cv_parser import is_complete_profile, parse_cv_profile, profile_for_scoring


SAMPLE = """
Mark Hickman
Professional Profile
Enterprise Architecture Leader with Azure, AWS, TOGAF and Prince2.
Over 20 years of contract delivery across Aston Martin and universities.
Professional Experience
Enterprise Architect, AI & Automation Consultant
University of Greenwich Enterprise Architect (Contract)
Solutions Architect (Contract)
Solutions Architect (Contract)
VW Financial Services
Solutions Architect (Contract)
TOGAF 9.1 Certified.
Prince 2 Certified Project Manager
"""


def test_parse_cv_profile_extracts_skills_and_contract_history():
    profile = parse_cv_profile(SAMPLE)
    assert "Azure" in profile["skills"]
    assert "AWS" in profile["skills"]
    assert "TOGAF" in profile["skills"]
    assert profile["contract_delivery_years"] == 20
    assert "open_to_contract" not in profile
    assert "higher education" in profile["domains"]
    assert "raw_text" not in profile
    assert "Azure" in profile["summary"]
    assert is_complete_profile(profile)


def test_parse_cv_profile_is_complete_not_empty():
    profile = parse_cv_profile(SAMPLE)
    assert profile != {}
    assert profile["roles"] == [
        "Enterprise Architect",
        "AI & Automation Consultant",
        "Solutions Architect",
    ]
    assert "financial services" in profile["domains"]
    assert "TOGAF" in " ".join(profile["certifications"])
    assert profile["seniority"] == "lead"


def test_parse_cv_profile_empty():
    assert parse_cv_profile("") == {}
    assert parse_cv_profile("   ") == {}
    assert not is_complete_profile({})
    assert not is_complete_profile(None)


def test_parse_cv_profile_does_not_fabricate_candidate_attributes():
    profile = parse_cv_profile("Junior developer with Python experience. Permanent roles only.")

    assert "seniority" not in profile
    assert "experience_years" not in profile
    assert "contract_delivery_years" not in profile
    assert "open_to_contract" not in profile
    assert not is_complete_profile(profile)


def test_parse_cv_profile_keeps_explicit_contract_preference():
    profile = parse_cv_profile("Solution Architect. Open to contract roles.")

    assert profile["open_to_contract"] is True
    assert "Solution Architect" in profile["roles"]
    assert is_complete_profile(profile)


def test_profile_for_scoring_replaces_empty_stored_profile():
    cv = {"parsed_profile": {}, "raw_text": SAMPLE}
    profile = profile_for_scoring(cv)
    assert profile is not None
    assert is_complete_profile(profile)
    assert "Azure" in profile["skills"]
    assert "Enterprise Architect" in profile["roles"]
    assert "raw_text" not in profile


def test_profile_for_scoring_rejects_empty_cv():
    assert profile_for_scoring(None) is None
    assert profile_for_scoring({"parsed_profile": {}, "raw_text": ""}) is None

from app.services.job_match import compact_profile, match_job_to_cv


CV = {
    "skills": ["Azure", "AWS", "TOGAF", "enterprise architecture", "solutions architecture"],
    "roles": ["Enterprise Architect", "Solution Architect"],
    "domains": ["automotive", "public sector"],
    "contract_delivery_years": 20,
    "summary": "Enterprise Architecture Leader with Azure and AWS.",
}


def test_match_scores_enterprise_architect_job_from_cv_skills():
    job = {
        "title": "Enterprise Architect - Emergent Technology",
        "location": "London",
        "job_type": "PERM",
        "description": "Lead enterprise architecture and technology strategy in London.",
        "parsed_requirements": {
            "required_skills": ["enterprise architecture", "technology strategy"],
            "keywords": ["enterprise architect", "TOGAF"],
        },
    }
    prefs = {"target_titles": ["Enterprise Architect"], "locations": ["London"]}
    result = match_job_to_cv(job, CV, prefs)
    assert result["score"] >= 60
    assert "enterprise architecture" in result["score_explanation"].lower() or "Enterprise Architect" in result["score_explanation"]


def test_match_scores_azure_contract_solution_architect():
    job = {
        "title": "Solution Architect - Azure Cloud",
        "location": "Remote UK",
        "job_type": "CONTRACT",
        "description": "Azure cloud architecture and enterprise architecture governance for financial services.",
        "parsed_requirements": {
            "required_skills": ["Azure cloud architecture", "enterprise architecture"],
            "keywords": ["Azure", "Solution Architect"],
        },
    }
    result = match_job_to_cv(job, CV, {"target_titles": ["Solutions Architect"], "locations": ["Remote UK"]})
    assert result["score"] >= 60
    assert "Azure" in result["strengths"]


def test_match_penalises_sales_account_director():
    job = {
        "title": "Enterprise Account Director (Strategic Accounts) – UK",
        "location": "Greater London",
        "job_type": "PERM",
        "description": "Uncapped commission, enterprise account management and sales leadership.",
        "parsed_requirements": {
            "required_skills": ["Enterprise account management", "Sales leadership"],
        },
    }
    result = match_job_to_cv(job, CV, {"target_titles": ["Enterprise Architect"]})
    assert result["score"] < 50


def test_match_without_cv_does_not_invent_a_score():
    result = match_job_to_cv({"title": "Enterprise Architect"}, None)
    assert result["score"] is None


def test_compact_profile_drops_raw_cv_text():
    compact = compact_profile({**CV, "raw_text": "x" * 8000, "summary": "EA leader"})
    assert "raw_text" not in compact
    assert compact["skills"][0] == "Azure"
    assert compact["summary"] == "EA leader"

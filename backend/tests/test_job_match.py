from app.services.cv_parser import profile_for_scoring
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


AZURE_FS_CONTRACT = {
    "title": "Solution Architect - Azure Cloud",
    "company": "Financial services organisation via Sanderson",
    "location": "Remote UK",
    "job_type": "CONTRACT",
    "description": (
        "Contract Solution Architect role in a financial services cloud transformation "
        "programme. Responsible for designing and governing end-to-end solutions aligned "
        "to enterprise architecture and regulatory requirements."
    ),
    "parsed_requirements": {
        "keywords": [
            "Solution Architect",
            "Azure",
            "Cloud",
            "Financial services",
            "Enterprise architecture",
            "Governance",
            "Regulatory",
            "Transformation",
            "Contract",
            "Design",
        ],
        "seniority": "senior",
        "certifications": [
            "Microsoft Azure Solutions Architect Expert",
            "Azure Administrator Certified",
        ],
        "required_skills": [
            "Azure cloud architecture",
            "Solution design",
            "Enterprise architecture",
            "Cloud governance",
            "Regulatory compliance",
            "Technical leadership",
            "Stakeholder management",
        ],
        "domain_knowledge": [
            "Financial services",
            "Cloud transformation",
            "Regulatory compliance",
            "Enterprise systems",
            "Digital transformation",
        ],
        "experience_years": 8,
        "nice_to_have_skills": [
            "Multi-cloud experience",
            "Infrastructure as Code",
            "DevOps practices",
            "Security architecture",
            "Cost optimization",
            "Migration strategy",
        ],
    },
}


AZURE_FS_PREFS = {
    "target_titles": ["Enterprise Architect", "Solutions Architect", "CTO"],
    "locations": ["London", "Remote UK"],
    "salary_min": 80000,
    "salary_max": 160000,
    "job_types": ["PERM", "CONTRACT"],
    "industries": ["Financial Services", "Technology"],
}

EMPTY_PROFILE_EXPLANATION = "the candidate profile is essentially empty"


def test_live_azure_fs_contract_is_a_good_cv_fit_not_empty_profile():
    """Regression: live job 4708a681 was scored 15 with 'profile is essentially empty'."""
    result = match_job_to_cv(AZURE_FS_CONTRACT, CV, AZURE_FS_PREFS)
    assert result["score"] >= 60
    assert result["score"] != 15
    assert EMPTY_PROFILE_EXPLANATION not in result["score_explanation"].lower()
    assert "empty" not in result["score_explanation"].lower()
    assert "Azure" in result["strengths"]
    assert "solution architect" in " ".join(result["strengths"]).lower()


def test_empty_stored_profile_still_matches_live_azure_job_from_cv_text():
    """Same live job, same stored-CV bug: parsed_profile was {}."""
    cv_row = {
        "parsed_profile": {},
        "raw_text": (
            "Mark Hickman\nProfessional Profile\n"
            "Enterprise Architecture Leader with Azure, AWS, TOGAF and Prince2.\n"
            "Over 20 years of contract delivery.\n"
            "Professional Experience\nEnterprise Architect, Solution Architect\n"
            "VW Financial Services\nSolutions Architect (Contract)\n"
        ),
    }
    profile = profile_for_scoring(cv_row)
    result = match_job_to_cv(AZURE_FS_CONTRACT, profile, AZURE_FS_PREFS)
    assert profile is not None
    assert "Azure" in profile["skills"]
    assert "raw_text" not in profile
    assert "financial services" in profile["domains"]
    assert result["score"] >= 60
    assert result["score"] != 15
    assert EMPTY_PROFILE_EXPLANATION not in result["score_explanation"].lower()
    assert "empty" not in result["score_explanation"].lower()
    assert "Azure" in result["strengths"]
    assert "financial services" in result["score_explanation"].lower()


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


def test_match_treats_typical_search_listing_as_apply_ready():
    job = {
        "title": "Solutions Architect",
        "location": "London",
        "job_type": "PERM",
        "description": "London hybrid solutions architect posting.",
        "parsed_requirements": {},
    }
    result = match_job_to_cv(job, CV, {"target_titles": ["Solutions Architect"], "locations": ["London"]})
    assert result["score"] >= 60


def test_match_without_cv_does_not_invent_a_score():
    result = match_job_to_cv({"title": "Enterprise Architect"}, None)
    assert result["score"] is None


def test_compact_profile_drops_raw_cv_text():
    compact = compact_profile({**CV, "raw_text": "x" * 8000, "summary": "EA leader"})
    assert "raw_text" not in compact
    assert compact["skills"][0] == "Azure"
    assert compact["summary"] == "EA leader"

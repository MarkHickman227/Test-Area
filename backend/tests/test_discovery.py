from app.services.discovery import DiscoveryService


def test_parse_results_extracts_jobs():
    service = DiscoveryService.__new__(DiscoveryService)
    raw = """Here are some jobs:
    [
        {"title": "Enterprise Architect", "company": "Acme Corp",
         "location": "London", "salary_text": "£80,000 - £120,000",
         "description": "Lead architecture team", "source_url": "https://indeed.com/j/123",
         "job_type": "PERM"},
        {"title": "Solutions Architect", "company": "XYZ Recruitment",
         "location": "Manchester", "salary_text": "",
         "description": "On behalf of our client, seeking a SA",
         "source_url": "https://indeed.com/j/456", "job_type": "contract"}
    ]
    Some trailing text."""

    jobs = service._parse_results(raw)
    assert len(jobs) == 2
    assert jobs[0]["title"] == "Enterprise Architect"
    assert jobs[0]["salary_min"] == 80000
    assert jobs[0]["salary_max"] == 120000
    assert jobs[0]["job_type"] == "PERM"
    assert jobs[0]["agency"] is False

    assert jobs[1]["title"] == "Solutions Architect"
    assert jobs[1]["job_type"] == "CONTRACT"
    assert jobs[1]["agency"] is True


def test_parse_results_handles_empty_response():
    service = DiscoveryService.__new__(DiscoveryService)
    assert service._parse_results("No results found") == []
    assert service._parse_results("") == []


def test_parse_results_handles_malformed_json():
    service = DiscoveryService.__new__(DiscoveryService)
    assert service._parse_results("[{invalid json}]") == []


def test_infer_job_type_from_explicit():
    assert DiscoveryService._infer_job_type("PERM", "") == "PERM"
    assert DiscoveryService._infer_job_type("permanent", "") == "PERM"
    assert DiscoveryService._infer_job_type("contract", "") == "CONTRACT"
    assert DiscoveryService._infer_job_type("freelance", "") == "CONTRACT"


def test_infer_job_type_from_description():
    assert DiscoveryService._infer_job_type("", "This is a permanent full-time role") == "PERM"
    assert DiscoveryService._infer_job_type("", "6 month contract position") == "CONTRACT"
    assert DiscoveryService._infer_job_type("", "Some vague description") is None


def test_parse_salary():
    assert DiscoveryService._parse_salary("£80,000 - £120,000") == {"salary_min": 80000, "salary_max": 120000}
    assert DiscoveryService._parse_salary("$100000") == {"salary_min": 100000, "salary_max": None}
    assert DiscoveryService._parse_salary("") == {"salary_min": None, "salary_max": None}
    assert DiscoveryService._parse_salary("Competitive") == {"salary_min": None, "salary_max": None}
    assert DiscoveryService._parse_salary(None) == {"salary_min": None, "salary_max": None}
    assert DiscoveryService._parse_salary("£90,000 - , DOE") == {"salary_min": 90000, "salary_max": None}
    assert DiscoveryService._parse_salary(",") == {"salary_min": None, "salary_max": None}

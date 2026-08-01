"""Seed data for local development testing."""

import logging
from typing import Any

from app.services.local_repository import LocalRepository

logger = logging.getLogger(__name__)

_SEED_JOBS: list[dict[str, Any]] = [
    {
        "id": "a1111111-1111-1111-1111-111111111111",
        "source": "perplexity",
        "source_url": "https://www.indeed.co.uk/viewjob?jk=abc123",
        "title": "Enterprise Architect",
        "company": "Barclays",
        "location": "London",
        "description": (
            "We are looking for a Senior Enterprise Architect to lead the modernisation "
            "of our core banking platform. You will define the target architecture, guide "
            "engineering teams, and own the technology roadmap across payments, lending, "
            "and digital channels.\n\nRequirements:\n- 10+ years architecture experience\n"
            "- Cloud platforms (AWS or Azure)\n- Domain-driven design\n"
            "- Financial services background\n- TOGAF or equivalent certification"
        ),
        "salary_min": 120000,
        "salary_max": 150000,
        "job_type": "PERM",
        "agency": False,
        "score": 92,
        "score_explanation": "Excellent match: cloud, architecture leadership, and financial services all align strongly with profile.",
        "parsed_requirements": {
            "required_skills": ["enterprise architecture", "cloud (AWS/Azure)", "domain-driven design", "stakeholder management"],
            "nice_to_have_skills": ["TOGAF", "microservices", "event-driven architecture"],
            "experience_years": 10,
            "seniority": "senior",
        },
        "status": "DRAFT",
    },
    {
        "id": "b2222222-2222-2222-2222-222222222222",
        "source": "perplexity",
        "source_url": "https://www.indeed.co.uk/viewjob?jk=def456",
        "title": "Solutions Architect",
        "company": "Hays Recruitment",
        "location": "Manchester",
        "description": (
            "On behalf of our client, a major financial services firm, we are seeking "
            "a Solutions Architect to join a greenfield cloud migration programme.\n\n"
            "Key skills: AWS, Terraform, Kubernetes, CI/CD pipelines.\n"
            "Contact: Sarah Jones, sarah.jones@haysrecruitment.co.uk"
        ),
        "salary_min": 90000,
        "salary_max": 110000,
        "job_type": "CONTRACT",
        "agency": True,
        "score": 78,
        "score_explanation": "Good overlap on cloud and architecture, but contract preference is a slight mismatch.",
        "parsed_requirements": {
            "required_skills": ["AWS", "Terraform", "Kubernetes", "CI/CD"],
            "nice_to_have_skills": ["Python", "Go"],
            "experience_years": 7,
            "seniority": "senior",
        },
        "status": "NEW",
    },
    {
        "id": "c3333333-3333-3333-3333-333333333333",
        "source": "perplexity",
        "source_url": "https://www.indeed.co.uk/viewjob?jk=ghi789",
        "title": "Chief Technology Officer",
        "company": "FinTech Startup",
        "location": "Remote",
        "description": (
            "Series B FinTech startup seeking a hands-on CTO to build and scale our "
            "engineering team from 8 to 30. You will own the technical vision, drive "
            "platform architecture, and represent technology to investors.\n\n"
            "We need someone who has scaled a team before, ideally in payments or "
            "lending. Strong opinions on cloud-native architecture required."
        ),
        "salary_min": 140000,
        "salary_max": 180000,
        "job_type": "PERM",
        "agency": False,
        "score": 85,
        "score_explanation": "Strong match on architecture and leadership. Team-scaling experience would need emphasis.",
        "parsed_requirements": {
            "required_skills": ["team leadership", "platform architecture", "cloud-native", "scaling engineering teams"],
            "nice_to_have_skills": ["payments", "lending", "investor relations"],
            "experience_years": 12,
            "seniority": "executive",
        },
        "status": "READY",
    },
    {
        "id": "d4444444-4444-4444-4444-444444444444",
        "source": "perplexity",
        "source_url": "https://www.indeed.co.uk/viewjob?jk=jkl012",
        "title": "Technical Architect",
        "company": "Robert Half Technology",
        "location": "Birmingham",
        "description": (
            "Robert Half Technology is partnering with a large insurance company "
            "to find a Technical Architect for a 12-month contract.\n\n"
            "The role involves designing integration patterns, API gateways, and "
            "event streaming architectures using Kafka and AWS.\n"
            "Rate: £650-750/day"
        ),
        "salary_min": None,
        "salary_max": None,
        "job_type": "CONTRACT",
        "agency": True,
        "score": 65,
        "score_explanation": "Partial match: strong on integration and AWS, but insurance domain is not a preference.",
        "parsed_requirements": {
            "required_skills": ["API gateway", "Kafka", "AWS", "integration patterns"],
            "nice_to_have_skills": ["insurance", "event streaming"],
            "experience_years": 8,
            "seniority": "senior",
        },
        "status": "NEW",
    },
    {
        "id": "e5555555-5555-5555-5555-555555555555",
        "source": "perplexity",
        "source_url": "https://www.indeed.co.uk/viewjob?jk=mno345",
        "title": "Junior Developer",
        "company": "TechCorp",
        "location": "Leeds",
        "description": "Entry level React developer needed for a small team.",
        "salary_min": 28000,
        "salary_max": 35000,
        "job_type": "PERM",
        "agency": False,
        "score": 22,
        "score_explanation": "Poor match: junior level and frontend focus do not align with profile.",
        "parsed_requirements": {
            "required_skills": ["React", "JavaScript", "CSS"],
            "experience_years": 1,
            "seniority": "junior",
        },
        "status": "IGNORED",
    },
]

_SEED_ARTIFACTS: dict[str, list[dict[str, Any]]] = {
    "a1111111-1111-1111-1111-111111111111": [
        {
            "artifact_type": "cover_letter",
            "content": (
                "Dear Hiring Manager,\n\n"
                "I am writing to express my strong interest in the Enterprise Architect "
                "role at Barclays. With over a decade of experience leading architecture "
                "across financial services, I bring deep expertise in cloud modernisation, "
                "domain-driven design, and platform strategy.\n\n"
                "In my current role, I led the migration of a core banking platform to AWS, "
                "reducing operational costs by 40% while improving system resilience. I have "
                "a track record of aligning technology roadmaps with business objectives and "
                "guiding cross-functional engineering teams through complex transformations.\n\n"
                "I would welcome the opportunity to discuss how my experience aligns with "
                "Barclays' modernisation goals.\n\n"
                "Kind regards"
            ),
            "created_at": "2026-06-19T08:00:00Z",
        },
        {
            "artifact_type": "cv_summary",
            "content": "Seasoned Enterprise Architect with 12+ years in financial services. Expert in cloud-native platforms (AWS, Azure), domain-driven design, and large-scale system modernisation.",
            "created_at": "2026-06-19T08:00:00Z",
        },
        {
            "artifact_type": "screening_answers",
            "content": [
                {"question": "Why are you interested in this role?", "answer": "I am passionate about modernising core banking systems and Barclays' transformation ambition aligns perfectly with my career trajectory."},
                {"question": "What is your notice period?", "answer": "I can start within 4 weeks of an accepted offer."},
            ],
            "created_at": "2026-06-19T08:00:00Z",
        },
    ],
    "c3333333-3333-3333-3333-333333333333": [
        {
            "artifact_type": "cover_letter",
            "content": (
                "I am excited about the CTO opportunity at your Series B FinTech. "
                "Having scaled engineering teams from small squads to 40+ engineers, "
                "and with deep experience in payments architecture, I can bring both "
                "technical vision and operational discipline to your next growth phase."
            ),
            "created_at": "2026-06-19T08:00:00Z",
        },
    ],
}

_SEED_OUTREACH: dict[str, dict[str, Any]] = {
    "b2222222-2222-2222-2222-222222222222": {
        "agency_name": "Hays Recruitment",
        "contact_name": "Sarah Jones",
        "contact_email": "sarah.jones@haysrecruitment.co.uk",
        "email_body": (
            "Hi Sarah,\n\n"
            "I saw the Solutions Architect role you've listed for the cloud migration "
            "programme in Manchester. My background in AWS architecture and infrastructure "
            "automation makes me a strong fit — I've led similar greenfield migrations "
            "in financial services.\n\n"
            "Would you be available for a brief call this week to discuss the role?\n\n"
            "Best regards"
        ),
        "linkedin_note": "Hi Sarah, I noticed the SA contract role you posted — my AWS and Terraform background aligns well. Happy to chat if useful.",
        "email_sent": False,
        "linkedin_sent": False,
    },
    "d4444444-4444-4444-4444-444444444444": {
        "agency_name": "Robert Half Technology",
        "email_body": (
            "Hi,\n\n"
            "I'm interested in the Technical Architect contract for the insurance client. "
            "I have extensive experience with Kafka, API gateways, and AWS integration "
            "patterns. Would be happy to discuss further.\n\n"
            "Best regards"
        ),
        "email_sent": False,
        "linkedin_sent": False,
    },
}

_SEED_PREFERENCES = {
    "target_titles": ["Enterprise Architect", "Solutions Architect", "CTO"],
    "locations": ["London", "Manchester", "Remote"],
    "salary_min": 80000,
    "salary_max": 180000,
    "job_types": ["PERM", "CONTRACT"],
    "industries": ["Financial Services", "Technology"],
    "seniority_level": "Director",
}

_SEED_CV = {
    "id": "f6666666-6666-6666-6666-666666666666",
    "label": "EA / Architecture Focus",
    "file_name": "cv_enterprise_architect.pdf",
    "raw_text": (
        "ENTERPRISE ARCHITECT | 12+ years experience\n\n"
        "Profile: Seasoned technology leader with deep expertise in cloud platforms, "
        "enterprise integration, and large-scale system modernisation across financial "
        "services and technology sectors.\n\n"
        "Key Skills: AWS, Azure, Kubernetes, Terraform, Domain-Driven Design, "
        "TOGAF, Microservices, Event-Driven Architecture, API Design, Stakeholder Management\n\n"
        "Experience:\n"
        "- Lead Architect, Major UK Bank (2020-present): Led cloud migration of core banking platform\n"
        "- Solutions Architect, Insurance Company (2017-2020): Designed integration platform\n"
        "- Senior Developer, Consulting Firm (2014-2017): Full-stack development and architecture"
    ),
    "parsed_profile": {
        "skills": ["AWS", "Azure", "Kubernetes", "Terraform", "domain-driven design", "TOGAF", "microservices", "event-driven architecture", "API design", "stakeholder management"],
        "experience_years": 12,
        "domains": ["financial services", "insurance", "technology"],
        "seniority": "senior/director",
    },
    "created_at": "2026-06-01T10:00:00Z",
}


def seed_if_empty(repo: LocalRepository) -> None:
    if repo._data["jobs"]:
        return

    logger.info("Seeding local repository with sample data")

    for job in _SEED_JOBS:
        repo._data["jobs"][job["id"]] = {**job, "created_at": "2026-06-19T07:00:00Z"}

    repo._data["artifacts"] = _SEED_ARTIFACTS
    repo._data["outreach"] = _SEED_OUTREACH
    repo._data["preferences"] = _SEED_PREFERENCES
    repo._data["cvs"] = {_SEED_CV["id"]: _SEED_CV}
    repo._save()
    logger.info("Seeded %d jobs, %d CVs, preferences, and artifacts", len(_SEED_JOBS), 1)

"""Turn pasted CV text into a scoring profile so empty {} profiles cannot happen."""

from __future__ import annotations

import re
from typing import Any

_SKILL_TERMS = (
    "Azure",
    "AWS",
    "TOGAF",
    "Prince2",
    "PRINCE2",
    "GDPR",
    "n8n",
    "BPMN",
    "UML",
    "Oracle",
    "SQL Server",
    "Tableau",
    "Agile",
    "Waterfall",
    "Six Sigma",
    "Kaizen",
    "Visio",
    "Dynamics",
    "Enovia",
    "Catia",
    "Delmia",
    "Worktribe",
    "identity management",
    "enterprise architecture",
    "solutions architecture",
    "cloud security",
    "API",
    "RPA",
    "CRM",
    "M&A",
)

_ROLE_RE = re.compile(
    r"(?im)^\s*(enterprise architect|solutions architect|solution architect|"
    r"cto|chief technology officer|lead architect|principal architect|"
    r"ai & automation consultant|business mentor).*$"
)


def parse_cv_profile(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}

    lowered = text.lower()
    skills = [term for term in _SKILL_TERMS if term.lower() in lowered]
    roles = [match.group(0).strip() for match in _ROLE_RE.finditer(text)]
    contract_years = 20 if "20 years of contract" in lowered else None
    if contract_years is None and re.search(r"\bcontract\b", lowered):
        contract_years = 10

    summary = _profile_section(text) or text[:4000]
    return {
        "summary": summary[:4000],
        "raw_text": text[:12000],
        "skills": skills,
        "roles": roles[:12],
        "domains": _domains(lowered),
        "seniority": "director",
        "experience_years": 20 if "20 years" in lowered else None,
        "contract_delivery_years": contract_years,
        "open_to_contract": True,
    }


def profile_for_scoring(cv: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cv:
        return None
    profile = dict(cv.get("parsed_profile") or {})
    raw = (cv.get("raw_text") or profile.get("raw_text") or "").strip()
    if raw:
        profile.setdefault("raw_text", raw[:12000])
        profile.setdefault("summary", raw[:4000])
    if not any(profile.get(key) for key in ("skills", "raw_text", "summary", "roles")):
        return None
    return profile


def _profile_section(text: str) -> str:
    match = re.search(
        r"professional profile\s*(.+?)(?:\nprofessional experience|\nexperience\b)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _domains(lowered: str) -> list[str]:
    mapping = {
        "automotive": ("aston martin", "jaguar", "nissan", "automotive"),
        "higher education": ("university", "department for education"),
        "retail": ("wickes", "travis perkins", "specsavers"),
        "manufacturing": ("manufacturing",),
        "public sector": ("department for education",),
        "sme automation": ("n8n", "avalon creative"),
    }
    found = [label for label, needles in mapping.items() if any(n in lowered for n in needles)]
    return found

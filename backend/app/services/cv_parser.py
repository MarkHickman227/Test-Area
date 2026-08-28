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
    r"technology director|it director|architecture director|"
    r"ai & automation consultant|business mentor).*$"
)

_CONTRACT_YEARS_RE = re.compile(
    r"(?i)\b(?:over|more than)?\s*(\d{1,2})\+?\s+years?\s+(?:of\s+)?"
    r"(?:[a-z-]+\s+){0,3}(?:contract|contracting|freelance)\b"
)

_EXPERIENCE_YEARS_RE = re.compile(
    r"(?i)\b(?:over|more than)?\s*(\d{1,2})\+?\s+years?\s+(?:of\s+)?"
    r"(?:professional\s+)?experience\b"
)

_OPEN_TO_CONTRACT_RE = re.compile(
    r"(?i)\b(?:open to|seeking|looking for|available for)\s+"
    r"(?:new\s+)?(?:contract|contracting|freelance)(?:\s+(?:roles?|work|opportunities))?\b"
)


def parse_cv_profile(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}

    lowered = text.lower()
    skills = [term for term in _SKILL_TERMS if term.lower() in lowered]
    roles = [match.group(0).strip() for match in _ROLE_RE.finditer(text)]
    summary = _profile_section(text) or text[:4000]
    profile: dict[str, Any] = {
        "summary": summary[:4000],
        "raw_text": text[:12000],
        "skills": skills,
        "roles": roles[:12],
        "domains": _domains(lowered),
    }

    seniority = _seniority(roles)
    if seniority:
        profile["seniority"] = seniority

    experience_match = _EXPERIENCE_YEARS_RE.search(text)
    if experience_match:
        profile["experience_years"] = int(experience_match.group(1))

    contract_match = _CONTRACT_YEARS_RE.search(text)
    if contract_match:
        profile["contract_delivery_years"] = int(contract_match.group(1))

    if _OPEN_TO_CONTRACT_RE.search(text):
        profile["open_to_contract"] = True

    return profile


def profile_for_scoring(cv: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cv:
        return None
    profile = dict(cv.get("parsed_profile") or {})
    raw = (cv.get("raw_text") or profile.get("raw_text") or "").strip()
    skills_or_roles = profile.get("skills") or profile.get("roles")
    # Live jobs were scored 0–25 with "profile is essentially empty" when
    # parsed_profile was {}. Rebuild skills/roles from the uploaded CV text.
    if raw and not skills_or_roles:
        parsed = parse_cv_profile(raw)
        if parsed:
            return parsed
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


def _seniority(roles: list[str]) -> str | None:
    role_text = " ".join(roles).lower()
    if re.search(r"\b(?:cto|chief technology officer)\b", role_text):
        return "executive"
    if re.search(r"\b(?:technology|it|architecture) director\b", role_text):
        return "director"
    if re.search(r"\b(?:lead|principal) architect\b", role_text):
        return "lead"
    return None

"""Turn uploaded CV text into a complete scoring profile. Empty {} is not a profile."""

from __future__ import annotations

import re
from typing import Any

_SKILL_TERMS = (
    "Azure",
    "AWS",
    "hybrid cloud",
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
    "data lake",
    "single sign-on",
    "SAP",
    "API",
    "RPA",
    "CRM",
    "M&A",
)

_ROLE_TITLE_RE = re.compile(
    r"(?i)\b(enterprise architect|solutions architect|solution architect|"
    r"data architect|chief technology officer|cto|lead architect|"
    r"principal architect|technology director|it director|"
    r"architecture director|ai & automation consultant|business mentor|"
    r"project manager)\b"
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

_CERT_RE = re.compile(
    r"(?i)\b(TOGAF(?:\s*[\d.]+)?|Prince\s*2|PRINCE2)(?:\s+certified(?:\s+project manager)?)?\b"
)


def parse_cv_profile(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}

    lowered = text.lower()
    skills = [term for term in _SKILL_TERMS if term.lower() in lowered]
    roles = _roles(text)
    summary = _profile_section(text) or re.sub(r"\s+", " ", text)[:4000]
    profile: dict[str, Any] = {
        "summary": summary[:4000],
        "skills": skills,
        "roles": roles,
        "domains": _domains(lowered),
        "certifications": _certifications(text),
    }

    seniority = _seniority(roles, text)
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


def is_complete_profile(profile: dict[str, Any] | None) -> bool:
    if not profile:
        return False
    skills = [s for s in (profile.get("skills") or []) if str(s).strip()]
    roles = [r for r in (profile.get("roles") or []) if str(r).strip()]
    summary = (profile.get("summary") or "").strip()
    return bool(skills or roles) and bool(summary)


def profile_for_scoring(cv: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cv:
        return None
    raw = (cv.get("raw_text") or "").strip()
    stored = dict(cv.get("parsed_profile") or {})
    parsed = parse_cv_profile(raw) if raw else {}
    if is_complete_profile(parsed):
        return parsed
    if is_complete_profile(stored):
        return stored
    return None


def _roles(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _ROLE_TITLE_RE.finditer(text):
        prefix = text[max(0, match.start() - 24) : match.start()].lower()
        if "certified" in prefix:
            continue
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        key = title.lower().replace("solutions architect", "solution architect")
        if key in {"cto"}:
            title = "CTO"
            key = "cto"
        if key in seen:
            continue
        seen.add(key)
        found.append(title)
    return found[:12]


def _certifications(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _CERT_RE.finditer(text):
        label = re.sub(r"\s+", " ", match.group(1)).strip()
        key = label.lower().replace("prince 2", "prince2")
        if key in seen:
            continue
        seen.add(key)
        found.append(label)
    if any(re.search(r"(?i)togaf\s+\d", item) for item in found):
        found = [item for item in found if not re.fullmatch(r"(?i)togaf", item)]
    return found[:8]


def _profile_section(text: str) -> str:
    match = re.search(
        r"professional profile\s*(.+?)(?:\nprofessional experience|\nexperience\b|"
        r"\ntechnical proficiencies)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    summary = re.sub(r"\s+", " ", match.group(1)).strip()
    return re.sub(r"(?i)^(professional profile\s*)+", "", summary).strip()


def _domains(lowered: str) -> list[str]:
    mapping = {
        "automotive": ("aston martin", "jaguar", "nissan", "automotive"),
        "higher education": ("university", "department for education", "department of education"),
        "retail": ("wickes", "travis perkins", "specsavers"),
        "manufacturing": ("manufacturing",),
        "public sector": ("department for education", "department of education", "natural resources wales"),
        "financial services": ("financial services", "vw financial"),
        "healthcare": ("optum", "unitedhealth", "healthcare"),
        "sme automation": ("n8n", "avalon creative"),
    }
    found = [label for label, needles in mapping.items() if any(n in lowered for n in needles)]
    return found


def _seniority(roles: list[str], text: str) -> str | None:
    blob = f"{' '.join(roles)} {text}".lower()
    if re.search(r"\b(?:cto|chief technology officer)\b", blob):
        return "executive"
    if re.search(r"\b(?:technology|it|architecture) director\b", blob):
        return "director"
    if re.search(
        r"\b(?:lead|principal) architect|enterprise architect|enterprise architecture leader\b",
        blob,
    ):
        return "lead"
    return None

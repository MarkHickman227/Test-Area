"""Compare a job description to the parsed CV without inventing experience."""

from __future__ import annotations

import json
import re
from typing import Any

_ROLE_TERMS = (
    "enterprise architect",
    "solutions architect",
    "solution architect",
    "chief technology officer",
    "lead architect",
    "principal architect",
    "technology director",
    "architecture director",
)

_SALES_TERMS = (
    "account director",
    "account executive",
    "sales director",
    "business development",
    "commission",
)

_TERM_ALIASES = {
    "solution architect": ("solution architect", "solutions architect"),
    "solutions architect": ("solutions architect", "solution architect"),
    "enterprise architect": ("enterprise architect", "enterprise architecture"),
}


def match_job_to_cv(
    job: dict[str, Any],
    cv_profile: dict[str, Any] | None,
    preferences: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not cv_profile:
        return {
            "score": None,
            "score_explanation": "No CV profile loaded, so this job was not scored.",
        }

    job_text = _job_text(job)
    cv_text = _cv_text(cv_profile)
    raw_len = len((cv_profile.get("raw_text") or "").strip())
    cv_chars = raw_len or len(cv_text.strip())
    if not cv_text.strip():
        return {
            "score": None,
            "score_explanation": "The uploaded CV is empty, so this job was not scored.",
        }

    skills = [str(s) for s in (cv_profile.get("skills") or []) if str(s).strip()]
    domains = [str(d) for d in (cv_profile.get("domains") or []) if str(d).strip()]
    cv_roles = [str(r) for r in (cv_profile.get("roles") or []) if str(r).strip()]
    matched_skills = [s for s in skills if _term_in_text(s, job_text)]
    for term in _wanted_terms(job):
        if _term_in_text(term, cv_text) and not any(term.lower() == s.lower() for s in matched_skills):
            matched_skills.append(term)
    matched_domains = [d for d in domains if _term_in_text(d, job_text)]
    matched_cv_roles = [r for r in cv_roles if _term_in_text(r, job_text)]
    role_hits = matched_cv_roles or [role for role in _ROLE_TERMS if _term_in_text(role, job_text)]
    title = (job.get("title") or "").lower()
    sales_role = any(term in title for term in _SALES_TERMS) and "architect" not in title

    # Listings are already from the user's EA/SA/CTO search. Most should be
    # apply-ready; only clearly unrelated titles stay below the draft threshold.
    score = 72
    if any(role in title for role in _ROLE_TERMS) or "cto" in title:
        score += 10
    elif role_hits:
        score += 6
    if matched_skills:
        score += min(12, 3 * len(matched_skills))
    if matched_domains:
        score += min(6, 2 * len(matched_domains))
    score += _preference_bonus(job, job_text, preferences)
    if job.get("job_type") == "CONTRACT" and cv_profile.get("contract_delivery_years"):
        score += 4
    if sales_role:
        score = min(score, 32)
    score = max(0, min(100, score))

    gaps = _gaps(job, cv_text)
    explanation = _explanation(
        job, matched_skills, matched_domains, role_hits, score, gaps, cv_chars
    )
    return {
        "score": score,
        "score_explanation": explanation,
        "strengths": matched_skills[:8] + role_hits[:4],
        "gaps": gaps[:6],
    }


def compact_profile(cv_profile: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "skills",
        "roles",
        "domains",
        "seniority",
        "experience_years",
        "contract_delivery_years",
        "open_to_contract",
        "certifications",
    ):
        if cv_profile.get(key) not in (None, "", [], {}):
            compact[key] = cv_profile[key]
    summary = (cv_profile.get("summary") or "").strip()
    if summary:
        compact["summary"] = summary[:2000]
    return compact


def _term_in_text(term: str, text: str) -> bool:
    needle = str(term or "").strip().lower()
    if not needle:
        return False
    variants = _TERM_ALIASES.get(needle, (needle,))
    for variant in variants:
        if len(variant) <= 3 or variant in {"api", "crm", "rpa", "uml", "m&a"}:
            if re.search(rf"\b{re.escape(variant)}\b", text) is not None:
                return True
        elif variant in text:
            return True
    return False


def _job_text(job: dict[str, Any]) -> str:
    parts = [
        job.get("title") or "",
        job.get("company") or "",
        job.get("location") or "",
        job.get("description") or "",
        job.get("job_type") or "",
        json.dumps(job.get("parsed_requirements") or {}, ensure_ascii=True),
    ]
    return " ".join(parts).lower()


def _preference_bonus(
    job: dict[str, Any],
    job_text: str,
    preferences: dict[str, Any] | None,
) -> int:
    if not preferences:
        return 0
    bonus = 0
    title = (job.get("title") or "").lower()
    for wanted in preferences.get("target_titles") or []:
        if str(wanted).lower() in title or str(wanted).lower() in job_text:
            bonus += 8
            break
    location = (job.get("location") or "").lower()
    for wanted in preferences.get("locations") or []:
        token = str(wanted).lower()
        if token in location or token in job_text:
            bonus += 4
            break
    return min(12, bonus)


def _cv_text(cv_profile: dict[str, Any]) -> str:
    parts = [
        cv_profile.get("raw_text") or "",
        cv_profile.get("summary") or "",
        " ".join(str(s) for s in (cv_profile.get("skills") or [])),
        " ".join(str(r) for r in (cv_profile.get("roles") or [])),
        " ".join(str(d) for d in (cv_profile.get("domains") or [])),
        " ".join(str(c) for c in (cv_profile.get("certifications") or [])),
    ]
    return " ".join(parts).lower()


def _wanted_terms(job: dict[str, Any]) -> list[str]:
    required = job.get("parsed_requirements") or {}
    terms: list[str] = []
    for key in ("required_skills", "keywords"):
        for item in required.get(key) or []:
            value = str(item).strip()
            if value:
                terms.append(value)
    return terms


def _gaps(job: dict[str, Any], cv_text: str) -> list[str]:
    gaps = []
    for skill in _wanted_terms(job):
        if not _term_in_text(skill, cv_text):
            gaps.append(skill)
    return gaps


def _explanation(
    job: dict[str, Any],
    matched_skills: list[str],
    matched_domains: list[str],
    role_hits: list[str],
    score: int,
    gaps: list[str],
    cv_chars: int,
) -> str:
    title = job.get("title") or "This role"
    bits = [
        f"{title} scored {score}/100 against the full uploaded CV ({cv_chars} characters)."
    ]
    if role_hits:
        bits.append("CV roles that overlap the listing: " + ", ".join(role_hits[:4]) + ".")
    if matched_skills:
        bits.append("Evidence in the full CV: " + ", ".join(matched_skills[:8]) + ".")
    else:
        bits.append("The full CV does not name the skills listed in this job.")
    if matched_domains:
        bits.append("Domain overlap: " + ", ".join(matched_domains[:4]) + ".")
    if gaps:
        bits.append("Requirements not found in the CV: " + ", ".join(gaps[:4]) + ".")
    return " ".join(bits)

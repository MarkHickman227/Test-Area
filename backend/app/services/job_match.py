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
    skills = [str(s) for s in (cv_profile.get("skills") or []) if str(s).strip()]
    domains = [str(d) for d in (cv_profile.get("domains") or []) if str(d).strip()]
    matched_skills = [s for s in skills if _term_in_text(s, job_text)]
    matched_domains = [d for d in domains if _term_in_text(d, job_text)]
    role_hits = [role for role in _ROLE_TERMS if _term_in_text(role, job_text)]
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

    gaps = _gaps(job, matched_skills)
    explanation = _explanation(job, matched_skills, matched_domains, role_hits, score, gaps)
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
    if len(needle) <= 3 or needle in {"api", "crm", "rpa", "uml", "m&a"}:
        return re.search(rf"\b{re.escape(needle)}\b", text) is not None
    return needle in text


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


def _gaps(job: dict[str, Any], matched_skills: list[str]) -> list[str]:
    required = job.get("parsed_requirements") or {}
    wanted = [str(s) for s in (required.get("required_skills") or []) if str(s).strip()]
    matched_lower = {s.lower() for s in matched_skills}
    gaps = []
    for skill in wanted:
        if skill.lower() in matched_lower:
            continue
        if not any(part in skill.lower() for part in matched_lower if len(part) > 4):
            gaps.append(skill)
    return gaps


def _explanation(
    job: dict[str, Any],
    matched_skills: list[str],
    matched_domains: list[str],
    role_hits: list[str],
    score: int,
    gaps: list[str],
) -> str:
    title = job.get("title") or "This role"
    bits = [
        f"{title} scored {score}/100 against the uploaded CV. "
        "This listing is in the current search, so it is treated as apply-ready "
        "unless the title is clearly unrelated."
    ]
    if role_hits:
        bits.append("Role overlap: " + ", ".join(role_hits[:4]) + ".")
    if matched_skills:
        bits.append("Skills named in the job text/requirements: " + ", ".join(matched_skills[:8]) + ".")
    else:
        bits.append("No CV skills were named in the job description.")
    if matched_domains:
        bits.append("Domain overlap: " + ", ".join(matched_domains[:4]) + ".")
    if gaps:
        bits.append("Requirements not named on the CV: " + ", ".join(gaps[:4]) + ".")
    return " ".join(bits)

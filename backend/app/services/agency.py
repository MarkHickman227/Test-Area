import re

_AGENCY_NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\brecruitment\b",
        r"\brecruiting\b",
        r"\bstaffing\b",
        r"\btalent\s+(?:acquisition|partner|solution)",
        r"\bheadhunt",
        r"\bsearch\s+(?:firm|consultant|partner)",
        r"\bplacement\b",
        r"\bpersonnel\b",
        r"\bmanpower\b",
        r"\bagency\b",
    ]
]

_DESCRIPTION_SIGNALS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"on behalf of (?:our|a|their) client",
        r"our client (?:is|are|has)",
        r"acting (?:on behalf|for)",
        r"we are (?:looking|seeking|recruiting) (?:on behalf|for (?:a|our) client)",
        r"end[\s-]?client",
        r"(?:umbrella|ltd) company",
    ]
]

_AGENCY_DOMAIN_KEYWORDS = frozenset(
    [
        "recruit",
        "staffing",
        "talent",
        "search",
        "personnel",
        "headhunt",
        "placement",
        "agency",
        "consulting",
    ]
)


def detect_agency(
    company: str | None = None,
    description: str | None = None,
    contact_email: str | None = None,
) -> bool:
    if company and any(p.search(company) for p in _AGENCY_NAME_PATTERNS):
        return True

    if contact_email:
        domain = contact_email.rsplit("@", 1)[-1].lower()
        if any(kw in domain for kw in _AGENCY_DOMAIN_KEYWORDS):
            return True

    if description and any(p.search(description) for p in _DESCRIPTION_SIGNALS):
        return True

    return False

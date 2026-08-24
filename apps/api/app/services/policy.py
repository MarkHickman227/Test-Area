from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

from app.models.enums import PolicyDecision

logger = logging.getLogger("privatecanvas.policy")

# Rule IDs only are persisted. Never return matched phrases to API clients.
MINOR_PATTERNS = [
    r"\bminors?\b",
    r"\bchild(?:ren|ish)?\b",
    r"\bkids?\b",
    r"\bteen(?:ager)?s?\b",
    r"\bunderage\b",
    r"\bunder[\s-]?age\b",
    r"\byouthful[\s-]?looking\b",
    r"\bbarely[\s-]?legal\b",
    r"\bschool[\s-]?girl\b",
    r"\bschoolgirl\b",
    r"\bschoolboy\b",
    r"\bloli(?:ta|con)?\b",
    r"\bshota\b",
    r"\bpre[\s-]?teen\b",
    r"\bpreteen\b",
    r"\binfant\b",
    r"\btoddler\b",
    r"\bbaby\b",
    r"\bped[oa]\b",
    r"\bage[\s-]?play\b",
    r"\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen)[\s-]?year",
    r"\b1[0-7]\s*(?:yo|y/?o|years?)\b",
    r"\bunder\s*18\b",
]

REAL_PERSON_PATTERNS = [
    r"\bcelebrity\b",
    r"\bcelebrities\b",
    r"\bpublic[\s-]?figure\b",
    r"\breal[\s-]?person\b",
    r"\bface[\s-]?swap\b",
    r"\bdeepfake\b",
    r"\bthis is (?:a photo of|my|his|her)\b",
    r"\bfrom (?:this|the) (?:photo|picture|image)\b",
    r"\binfluencer\b",
    r"\bnamed after\b",
]

VIOLENCE_PATTERNS = [
    r"\brape\b",
    r"\bnon[\s-]?consensual\b",
    r"\bwithout consent\b",
    r"\bforced\b",
    r"\bcoerc(?:e|ion|ed)\b",
    r"\bincest\b",
    r"\bbestiality\b",
    r"\bzoophilia\b",
    r"\bnecrophilia\b",
    r"\btraffick",
    r"\bsexual violence\b",
    r"\bsnuff\b",
]

EVASION_PATTERNS = [
    r"\bjailbreak\b",
    r"\bbypass (?:the )?(?:filter|safety|policy)\b",
    r"\bignore (?:previous|all) (?:instructions|rules|filters)\b",
    r"\bdan mode\b",
    r"\bunfiltered\b",
    r"\buncensored model\b",
    r"\bevasion of safety\b",
]

AMBIGUOUS_AGE_PATTERNS = [
    r"\byoung(?:er|-looking)?\b",
    r"\bpetite adult\b",
    r"\blooks 18\b",
    r"\bjust turned 18\b",
    r"\bcollege (?:girl|boy|kid)\b",
]


@dataclass
class PolicyResult:
    decision: PolicyDecision
    rule_ids: list[str] = field(default_factory=list)
    score: float | None = None


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_MINOR = _compile(MINOR_PATTERNS)
_REAL = _compile(REAL_PERSON_PATTERNS)
_VIOLENCE = _compile(VIOLENCE_PATTERNS)
_EVASION = _compile(EVASION_PATTERNS)
_AMBIGUOUS = _compile(AMBIGUOUS_AGE_PATTERNS)


def _hits(compiled: list[re.Pattern[str]], text: str, prefix: str) -> list[str]:
    found: list[str] = []
    for idx, pattern in enumerate(compiled):
        if pattern.search(text):
            found.append(f"{prefix}:{idx}")
    return found


class PolicyEngine:
    """Deterministic prompt gate. Classifier API is a stub hook for later."""

    def evaluate(self, prompt: str, negative_prompt: str | None = None) -> PolicyResult:
        # Only the user-requested (positive) prompt is gated. Negative lists may
        # include prohibited terms as exclusions.
        text = prompt
        minor = _hits(_MINOR, text, "minor")
        if minor:
            return PolicyResult(PolicyDecision.BLOCK, minor, score=0.99)
        violence = _hits(_VIOLENCE, text, "violence")
        if violence:
            return PolicyResult(PolicyDecision.BLOCK, violence, score=0.98)
        real = _hits(_REAL, text, "identity")
        if real:
            return PolicyResult(PolicyDecision.BLOCK, real, score=0.9)
        evasion = _hits(_EVASION, text, "evasion")
        if evasion:
            return PolicyResult(PolicyDecision.BLOCK, evasion, score=0.85)
        ambiguous = _hits(_AMBIGUOUS, text, "age_ambiguous")
        if ambiguous:
            return PolicyResult(PolicyDecision.HOLD_FOR_REVIEW, ambiguous, score=0.6)
        return PolicyResult(PolicyDecision.ALLOW, [], score=0.05)


def fingerprint_parameters(payload: dict) -> str:
    canonical = repr(sorted(payload.items())).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

from __future__ import annotations

from dataclasses import dataclass

PRICING_RULE_VERSION = "pricing-v1"

RESOLUTION_MULTIPLIERS = {
    "768x768": 1.0,
    "768x1152": 1.25,
    "1152x768": 1.25,
    "1024x1024": 1.5,
}

ASPECT_TO_RESOLUTION = {
    ("1:1", "768x768"): True,
    ("1:1", "1024x1024"): True,
    ("2:3", "768x1152"): True,
    ("3:2", "1152x768"): True,
    ("9:16", "768x1152"): True,
    ("16:9", "1152x768"): True,
}

ALLOWED_ASPECTS = ["1:1", "2:3", "3:2", "9:16", "16:9"]
ALLOWED_RESOLUTIONS = list(RESOLUTION_MULTIPLIERS)
ALLOWED_COUNTS = [1, 2, 4]


@dataclass(frozen=True)
class PricingInput:
    base_model_cost: int
    resolution: str
    image_count: int
    priority_multiplier: float = 1.0
    post_processing_cost: int = 0
    workflow_multiplier: float = 1.0


def calculate_credit_cost(inp: PricingInput) -> int:
    multiplier = RESOLUTION_MULTIPLIERS.get(inp.resolution)
    if multiplier is None:
        raise ValueError("Unsupported resolution")
    if inp.image_count not in ALLOWED_COUNTS:
        raise ValueError("Unsupported image count")
    raw = (
        inp.base_model_cost
        * multiplier
        * inp.image_count
        * inp.priority_multiplier
        * inp.workflow_multiplier
        + inp.post_processing_cost
    )
    return max(1, int(round(raw)))


def default_resolution_for_aspect(aspect: str) -> str:
    mapping = {
        "1:1": "768x768",
        "2:3": "768x1152",
        "3:2": "1152x768",
        "9:16": "768x1152",
        "16:9": "1152x768",
    }
    return mapping[aspect]

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PLACEHOLDER_NOTE = "Synthetic non-explicit placeholder. Not a model output."


def render_placeholder(job_id: str, width: int, height: int, index: int) -> bytes:
    image = Image.new("RGB", (width, height), (28, 24, 22))
    draw = ImageDraw.Draw(image)
    accent = (196, 165, 116)
    margin = max(16, min(width, height) // 24)
    draw.rectangle(
        [margin, margin, width - margin, height - margin], outline=accent, width=3
    )
    draw.line(
        [(margin, height // 3), (width - margin, height // 3)], fill=accent, width=2
    )
    try:
        font = ImageFont.load_default()
    except OSError:
        font = None
    lines = [
        "PrivateCanvas",
        "Placeholder output",
        f"job {job_id[:8]}",
        f"frame {index + 1}",
        PLACEHOLDER_NOTE,
    ]
    y = height // 3 + 24
    for line in lines:
        draw.text((margin + 16, y), line, fill=(243, 239, 232), font=font)
        y += 22
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_thumbnail(png_bytes: bytes, max_edge: int = 256) -> bytes:
    with Image.open(io.BytesIO(png_bytes)) as img:
        img = img.convert("RGB")
        img.thumbnail((max_edge, max_edge))
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def _flatten_substitutions(substitutions: dict) -> dict:
    flat: dict = {}
    for key, value in substitutions.items():
        if key == "preset_values":
            if not isinstance(value, dict):
                raise ValueError("preset_values must be an object")
            for inner_key, inner_value in value.items():
                if not isinstance(inner_key, str) or "." in inner_key:
                    raise ValueError("Invalid preset field")
                flat[f"preset.{inner_key}"] = inner_value
            continue
        if isinstance(value, dict):
            raise ValueError("Nested substitutions are only allowed via preset_values")
        flat[key] = value
    return flat


def build_workflow_payload(template: dict, substitutions: dict) -> dict:
    allowed = set(template.get("allowed_variable_fields") or [])
    extra = set(substitutions) - allowed
    if extra:
        raise ValueError("Disallowed workflow substitution")
    flat = _flatten_substitutions(substitutions)
    raw = json.dumps(template["fixed_graph"])
    for key, value in sorted(flat.items(), key=lambda item: len(item[0]), reverse=True):
        quoted = '"{{' + key + '}}"'
        if quoted in raw:
            raw = raw.replace(quoted, json.dumps(value))
        raw = raw.replace("{{" + key + "}}", str(value))
    if "{{" in raw:
        raise ValueError("Unsubstituted workflow placeholders remain")
    graph = json.loads(raw)
    return comfyui_prompt_graph(graph)


def comfyui_prompt_graph(fixed_graph: dict) -> dict:
    nodes = fixed_graph.get("nodes") if isinstance(fixed_graph, dict) else None
    source = nodes if isinstance(nodes, dict) else fixed_graph
    return {
        key: value
        for key, value in source.items()
        if isinstance(value, dict) and value.get("class_type")
    }


def workflow_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

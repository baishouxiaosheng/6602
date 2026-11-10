"""Shared parsing for every provider: strip fences, parse, validate (Lec 9, Parse JSON)."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def extract_json_text(raw: str) -> str:
    """Remove markdown fences and any prose around the outermost JSON object."""
    text = _FENCE_RE.sub("", raw or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        text = text[start : end + 1]
    return text


def validate_json_text(raw: str, schema: type[T]) -> T:
    """Raise ValueError with a short, model-readable reason when ``raw`` is not valid."""
    text = extract_json_text(raw)
    if not text:
        raise ValueError("empty answer")
    try:
        return schema.model_validate(json.loads(text))
    except json.JSONDecodeError as err:
        raise ValueError(f"not valid JSON: {err.msg} at position {err.pos}") from err
    except ValidationError as err:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}"
            for e in err.errors()[:6]
        )
        raise ValueError(f"JSON does not match the schema: {problems}") from err


def schema_instruction(schema: type[BaseModel]) -> str:
    return (
        "Answer with ONE json object only. No prose, no markdown fences.\n"
        "The object must validate against this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    )

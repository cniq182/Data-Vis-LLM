"""Parse, sanitize, validate and summarize Vega-Lite specs produced by the LLM.

Validation errors are written so they can be fed back to the LLM verbatim
in the self-healing loop.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

Spec = dict[str, Any]

# Keys whose values may name a data column.
_FIELD_KEYS = ("field",)
_FIELD_LIST_KEYS = ("groupby", "fold")
# Keys that introduce derived fields inside transforms.
_DERIVED_KEYS = ("as",)
# Keys stripped anywhere in the spec: data always comes from our DataFrame.
_FORBIDDEN_KEYS = ("data", "datasets")


class SpecError(Exception):
    """A spec that cannot be rendered. The message is meant for the LLM."""


def parse_spec(text: str) -> Spec:
    """Extract a JSON object from raw LLM output (tolerates ``` fences)."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        spec = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SpecError(f"Output is not valid JSON: {exc}") from exc
    if not isinstance(spec, dict):
        raise SpecError("The top-level JSON value must be an object.")
    return spec


def sanitize(spec: Spec) -> Spec:
    """Remove any data source the LLM may have added (URLs, inline values)."""
    if isinstance(spec, dict):
        return {k: sanitize(v) for k, v in spec.items() if k not in _FORBIDDEN_KEYS}
    if isinstance(spec, list):
        return [sanitize(v) for v in spec]
    return spec


def _collect(node: Any, used: set[str], derived: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _FIELD_KEYS and isinstance(value, str):
                used.add(value)
            elif key in _FIELD_LIST_KEYS and isinstance(value, list):
                used.update(v for v in value if isinstance(v, str))
            elif key in _DERIVED_KEYS:
                items = value if isinstance(value, list) else [value]
                derived.update(v for v in items if isinstance(v, str))
            _collect(value, used, derived)
    elif isinstance(node, list):
        for item in node:
            _collect(item, used, derived)


def check_fields(spec: Spec, columns: set[str]) -> None:
    """Fail if the spec references columns that do not exist.

    JSON Schema validation cannot catch this, and it is the most common
    cause of an empty or silently wrong chart.
    """
    used: set[str] = set()
    derived: set[str] = set()
    _collect(spec, used, derived)
    unknown = sorted(used - columns - derived)
    if unknown:
        raise SpecError(
            f"Unknown field(s) {unknown}. Available columns: {sorted(columns)}."
        )


@lru_cache(maxsize=1)
def _validator() -> Any:
    """Load the Vega-Lite JSON schema bundled with altair (any version)."""
    import altair
    import jsonschema

    altair_dir = Path(altair.__file__).parent
    candidates = sorted(altair_dir.glob("vegalite/v*/schema/vega-lite-schema.json"))
    if not candidates:
        raise RuntimeError(f"Vega-Lite schema not found inside {altair_dir}")
    schema = json.loads(candidates[-1].read_text(encoding="utf-8"))
    return jsonschema.Draft7Validator(schema)


def check_schema(spec: Spec) -> None:
    import jsonschema

    # Vega-Lite requires a top-level "data" entry. Ours is injected by
    # Streamlit at render time, so a placeholder is added for validation only.
    candidate = {"data": {"name": "table"}, **spec}
    error = jsonschema.exceptions.best_match(_validator().iter_errors(candidate))
    if error is not None:
        path = "/".join(str(p) for p in error.absolute_path) or "(root)"
        raise SpecError(f"Invalid Vega-Lite at {path}: {error.message[:300]}")


def validate(spec: Spec, columns: set[str]) -> Spec:
    """Full pipeline: sanitize, check fields, check schema. Returns clean spec."""
    clean = sanitize(spec)
    check_fields(clean, columns)
    check_schema(clean)
    return clean


def summarize(spec: Spec) -> str:
    """Human-readable description of what the chart encodes (transparency, risk 1)."""
    mark = spec.get("mark")
    mark_name = mark.get("type") if isinstance(mark, dict) else mark
    parts: list[str] = []
    for channel, enc in spec.get("encoding", {}).items():
        if not isinstance(enc, dict):
            continue
        field = enc.get("field", "")
        for op_key in ("aggregate", "timeUnit"):
            if op_key in enc:
                field = f"{enc[op_key]}({field})" if field else str(enc[op_key])
        if enc.get("bin"):
            field = f"bin({field})"
        if field:
            parts.append(f"{channel} = {field}")
    filters = [t["filter"] for t in spec.get("transform", []) if "filter" in t]
    text = f"{mark_name or 'layered'} chart"
    if parts:
        text += ": " + ", ".join(parts)
    if filters:
        text += f" | filters: {filters}"
    return text
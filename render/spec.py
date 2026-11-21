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

# The LLM often writes singular time units ("hour"); Vega-Lite needs the plural ("hours").
_TIME_UNIT_FIXES = (
    (re.compile(r"hour(?!s)"), "hours"),
    (re.compile(r"minute(?!s)"), "minutes"),
    (re.compile(r"second(?!s)"), "seconds"),
)


class SpecError(Exception):
    """A spec that cannot be rendered. The message is meant for the LLM;
    `detail` keeps the full, untruncated explanation for the log."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail or message


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


def _strip_data(node: Any) -> Any:
    """Remove any data source the LLM may have added (URLs, inline values)."""
    if isinstance(node, dict):
        return {k: _strip_data(v) for k, v in node.items() if k not in _FORBIDDEN_KEYS}
    if isinstance(node, list):
        return [_strip_data(v) for v in node]
    return node

def _fix_time_unit(value: str) -> str:
    for pattern, plural in _TIME_UNIT_FIXES:
        value = pattern.sub(plural, value)
    return value


def _fix_time_units(node: Any) -> Any:
    """Recursively replace singular time units anywhere in the spec."""
    if isinstance(node, dict):
        fixed: dict[str, Any] = {}
        for key, value in node.items():
            if key == "timeUnit" and isinstance(value, str):
                fixed[key] = _fix_time_unit(value)
            elif key == "timeUnit" and isinstance(value, dict) and isinstance(value.get("unit"), str):
                fixed[key] = {**value, "unit": _fix_time_unit(value["unit"])}
            else:
                fixed[key] = _fix_time_units(value)
        return fixed
    if isinstance(node, list):
        return [_fix_time_units(v) for v in node]
    return node

def sanitize(spec: Spec) -> Spec:
    """Remove data sources and fix known LLM habits that break validation."""
    clean = _fix_time_units(_strip_data(spec))

    # config.view.width/height is invalid in our Vega-Lite schema: move it to the top level.
    config = clean.get("config")
    view = config.get("view") if isinstance(config, dict) else None
    if isinstance(view, dict):
        for key in ("width", "height"):
            if key in view:
                clean.setdefault(key, view.pop(key))
        if not view:
            del config["view"]
        if not config:
            del clean["config"]

    return clean

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


def _leaf_errors(error: Any) -> Any:
    """Walk down the tree of sub-errors (one per schema alternative) to the leaves."""
    if not error.context:
        yield error
    else:
        for sub in error.context:
            yield from _leaf_errors(sub)


def _short_message(error: Any) -> str:
    """The error message without echoing large objects back."""
    message = error.message
    if isinstance(error.instance, (dict, list)):
        message = message.replace(repr(error.instance), "this object", 1)
    return message[:200]


def check_schema(spec: Spec) -> None:
    import jsonschema  # noqa: F401  (loaded by _validator)

    # Vega-Lite requires a top-level "data" entry. Ours is injected by
    # Streamlit at render time, so a placeholder is added for validation only.
    candidate = {"data": {"name": "table"}, **spec}
    errors = list(_validator().iter_errors(candidate))
    if not errors:
        return

    # The most specific causes are the deepest leaf errors.
    leaves = [leaf for error in errors for leaf in _leaf_errors(error)]
    full_detail = "\n".join(
        f"{'/'.join(str(p) for p in leaf.absolute_path) or '(root)'}: {leaf.message}"
        for leaf in leaves
    )
    max_depth = max(len(leaf.absolute_path) for leaf in leaves)
    deepest = [leaf for leaf in leaves if len(leaf.absolute_path) == max_depth]
    path = "/".join(str(p) for p in deepest[0].absolute_path) or "(root)"

    # Invalid value: list the allowed ones so the model can pick a valid one.
    options: set[str] = set()
    for leaf in deepest:
        if leaf.validator == "enum":
            options.update(str(o) for o in leaf.validator_value)
        elif leaf.validator == "const":
            options.add(str(leaf.validator_value))
    if options:
        raise SpecError(
            f"Invalid value {deepest[0].instance!r} at {path}. "
            f"Valid values: {', '.join(sorted(options))}.",
            detail=full_detail,
        )

    messages = sorted({_short_message(leaf) for leaf in deepest})
    raise SpecError(
        f"Invalid Vega-Lite at {path}: " + " | ".join(messages[:3]),
        detail=full_detail,
    )


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
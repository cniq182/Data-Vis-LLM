"""Automatic grader for the autochart benchmark.

It does NOT compare JSON text. It reduces a Vega-Lite spec to its *meaning*
(a "signature") and compares that with the expected answer of a case:

    group_by : which fields the data is grouped by (any channel), with timeUnit
    measure  : what is calculated (aggregate + field; field ignored for count)
    filters  : which rows are kept (field + value, with timeUnit if any)

Things that do not change the meaning are ignored: titles, sort, width,
height, config, colours, tooltips, "remove nulls" filters.

Anything marked as a failure is reviewed by hand afterwards.

Quick self-check (uses real specs from pre-pilot 4):
    python -m benchmark.grader
"""

import re
from dataclasses import dataclass, field

# Channels that split the data into groups (bars, lines, colours, facets).
GROUP_CHANNELS = ("x", "y", "color", "column", "row", "facet",
                  "xOffset", "yOffset", "shape", "detail")
# Channels that never change which numbers are shown.
IGNORED_CHANNELS = ("tooltip", "href", "description", "opacity", "size",
                    "strokeWidth", "text")

AGGREGATE_SYNONYMS = {"average": "mean", "avg": "mean", "total": "sum"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _norm_time_unit(tu):
    """'utchours' -> 'hours'; {'unit': 'hours'} -> 'hours'; None stays None."""
    if isinstance(tu, dict):
        tu = tu.get("unit")
    if not tu:
        return None
    tu = str(tu).lower()
    if tu.startswith("utc"):
        tu = tu[3:]
    return tu


def _norm_value(v):
    """Compare values loosely: 5 == '5' == 5.0, 'Riverside' == 'riverside'."""
    if isinstance(v, (list, tuple)) and len(v) == 1:
        v = v[0]
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip().strip("'\"").lower()


def _norm_aggregate(a):
    if isinstance(a, dict):          # e.g. {"argmax": "fare"}
        return str(list(a.keys())[0])
    a = str(a).lower()
    return AGGREGATE_SYNONYMS.get(a, a)


def _mark_type(spec):
    mark = spec.get("mark")
    if isinstance(mark, dict):
        mark = mark.get("type")
    return mark


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
# datum.field == 'value'   |   datum['field'] === "value"
_EXPR_EQ = re.compile(
    r"datum(?:\.(\w+)|\[['\"]([^'\"]+)['\"]\])\s*===?\s*(['\"][^'\"]*['\"]|[\w.\-]+)"
)
# hours(datum.field) == 5
_EXPR_TU = re.compile(
    r"(utc)?(hours|day|month|year|date|minutes)\(\s*datum(?:\.(\w+)|\[['\"]([^'\"]+)['\"]\])\s*\)"
    r"\s*===?\s*(['\"][^'\"]*['\"]|[\w.\-]+)"
)


def _filters_from_predicate(pred):
    """Turn one Vega-Lite filter (dict or string) into a list of
    (field, timeUnit, value) tuples. 'Remove nulls' filters are dropped."""
    out = []
    if isinstance(pred, dict):
        if "and" in pred:
            for p in pred["and"]:
                out += _filters_from_predicate(p)
            return out
        if "valid" in pred:                  # remove-nulls filter: ignore
            return out
        fld = pred.get("field")
        tu = _norm_time_unit(pred.get("timeUnit"))
        if "equal" in pred:
            out.append((fld, tu, _norm_value(pred["equal"])))
        elif "oneOf" in pred and len(pred["oneOf"]) == 1:
            out.append((fld, tu, _norm_value(pred["oneOf"][0])))
        else:
            # range, lt, gt, oneOf with several values...: keep as text so it
            # never matches by accident (a human will review it).
            out.append((fld, tu, "other:" + str(sorted(pred.items()))))
        return out

    if isinstance(pred, str):
        expr = pred
        # Drop null checks like "isValid(datum.x)" or "datum.x != null".
        if re.fullmatch(r"\s*(isValid\(.*\)|datum\.\w+\s*!==?\s*null)\s*", expr):
            return out
        for m in _EXPR_TU.finditer(expr):
            fld = m.group(3) or m.group(4)
            out.append((fld, m.group(2), _norm_value(m.group(5))))
        expr_no_tu = _EXPR_TU.sub("", expr)
        for m in _EXPR_EQ.finditer(expr_no_tu):
            fld = m.group(1) or m.group(2)
            out.append((fld, None, _norm_value(m.group(3))))
        if not out:
            out.append((None, None, "other:" + expr))
    return out


# ---------------------------------------------------------------------------
# Signature = meaning of a spec
# ---------------------------------------------------------------------------
@dataclass
class Signature:
    group_by: set = field(default_factory=set)    # {(field, timeUnit)}
    measure: tuple = None                         # (aggregate, field or None)
    filters: set = field(default_factory=set)     # {(field, timeUnit, value)}
    mark: str = None

    def describe(self) -> str:
        g = ", ".join(f"{tu}({f})" if tu else str(f) for f, tu in sorted(self.group_by, key=str))
        m = "none" if self.measure is None else (
            f"{self.measure[0]}({self.measure[1] or ''})")
        fl = ", ".join(f"{(tu + '(' + str(f) + ')') if tu else f}={v}"
                       for f, tu, v in sorted(self.filters, key=str)) or "none"
        return f"mark={self.mark}; group_by=[{g}]; measure={m}; filters=[{fl}]"


def signature_of(spec: dict) -> Signature:
    """Reduce a Vega-Lite spec to its meaning."""
    sig = Signature()

    # Layered charts: merge the layers (the shared encoding + each layer).
    parts = [spec]
    if isinstance(spec.get("layer"), list):
        parts += spec["layer"]
    sig.mark = _mark_type(spec) or next(
        (_mark_type(p) for p in parts[1:] if _mark_type(p)), None)

    computed_fields = set()   # names created by transforms ("as": ...)

    for part in parts:
        for t in part.get("transform", []) or []:
            if "filter" in t:
                sig.filters.update(_filters_from_predicate(t["filter"]))
            if "aggregate" in t:                 # transform-level aggregate
                for a in t["aggregate"]:
                    op = _norm_aggregate(a.get("op"))
                    sig.measure = (op, None if op == "count" else a.get("field"))
                    computed_fields.add(a.get("as"))
                for g in t.get("groupby", []):
                    sig.group_by.add((g, None))
            if "timeUnit" in t and "as" in t:     # transform-level timeUnit
                computed_fields.add(t["as"])
                sig.group_by.add((t.get("field"), _norm_time_unit(t["timeUnit"])))
            for key in ("calculate", "joinaggregate", "window", "bin"):
                if key in t and "as" in t:
                    computed_fields.add(t["as"] if isinstance(t["as"], str) else None)

        for channel, enc in (part.get("encoding") or {}).items():
            if channel in IGNORED_CHANNELS or not isinstance(enc, dict):
                continue
            fld = enc.get("field")
            if isinstance(fld, dict):            # {"repeat": ...}
                fld = None
            agg = enc.get("aggregate")
            if agg is not None:
                op = _norm_aggregate(agg)
                sig.measure = (op, None if op == "count" else fld)
            elif fld and fld not in computed_fields and channel in GROUP_CHANNELS:
                tu = _norm_time_unit(enc.get("timeUnit"))
                if enc.get("bin"):
                    tu = "bin"
                sig.group_by.add((fld, tu))
            elif fld and fld in computed_fields and sig.measure is None:
                # e.g. y = "avg_tip" created by a transform aggregate
                pass

    # Colour encoding that repeats the x/y grouping field adds no new group.
    sig.group_by = {g for g in sig.group_by if g[0] is not None}
    return sig


def _expected_signature(exp: dict) -> Signature:
    sig = Signature()
    sig.group_by = {(g["field"], g.get("timeUnit")) for g in exp.get("group_by", [])}
    m = exp.get("measure")
    if m:
        op = _norm_aggregate(m["aggregate"])
        sig.measure = (op, None if op == "count" else m.get("field"))
    sig.filters = {(f["field"], f.get("timeUnit"), _norm_value(f["value"]))
                   for f in exp.get("filters", [])}
    return sig


def _differences(got: Signature, want: Signature) -> list:
    diffs = []
    if got.group_by != want.group_by:
        diffs.append(f"group_by: expected {sorted(want.group_by, key=str)}, "
                     f"got {sorted(got.group_by, key=str)}")
    if got.measure != want.measure:
        diffs.append(f"measure: expected {want.measure}, got {got.measure}")
    if got.filters != want.filters:
        diffs.append(f"filters: expected {sorted(want.filters, key=str)}, "
                     f"got {sorted(got.filters, key=str)}")
    return diffs


# ---------------------------------------------------------------------------
# Grade one case
# ---------------------------------------------------------------------------
@dataclass
class Grade:
    passed: bool
    reason: str            # short, human-readable
    mark_ok: bool = None   # secondary measure (None if no chart)
    signature: str = None  # describe() of the final spec


def grade(expected: dict, outcome: str, spec: dict = None) -> Grade:
    """expected: the case's "expected" dict.
    outcome: "chart" | "clarification" | "failure" (the system's final result).
    spec: the final Vega-Lite spec (only when outcome == "chart")."""
    want = expected["outcome"]

    if outcome == "failure":
        return Grade(False, "system failure: no valid chart")

    if outcome == "clarification":
        if want in ("clarification", "chart_or_clarification"):
            return Grade(True, "clarification as expected")
        return Grade(False, "unnecessary clarification")

    # outcome == "chart"
    sig = signature_of(spec or {})
    mark_ok = sig.mark in expected.get("marks", [sig.mark])
    if want == "clarification":
        return Grade(False, "chart instead of clarification (silent guess)",
                     mark_ok, sig.describe())

    all_diffs = []
    for alt in expected["accept"]:
        diffs = _differences(sig, _expected_signature(alt))
        if not diffs:
            return Grade(True, "chart matches", mark_ok, sig.describe())
        all_diffs.append("; ".join(diffs))
    # Report the closest alternative (fewest differences).
    best = min(all_diffs, key=lambda d: d.count(";"))
    return Grade(False, best, mark_ok, sig.describe())


# ---------------------------------------------------------------------------
# Self-check with real specs from pre-pilot 4 (taxis data)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    checks = [
        # T4: mean tip per borough, credit card only -> should PASS
        (
            {"outcome": "chart", "marks": ["bar"], "accept": [{
                "group_by": [{"field": "pickup_borough"}],
                "measure": {"aggregate": "mean", "field": "tip"},
                "filters": [{"field": "payment", "value": "credit card"}]}]},
            {"mark": "bar", "encoding": {
                "x": {"field": "pickup_borough", "type": "nominal"},
                "y": {"field": "tip", "type": "quantitative", "aggregate": "mean"}},
             "transform": [{"filter": {"field": "payment", "equal": "credit card"}}]},
            True,
        ),
        # T1 answered with sum(passengers) when count was expected -> FAIL
        (
            {"outcome": "chart", "marks": ["bar"], "accept": [{
                "group_by": [{"field": "pickup_borough"}],
                "measure": {"aggregate": "count"}, "filters": []}]},
            {"mark": "bar", "encoding": {
                "x": {"field": "pickup_borough", "type": "nominal", "sort": "-y"},
                "y": {"field": "passengers", "aggregate": "sum"}},
             "config": {"view": {"stroke": None}}},
            False,
        ),
        # T3: count per hour -> PASS
        (
            {"outcome": "chart", "marks": ["bar", "line"], "accept": [{
                "group_by": [{"field": "pickup", "timeUnit": "hours"}],
                "measure": {"aggregate": "count"}, "filters": []}]},
            {"mark": "bar", "encoding": {
                "x": {"field": "pickup", "type": "temporal", "timeUnit": "hours"},
                "y": {"aggregate": "count"}}, "width": 500},
            True,
        ),
        # Same filter written as an expression string -> PASS
        (
            {"outcome": "chart", "marks": ["bar"], "accept": [{
                "group_by": [{"field": "dropoff_borough"}],
                "measure": {"aggregate": "count"},
                "filters": [{"field": "pickup_borough", "value": "Brooklyn"}]}]},
            {"mark": "bar", "encoding": {
                "x": {"field": "dropoff_borough"}, "y": {"aggregate": "count"}},
             "transform": [{"filter": "datum.pickup_borough == 'Brooklyn'"},
                           {"filter": {"field": "pickup_borough", "valid": True}}]},
            True,
        ),
        # Filter on a clock hour, written as an expression -> PASS
        (
            {"outcome": "chart", "marks": ["bar"], "accept": [{
                "group_by": [{"field": "pickup_borough"}],
                "measure": {"aggregate": "count"},
                "filters": [{"field": "pickup", "timeUnit": "hours", "value": 5}]}]},
            {"mark": "bar", "encoding": {
                "x": {"field": "pickup_borough"}, "y": {"aggregate": "count"}},
             "transform": [{"filter": "hours(datum.pickup) == 5"}]},
            True,
        ),
    ]
    n_ok = 0
    for i, (exp, spec, should_pass) in enumerate(checks, 1):
        g = grade(exp, "chart", spec)
        ok = g.passed == should_pass
        n_ok += ok
        print(f"[{'OK ' if ok else 'BAD'}] check {i}: passed={g.passed} | {g.reason}")
        print(f"      {g.signature}")
    # Outcome-only checks
    print("[OK ]" if grade({"outcome": "clarification"}, "clarification").passed else "[BAD]",
          "clarification expected and given")
    print("[OK ]" if not grade({"outcome": "chart", "accept": []}, "clarification").passed else "[BAD]",
          "unnecessary clarification is a failure")
    print(f"\n{n_ok}/{len(checks)} spec checks behave as expected")
import pytest
from render.spec import SpecError, check_fields, check_schema, parse_spec, sanitize, summarize
from render.spec import SpecError, check_fields, parse_spec, sanitize, summarize

COLUMNS = {"order date", "region", "revenue"}


def test_parse_tolerates_code_fences() -> None:
    assert parse_spec('```json\n{"mark": "bar"}\n```') == {"mark": "bar"}


def test_parse_rejects_non_json() -> None:
    with pytest.raises(SpecError):
        parse_spec("Here is your chart!")


def test_sanitize_strips_external_data() -> None:
    spec = {"data": {"url": "https://evil.example"}, "layer": [{"data": {}, "mark": "line"}]}
    assert sanitize(spec) == {"layer": [{"mark": "line"}]}


def test_unknown_field_is_reported_with_alternatives() -> None:
    spec = {"mark": "bar", "encoding": {"x": {"field": "Region", "type": "nominal"}}}
    with pytest.raises(SpecError, match="Available columns"):
        check_fields(spec, COLUMNS)


def test_derived_fields_are_allowed() -> None:
    spec = {
        "transform": [{"aggregate": [{"op": "sum", "field": "revenue", "as": "total"}],
                       "groupby": ["region"]}],
        "mark": "bar",
        "encoding": {"x": {"field": "region"}, "y": {"field": "total"}},
    }
    check_fields(spec, COLUMNS)


def test_summary_shows_aggregation() -> None:
    spec = {"mark": "line", "encoding": {
        "x": {"field": "order date", "timeUnit": "yearmonth", "type": "temporal"},
        "y": {"field": "revenue", "aggregate": "sum", "type": "quantitative"}}}
    assert summarize(spec) == "line chart: x = yearmonth(order date), y = sum(revenue)"

def test_schema_accepts_valid_spec() -> None:
    check_schema({"mark": "bar", "encoding": {"x": {"field": "region", "type": "nominal"}}})


def test_schema_rejects_unknown_mark() -> None:
    with pytest.raises(SpecError, match="mark"):
        check_schema({"mark": "barr"})
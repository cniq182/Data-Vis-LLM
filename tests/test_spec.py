import pytest
from render.spec import SpecError, check_fields, check_schema, parse_spec, sanitize, summarize, validate
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

def test_view_size_in_config_is_moved_and_valid() -> None:
    spec = validate({"mark": "bar", "config": {"view": {"width": 400, "height": 300}}}, set())
    assert spec == {"mark": "bar", "width": 400, "height": 300}

def test_singular_time_units_are_fixed() -> None:
    spec = {"mark": "bar", "encoding": {
        "x": {"field": "pickup", "timeUnit": "hour", "type": "ordinal"},
        "y": {"field": "pickup", "timeUnit": {"unit": "yearmonthdatehour"}, "type": "temporal"}}}
    clean = sanitize(spec)
    assert clean["encoding"]["x"]["timeUnit"] == "hours"
    assert clean["encoding"]["y"]["timeUnit"]["unit"] == "yearmonthdatehours"


def test_singular_hour_passes_validation() -> None:
    spec = {"mark": "bar", "encoding": {"x": {"field": "pickup", "timeUnit": "hour", "type": "ordinal"}}}
    validate(spec, {"pickup"})   # failed in the pre-pilot (T3); must not raise now

def test_schema_error_lists_valid_values() -> None:
    with pytest.raises(SpecError, match="Valid values") as exc_info:
        check_schema({"mark": "barr"})
    assert "bar" in str(exc_info.value)


def test_schema_error_points_to_the_cause_without_echoing_spec() -> None:
    with pytest.raises(SpecError) as exc_info:
        check_schema({"mark": "bar", "config": {"view": {"width": 400}}})
    message = str(exc_info.value)
    assert "config/view" in message
    assert "width" in message
    assert len(message) < 500        # no longer echoes the whole spec

def test_schema_error_keeps_full_detail_for_the_log() -> None:
    with pytest.raises(SpecError) as exc_info:
        check_schema({"mark": "bar", "config": {"view": {"width": 400}}})
    error = exc_info.value
    assert "config/view" in error.detail
    assert len(error.detail) > len(str(error))   # the log gets more than the model
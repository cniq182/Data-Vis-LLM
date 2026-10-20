from pathlib import Path

import pytest

from data.loader import DataLoadError, extract_schema, load_csv

SAMPLE = Path(__file__).parent.parent / "sample_data" / "sales.csv"


def test_semicolon_csv_is_loaded_and_typed() -> None:
    df = load_csv(SAMPLE.read_bytes())
    schema = extract_schema(df)
    types = {c.name: c.vl_type for c in schema.columns}
    assert types == {
        "order date": "temporal",
        "region": "nominal",
        "product_name": "nominal",   # '.' replaced for Vega-Lite
        "units": "quantitative",
        "revenue": "quantitative",
    }
    assert schema.n_rows == 6
    assert len(schema.sample) == 3


def test_latin1_is_decoded() -> None:
    raw = "city,temp\nKøbenhavn,12\nÅrhus,11\n".encode("latin-1")
    df = load_csv(raw)
    assert df["city"].iloc[0] == "København"


def test_duplicate_columns_are_renamed() -> None:
    df = load_csv(b"a,a,b\n1,2,3\n4,5,6\n")
    assert list(df.columns)[:2] == ["a", "a_1"]


def test_empty_file_fails_clearly() -> None:
    with pytest.raises(DataLoadError):
        load_csv(b"")

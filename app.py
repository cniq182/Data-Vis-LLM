"""autochart - tracer bullet.

The LLM is not wired yet: a hand-written Vega-Lite spec stands in for it,
so the path CSV -> schema -> spec -> validation -> render can be verified
end to end first.
"""
from __future__ import annotations

import json

import streamlit as st

from data.loader import DataLoadError, extract_schema, load_csv
from render.spec import SpecError, parse_spec, summarize, validate

EXAMPLE_SPEC = {
    "mark": "bar",
    "encoding": {
        "x": {"field": "region", "type": "nominal"},
        "y": {"field": "revenue", "aggregate": "sum", "type": "quantitative"},
    },
}

st.set_page_config(page_title="autochart", layout="wide")
st.title("autochart")

uploaded = st.file_uploader("Upload a CSV file", type=["csv"])
if uploaded is None:
    st.info("Upload a CSV to start.")
    st.stop()

try:
    df = load_csv(uploaded.getvalue())
except DataLoadError as exc:
    st.error(str(exc))
    st.stop()

schema = extract_schema(df)

with st.expander(f"Schema sent to the model ({schema.n_rows} rows)"):
    st.json(schema.to_prompt_dict())

spec_text = st.text_area(
    "Vega-Lite spec (stand-in for the LLM)",
    value=json.dumps(EXAMPLE_SPEC, indent=2),
    height=250,
)

if st.button("Render chart"):
    try:
        spec = validate(parse_spec(spec_text), schema.column_names)
    except SpecError as exc:
        st.error(f"The chart could not be drawn. {exc}")
        st.stop()
    st.caption(summarize(spec))
    st.vega_lite_chart(df, spec)
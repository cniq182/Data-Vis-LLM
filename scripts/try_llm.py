"""Try generate_spec with a question and then a refinement (multi-turn)."""
from pathlib import Path

from data.loader import extract_schema, load_csv
from llm.client import generate_spec
from render.spec import SpecError, parse_spec, summarize, validate

df = load_csv(Path("sample_data/sales.csv").read_bytes())
schema = extract_schema(df)

current_spec = None
for request in ["What is the total revenue per region?", "Show it as a line over months instead."]:
    result = generate_spec(schema, request, current_spec)
    print(f"\n>>> {request}  ({result.latency_s:.2f} s, {result.total_tokens} tokens)")
    try:
        current_spec = validate(parse_spec(result.text), schema.column_names)
        print("VALID:", summarize(current_spec))
    except SpecError as exc:
        print("INVALID:", exc)
        print(result.text)
        break
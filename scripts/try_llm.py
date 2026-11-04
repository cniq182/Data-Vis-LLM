"""Try the self-healing pipeline with the real model."""
from pathlib import Path

from llm.interaction_log import log_result
from data.loader import extract_schema, load_csv
from llm.pipeline import ask
from render.spec import summarize

df = load_csv(Path("sample_data/sales.csv").read_bytes())
schema = extract_schema(df)

requests = [
    "What is the total revenue per region?",
    "Show it as a line over months instead.",
    "Show the total profit per product.",        # trap: there is no 'profit' column
]

current_spec = None
for request in requests:
    result = ask(schema, request, current_spec)
    log_result(request, result, session_id="try_llm", had_current_spec=current_spec is not None)
    print(f"\n>>> {request}")
    print(f"attempts: {len(result.attempts)} | total latency: {result.total_latency_s:.2f} s")
    for i, attempt in enumerate(result.attempts, start=1):
        print(f"  #{i}: {'OK' if attempt.error is None else 'ERROR: ' + attempt.error}")
    if result.ok:
        current_spec = result.spec
        print("RESULT:", summarize(result.spec))
    elif result.clarification:
        print("CLARIFICATION:", result.clarification)
    else:
        print("FAILED:", result.error)
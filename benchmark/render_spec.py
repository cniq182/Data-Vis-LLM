"""Render the final chart of one benchmark case as an HTML page, for manual review.

It takes the exact spec stored in the results file and attaches the real data
(bikes.csv), like the app does, then opens it with vega-embed in the browser.

Run from the repo root (needs internet for the vega-embed scripts):
    python -m benchmark.render_spec cai flt-02 1649
    (model, case id, time of the run as in the file name: run_cai_20261124-1649.jsonl)
"""

import json
import sys
import webbrowser
from pathlib import Path

import pandas as pd

BENCH_DIR = Path(__file__).parent

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
</head><body style="font-family: sans-serif">
<h3>{title}</h3><p>{signature}</p>
<div id="chart"></div><pre id="error" style="color: red"></pre>
<script>
const spec = {spec};
vegaEmbed("#chart", spec).catch(e => document.getElementById("error").textContent = e);
</script></body></html>"""


def main() -> None:
    model, case_id, run_time = sys.argv[1], sys.argv[2], sys.argv[3]
    files = list((BENCH_DIR / "results").glob(f"run_{model}_*{run_time}.jsonl"))
    if len(files) != 1:
        sys.exit(f"Expected one results file for {model} {run_time}, found {files}")
    with open(files[0], encoding="utf-8") as f:
        row = next(r for r in map(json.loads, f) if r["case_id"] == case_id)
    if not row["final_spec"]:
        sys.exit(f"{case_id} has no chart (outcome: {row['final_outcome']})")

    case = next(c for c in map(json.loads, open(BENCH_DIR / "cases.jsonl", encoding="utf-8"))
                if c["id"] == case_id)
    df = pd.read_csv(BENCH_DIR / "datasets" / case["dataset"])
    spec = dict(row["final_spec"])
    spec["data"] = {"values": json.loads(df.to_json(orient="records"))}

    out = BENCH_DIR / "results" / f"review_{model}_{case_id}_{run_time}.html"
    out.write_text(HTML.format(
        title=f"{model} {case_id} ({run_time}): {' / '.join(case['turns'])}",
        signature=row["signature"],
        spec=json.dumps(spec),
    ), encoding="utf-8")
    print(f"Saved {out}")
    webbrowser.open(out.resolve().as_uri())


if __name__ == "__main__":
    main()
"""Summary tables for the paper: accuracy, consistency, latency and tokens
per model, dataset and category, over ALL runs in benchmark/results/.

- Results files run_<model>_<stamp>.jsonl may contain any subset of cases
  (e.g. the bikes cases in some runs, the shop cases in others).
- "Run k" of a case = its k-th execution (in time order) for that model.
- Manual review (benchmark/manual_review.jsonl): a verdict applies to an
  execution only if it produced the SAME answer (outcome + chart meaning) as
  the reviewed one (the "run" file, or by default the first execution).
  New, different failures are listed as "not reviewed".

Run from the repo root:
    python -m benchmark.summarize
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

BENCH_DIR = Path(__file__).parent
RESULTS_DIR = BENCH_DIR / "results"
REVIEW_PATH = BENCH_DIR / "manual_review.jsonl"
CASES_PATH = BENCH_DIR / "cases.jsonl"
OUT_PATH = RESULTS_DIR / "summary.md"

CATEGORY_ORDER = ["aggregation", "temporal", "filter", "multi-turn", "unanswerable"]


def wilson_ci(k: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson confidence interval for a proportion k/n (good for small n)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def answer_key(row: dict) -> tuple:
    """What the system answered: outcome + meaning of the chart."""
    return (row["final_outcome"], row.get("signature"))


def load_executions():
    """{model: {case_id: [row of run 1, row of run 2, ...]}} in time order."""
    dataset_of = {}
    with open(CASES_PATH, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                c = json.loads(line)
                dataset_of[c["id"]] = c["dataset"]
    execs: dict[str, dict[str, list]] = {}
    for f in sorted(RESULTS_DIR.glob("run_*.jsonl")):   # sorted -> oldest first
        model = f.stem[len("run_"):].rsplit("_", 1)[0]
        with open(f, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        for r in rows:
            r["_file"] = f.name
            r["dataset"] = dataset_of.get(r["case_id"], "?")
            execs.setdefault(model, {}).setdefault(r["case_id"], []).append(r)
        print(f"{model:12} <- {f.name} ({len(rows)} cases)")
    # Study model first, then the others alphabetically.
    return dict(sorted(execs.items(), key=lambda kv: (kv[0] != "cai", kv[0])))


def load_review(execs) -> dict[tuple[str, str], list]:
    if not REVIEW_PATH.exists():
        return {}
    with open(REVIEW_PATH, encoding="utf-8") as fh:
        reviews = [json.loads(line) for line in fh if line.strip()]
    out: dict[tuple[str, str], list] = {}
    for rv in reviews:
        rows = execs.get(rv["model"], {}).get(rv["case_id"], [])
        if rv.get("run"):
            ref = next((r for r in rows if r["_file"] == rv["run"]), None)
        else:
            ref = rows[0] if rows else None
        rv = dict(rv, reviewed_answer=answer_key(ref) if ref else None)
        out.setdefault((rv["model"], rv["case_id"]), []).append(rv)
    return out


def verdict(row: dict, review: dict) -> tuple[bool, dict | None]:
    for rv in review.get((row["model"], row["case_id"]), []):
        if rv["reviewed_answer"] == answer_key(row):
            return rv["manual_pass"], rv
    return row["auto_pass"], None


def fmt(x, digits=1) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def model_row(label: str, cases: dict[str, list], review: dict) -> str:
    """One table row for a set of cases (each with its list of executions)."""
    n_q = len(cases)
    n_runs = min(len(v) for v in cases.values())
    auto_k = [sum(v[i]["auto_pass"] for v in cases.values()) for i in range(n_runs)]
    rev_k = [sum(verdict(v[i], review)[0] for v in cases.values()) for i in range(n_runs)]
    mean_k = float(np.mean(rev_k))
    lo, hi = wilson_ci(mean_k, n_q)
    consistent = sum(len({answer_key(r) for r in v}) == 1 for v in cases.values())
    rows = [r for v in cases.values() for r in v]
    lat = [r["wall_s"] for r in rows if r["wall_s"] is not None]
    tin = [r["prompt_tokens"] for r in rows if r["prompt_tokens"] is not None]
    tout = [r["completion_tokens"] for r in rows if r["completion_tokens"] is not None]
    att = [r["n_attempts"] for r in rows if r["n_attempts"] is not None]
    return (
        f"| {label} | {n_q} | {n_runs} "
        f"| {', '.join(map(str, auto_k))} | {', '.join(map(str, rev_k))} "
        f"| {100 * mean_k / n_q:.0f}% | {100*lo:.0f}–{100*hi:.0f}% "
        f"| {consistent}/{n_q} "
        f"| {fmt(np.median(lat) if lat else None)} "
        f"| {fmt(np.percentile(lat, 90) if lat else None)} "
        f"| {fmt(np.mean(tin) if tin else None, 0)} "
        f"| {fmt(np.mean(tout) if tout else None, 0)} "
        f"| {fmt(np.mean(att) if att else None, 2)} |"
    )


HEADER = [
    "| Model | Questions | Runs | Correct per run (auto) | Correct per run (reviewed) "
    "| Mean accuracy (reviewed) | 95% CI | Consistent cases "
    "| Latency median (s) | Latency P90 (s) | Input tokens (mean) "
    "| Output tokens (mean) | Attempts (mean) |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
]


def main() -> None:
    execs = load_executions()
    review = load_review(execs)
    datasets = sorted({r["dataset"] for m in execs.values() for v in m.values() for r in v})
    lines = ["# autochart benchmark – summary", ""]

    # ---- Table 1: all questions together ---------------------------------
    lines += ["## All datasets together", ""] + HEADER
    for model, cases in execs.items():
        lines.append(model_row(model, cases, review))

    # ---- Table 2: per dataset ---------------------------------------------
    for ds in datasets:
        lines += ["", f"## Dataset {ds}", ""] + HEADER
        for model, cases in execs.items():
            sub = {cid: v for cid, v in cases.items() if v[0]["dataset"] == ds}
            if sub:
                lines.append(model_row(model, sub, review))

    # ---- Table 3: reviewed accuracy per category -------------------------
    models = list(execs)
    lines += ["", "## Reviewed accuracy per category (correct / questions x runs)", "",
              "| Category | " + " | ".join(models) + " |",
              "|---|" + "---|" * len(models)]
    for cat in CATEGORY_ORDER:
        cells = []
        for model in models:
            rows = [r for v in execs[model].values() for r in v if r["category"] == cat]
            k = sum(verdict(r, review)[0] for r in rows)
            cells.append(f"{k}/{len(rows)}")
        lines.append(f"| {cat} | " + " | ".join(cells) + " |")

    # ---- Table 4: every failure after review -----------------------------
    lines += ["", "## Failures after manual review", "",
              "| Model | Run | Case | Outcome | Type | Note |",
              "|---|---|---|---|---|---|"]
    n_not_reviewed = 0
    for model, cases in execs.items():
        for cid, runs in cases.items():
            for i, r in enumerate(runs, 1):
                passed, rv = verdict(r, review)
                if passed:
                    continue
                if rv is None:
                    n_not_reviewed += 1
                lines.append(
                    f"| {model} | {i} | {cid} | {r['final_outcome']} "
                    f"| {rv['failure_type'] if rv else '**not reviewed**'} "
                    f"| {rv['note'] if rv else r['auto_reason']} |")

    lines += [
        "",
        "Notes: run k = k-th execution of each question, temperature 0. Mean accuracy = "
        "mean over runs; the CI uses n = number of distinct questions, because repeating "
        "the same questions does not add new questions. Consistent cases = same outcome "
        "and chart meaning in every run. Latency = wall-clock time per question (all turns "
        "and retries), over all runs. Tokens = sum over all LLM calls of a question.",
    ]
    if n_not_reviewed:
        lines.append(f"\n**{n_not_reviewed} failure(s) not reviewed yet.**")

    text = "\n".join(lines)
    OUT_PATH.write_text(text + "\n", encoding="utf-8")
    print()
    print(text)
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
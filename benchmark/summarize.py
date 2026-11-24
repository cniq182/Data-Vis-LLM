"""Summary tables for the paper: accuracy, latency and tokens per model and category.

Reads the latest run file of each model in benchmark/results/ and the manual
review (benchmark/manual_review.jsonl), and writes benchmark/results/summary.md.

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
OUT_PATH = RESULTS_DIR / "summary.md"

CATEGORY_ORDER = ["aggregation", "temporal", "filter", "multi-turn", "unanswerable"]


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson confidence interval for a proportion k/n (good for small n)."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_latest_runs() -> dict[str, list[dict]]:
    """{model: rows} using only the most recent run file of each model."""
    latest: dict[str, Path] = {}
    for f in sorted(RESULTS_DIR.glob("run_*.jsonl")):   # sorted -> newest last
        model = f.stem[len("run_"):].rsplit("_", 1)[0]
        latest[model] = f
    runs = {}
    # Study model first, then the others alphabetically.
    for model, f in sorted(latest.items(), key=lambda kv: (kv[0] != "cai", kv[0])):
        with open(f, encoding="utf-8") as fh:
            runs[model] = [json.loads(line) for line in fh if line.strip()]
        print(f"{model:12} <- {f.name} ({len(runs[model])} cases)")
    return runs


def load_review() -> dict[tuple[str, str], dict]:
    if not REVIEW_PATH.exists():
        return {}
    with open(REVIEW_PATH, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return {(r["model"], r["case_id"]): r for r in rows}


def final_pass(row: dict, review: dict) -> bool:
    """Manual verdict if the case was reviewed, otherwise the automatic one."""
    r = review.get((row["model"], row["case_id"]))
    return r["manual_pass"] if r else row["auto_pass"]


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.0f}%" if n else "-"


def fmt(x, digits=1) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{digits}f}"


def main() -> None:
    runs = load_latest_runs()
    review = load_review()
    lines = ["# autochart benchmark – summary", ""]

    # ---- Table 1: one row per model -------------------------------------
    lines += [
        "## Per model",
        "",
        "| Model | n | Accuracy (auto) | Accuracy (reviewed) | 95% CI (reviewed) "
        "| Latency median (s) | Latency P90 (s) | Input tokens (mean) "
        "| Output tokens (mean) | Attempts (mean) | Chart type OK |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for model, rows in runs.items():
        n = len(rows)
        k_auto = sum(r["auto_pass"] for r in rows)
        k_rev = sum(final_pass(r, review) for r in rows)
        lo, hi = wilson_ci(k_rev, n)
        lat = [r["wall_s"] for r in rows if r["wall_s"] is not None]
        tin = [r["prompt_tokens"] for r in rows if r["prompt_tokens"] is not None]
        tout = [r["completion_tokens"] for r in rows if r["completion_tokens"] is not None]
        att = [r["n_attempts"] for r in rows if r["n_attempts"] is not None]
        charts = [r for r in rows if r["mark_ok"] is not None]
        lines.append(
            f"| {model} | {n} | {pct(k_auto, n)} ({k_auto}/{n}) "
            f"| {pct(k_rev, n)} ({k_rev}/{n}) | {100*lo:.0f}–{100*hi:.0f}% "
            f"| {fmt(np.median(lat) if lat else None)} "
            f"| {fmt(np.percentile(lat, 90) if lat else None)} "
            f"| {fmt(np.mean(tin) if tin else None, 0)} "
            f"| {fmt(np.mean(tout) if tout else None, 0)} "
            f"| {fmt(np.mean(att) if att else None, 2)} "
            f"| {pct(sum(r['mark_ok'] for r in charts), len(charts))} |"
        )

    # ---- Table 2: reviewed accuracy per category -------------------------
    models = list(runs)
    lines += [
        "",
        "## Reviewed accuracy per category",
        "",
        "| Category | n | " + " | ".join(models) + " |",
        "|---|---|" + "---|" * len(models),
    ]
    for cat in CATEGORY_ORDER:
        cells, n_cat = [], None
        for model in models:
            rows = [r for r in runs[model] if r["category"] == cat]
            n_cat = len(rows)
            k = sum(final_pass(r, review) for r in rows)
            cells.append(f"{k}/{len(rows)}")
        lines.append(f"| {cat} | {n_cat} | " + " | ".join(cells) + " |")

    # ---- Table 3: list of failures (after review) ------------------------
    lines += ["", "## Failures after manual review", "",
              "| Model | Case | Outcome | Type | Note |", "|---|---|---|---|---|"]
    for model, rows in runs.items():
        for r in rows:
            if final_pass(r, review):
                continue
            rv = review.get((model, r["case_id"]), {})
            note = rv.get("note") or r["auto_reason"]
            lines.append(f"| {model} | {r['case_id']} | {r['final_outcome']} "
                         f"| {rv.get('failure_type', 'not reviewed')} | {note} |")

    lines += [
        "",
        "Notes: latency = wall-clock time per case, all turns and retries included "
        "(multi-turn cases add up their turns). Tokens = sum over all LLM calls of the "
        "case. Accuracy (reviewed) = manual verdict where a failure was reviewed, "
        "automatic verdict otherwise. 1 run per model, temperature 0.",
    ]

    text = "\n".join(lines)
    OUT_PATH.write_text(text + "\n", encoding="utf-8")
    print()
    print(text)
    print(f"\nSaved to {OUT_PATH}")


if __name__ == "__main__":
    main()
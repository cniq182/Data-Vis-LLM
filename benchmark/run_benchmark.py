"""Run the autochart benchmark: every case x every model, results to JSONL.

The frozen system (study-v1) is NOT modified. We only *call* it:
- llm.pipeline.ask(...)  -> the same self-healing loop the app uses
- generate=<our function> -> same prompt and settings as llm.client.generate_spec,
                             but with another model name, and it also records
                             input/output tokens separately.

Usage (from the repo root, on DTU campus or VPN):
    python -m benchmark.run_benchmark                       # cai, all cases
    python -m benchmark.run_benchmark --models cai cai-instant cai-mini
    python -m benchmark.run_benchmark --cases agg-01 mt-04  # only some cases

Output: one file per model and run, e.g.
    benchmark/results/run_cai_20261124-1100.jsonl   (one line per case)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from data.loader import extract_schema, load_csv
from llm.client import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    TEMPERATURE,
    LLMResult,
    _client,
    build_user_message,
)
from llm.pipeline import ask

from benchmark.grader import grade

BENCH_DIR = Path(__file__).parent
CASES_PATH = BENCH_DIR / "cases.jsonl"
DATASETS_DIR = BENCH_DIR / "datasets"
RESULTS_DIR = BENCH_DIR / "results"

# Same settings as the app (study-v1).
MAX_ATTEMPTS = 3
TIME_BUDGET_S = 60

# Every LLM call made by our generate function is appended here, so we can
# read the input/output tokens of each call afterwards.
CALLS: list[dict] = []


# ---------------------------------------------------------------------------
# Our own generate function: identical to llm.client.generate_spec except
# (1) the model name is a parameter and (2) tokens are recorded separately.
# ---------------------------------------------------------------------------
def make_generate(model: str):
    def generate(schema, question, current_spec=None, feedback=None) -> LLMResult:
        start = time.perf_counter()
        response = _client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(
                    schema, question, current_spec, feedback)},
            ],
            temperature=TEMPERATURE,
        )
        latency = time.perf_counter() - start
        usage = response.usage
        CALLS.append({
            "latency_s": round(latency, 3),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        })
        return LLMResult(
            text=response.choices[0].message.content or "",
            model=model,
            latency_s=latency,
            total_tokens=usage.total_tokens if usage else None,
        )
    return generate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_cases(only_ids: list[str] | None) -> list[dict]:
    with open(CASES_PATH, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]
    if only_ids:
        cases = [c for c in cases if c["id"] in only_ids]
    return cases


_SCHEMAS: dict = {}


def get_schema(dataset: str):
    """Load each dataset once, exactly as the app does (load_csv on bytes)."""
    if dataset not in _SCHEMAS:
        df = load_csv((DATASETS_DIR / dataset).read_bytes())
        _SCHEMAS[dataset] = extract_schema(df)
    return _SCHEMAS[dataset]


def git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return None


def _sum(values):
    values = [v for v in values if v is not None]
    return sum(values) if values else None


# ---------------------------------------------------------------------------
# Run one case (one or more turns) with one model
# ---------------------------------------------------------------------------
def run_case(case: dict, model: str, generate) -> dict:
    schema = get_schema(case["dataset"])
    current_spec = None          # chart shown on screen after each turn
    pending_clarification = None
    clarified_question = None    # question that triggered the clarification
    turns_log = []
    case_start = time.perf_counter()

    for question in case["turns"]:
        n_calls_before = len(CALLS)
        turn_start = time.perf_counter()
        try:
            result = ask(
                schema, question, current_spec,
                previous_clarification=pending_clarification,
                previous_question=clarified_question,
                generate=generate,
                max_attempts=MAX_ATTEMPTS,
                time_budget_s=TIME_BUDGET_S,
            )
            crash = None
        except Exception as e:   # network error, timeout, ...
            result, crash = None, f"{type(e).__name__}: {e}"
        wall_s = time.perf_counter() - turn_start
        calls = CALLS[n_calls_before:]

        if result is not None and result.ok:
            outcome = "chart"
            current_spec = result.spec
            pending_clarification, clarified_question = None, None
        elif result is not None and result.clarification:
            outcome = "clarification"
            # Like the app: the reply to a clarification carries the original question.
            clarified_question = clarified_question or question
            pending_clarification = result.clarification
        else:
            outcome = "failure"

        turns_log.append({
            "question": question,
            "outcome": outcome,
            "n_attempts": len(result.attempts) if result else len(calls),
            "latency_s": round(result.total_latency_s, 3) if result else None,
            "wall_s": round(wall_s, 3),
            "prompt_tokens": _sum(c["prompt_tokens"] for c in calls),
            "completion_tokens": _sum(c["completion_tokens"] for c in calls),
            "total_tokens": _sum(c["total_tokens"] for c in calls),
            "clarification": result.clarification if result else None,
            "error": crash or (result.error if result else None),
            "attempt_errors": [a.error for a in result.attempts] if result else [],
            "spec": result.spec if (result and result.ok) else None,
        })

    final = turns_log[-1]
    g = grade(case["expected"], final["outcome"], final["spec"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": git_commit(),
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "temperature": TEMPERATURE,
        "max_attempts": MAX_ATTEMPTS,
        "time_budget_s": TIME_BUDGET_S,
        "case_id": case["id"],
        "category": case["category"],
        "n_turns": len(case["turns"]),
        # --- result -------------------------------------------------------
        "final_outcome": final["outcome"],
        "final_spec": final["spec"],
        "auto_pass": g.passed,
        "auto_reason": g.reason,
        "mark_ok": g.mark_ok,
        "signature": g.signature,
        "manual_verdict": None,   # filled in by hand when reviewing failures
        "manual_note": None,
        # --- cost and speed (all turns, retries included) -----------------
        "latency_s": _sum(t["latency_s"] for t in turns_log),
        "wall_s": round(time.perf_counter() - case_start, 3),
        "n_attempts": _sum(t["n_attempts"] for t in turns_log),
        "prompt_tokens": _sum(t["prompt_tokens"] for t in turns_log),
        "completion_tokens": _sum(t["completion_tokens"] for t in turns_log),
        "total_tokens": _sum(t["total_tokens"] for t in turns_log),
        "turns": turns_log,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Run the autochart benchmark.")
    parser.add_argument("--models", nargs="+", default=["cai"],
                        help="model names on CampusAI (default: cai)")
    parser.add_argument("--cases", nargs="*", default=None,
                        help="only run these case ids (default: all)")
    parser.add_argument("--dataset", default=None,
                        help="only run the cases of this dataset, e.g. shop.csv")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.dataset:
        cases = [c for c in cases if c["dataset"] == args.dataset]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    print(f"{len(cases)} cases x {len(args.models)} model(s), prompt {PROMPT_VERSION}, "
          f"commit {git_commit()}")

    for model in args.models:
        out_path = RESULTS_DIR / f"run_{model}_{stamp}.jsonl"
        generate = make_generate(model)
        n_pass = 0
        print(f"\n=== {model} -> {out_path}")
        with open(out_path, "w", encoding="utf-8") as out:
            for i, case in enumerate(cases, 1):
                row = run_case(case, model, generate)
                # Write each case at once, so a crash does not lose earlier results.
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                n_pass += row["auto_pass"]
                status = "PASS" if row["auto_pass"] else "FAIL"
                print(f"[{i:2}/{len(cases)}] {case['id']:7} {status}  "
                      f"{row['final_outcome']:13} {row['wall_s']:6.1f}s  "
                      f"{row['total_tokens'] or '-':>6} tok  {row['auto_reason']}")
        print(f"--- {model}: {n_pass}/{len(cases)} passed (automatic grading)")


if __name__ == "__main__":
    main()
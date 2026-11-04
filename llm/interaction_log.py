"""Append one JSON line per chart request to a log file (data for evaluation)."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm.client import MODEL, TEMPERATURE
from llm.pipeline import ChartResult

LOG_DIR = Path("logs")


def log_result(
    question: str,
    result: ChartResult,
    *,
    session_id: str,
    had_current_spec: bool,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Write one record to logs/<session_id>.jsonl and return it."""
    if result.ok:
        outcome = "chart"
    elif result.clarification:
        outcome = "clarification"
    else:
        outcome = "failure"

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_id": session_id,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "question": question,
        "had_current_spec": had_current_spec,     # True = refinement turn
        "outcome": outcome,
        "n_attempts": len(result.attempts),
        "total_latency_s": round(result.total_latency_s, 3),
        "total_tokens": sum(a.total_tokens or 0 for a in result.attempts),
        "error": result.error,
        "clarification": result.clarification,
        "final_spec": result.spec,
        "attempts": [asdict(a) for a in result.attempts],
    }

    path = log_path or LOG_DIR / f"{session_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
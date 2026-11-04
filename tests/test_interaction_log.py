import json

from llm.interaction_log import log_result
from llm.pipeline import Attempt, ChartResult


def test_log_appends_one_line_per_request(tmp_path) -> None:
    result = ChartResult(
        spec={"mark": "bar"},
        attempts=[
            Attempt("bad", "Unknown field", 1.5, 100),
            Attempt("{}", None, 2.0, 120),
        ],
    )
    path = tmp_path / "s1.jsonl"

    log_result("q1", result, session_id="s1", had_current_spec=False, log_path=path)
    log_result("q2", result, session_id="s1", had_current_spec=True, log_path=path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2                      # appended, not overwritten
    record = json.loads(lines[0])
    assert record["outcome"] == "chart"
    assert record["n_attempts"] == 2
    assert record["total_latency_s"] == 3.5
    assert record["total_tokens"] == 220
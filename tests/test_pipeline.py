import json

from data.loader import extract_schema, load_csv
from llm.client import LLMResult
from llm.pipeline import ask

SCHEMA = extract_schema(load_csv(b"region,revenue\nNorth,10\nSouth,20\n"))
GOOD = json.dumps({
    "mark": "bar",
    "encoding": {
        "x": {"field": "region", "type": "nominal"},
        "y": {"field": "revenue", "aggregate": "sum", "type": "quantitative"},
    },
})


def scripted(*answers: str):
    """Fake generator: returns the given answers in order and records the feedback it got."""
    calls: list = []

    def generate(schema, question, current_spec, feedback):
        calls.append(feedback)
        return LLMResult(text=answers[len(calls) - 1], model="fake", latency_s=1.0, total_tokens=10)

    return generate, calls


def test_valid_on_first_try() -> None:
    generate, calls = scripted(GOOD)
    result = ask(SCHEMA, "q", generate=generate)
    assert result.ok
    assert len(result.attempts) == 1
    assert calls == [None]                     # no feedback needed


def test_recovers_after_unknown_field() -> None:
    bad = json.dumps({"mark": "bar", "encoding": {"x": {"field": "Region", "type": "nominal"}}})
    generate, calls = scripted(bad, GOOD)
    result = ask(SCHEMA, "q", generate=generate)
    assert result.ok
    assert len(result.attempts) == 2
    assert "Available columns" in calls[1].error   # the error was sent back to the model
    assert result.total_latency_s == 2.0


def test_gives_up_after_max_attempts() -> None:
    generate, _ = scripted("not json", "not json", "not json")
    result = ask(SCHEMA, "q", generate=generate, max_attempts=3)
    assert not result.ok
    assert len(result.attempts) == 3
    assert result.error is not None

def test_clarification_is_returned_without_retry() -> None:
    generate, calls = scripted('{"clarification": "There is no profit column."}')
    result = ask(SCHEMA, "q", generate=generate)
    assert not result.ok
    assert result.clarification == "There is no profit column."
    assert len(calls) == 1          # not treated as an error, so no retry
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
    generate, _ = scripted("not json", "still not json", "{broken")   # three different bad answers
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

def test_previous_clarification_is_sent_with_the_reply() -> None:
    seen: list[str] = []

    def generate(schema, question, current_spec, feedback):
        seen.append(question)
        return LLMResult(text=GOOD, model="fake", latency_s=0.0, total_tokens=0)

    ask(SCHEMA, "yes", generate=generate, previous_clarification="Bar chart per port instead?")
    assert "Bar chart per port instead?" in seen[0]
    assert "yes" in seen[0]

def test_stops_early_when_retry_repeats_the_same_spec() -> None:
    bad = json.dumps({"mark": "bar", "encoding": {"x": {"field": "Region", "type": "nominal"}}})
    same_bad_reformatted = json.dumps(json.loads(bad), indent=2)   # same spec, different spacing
    generate, calls = scripted(bad, same_bad_reformatted, GOOD)
    result = ask(SCHEMA, "q", generate=generate)
    assert not result.ok
    assert len(calls) == 2                 # the third attempt is never made
    assert "repeated" in result.error


def test_stops_when_time_budget_would_be_exceeded() -> None:
    generate, calls = scripted("not json", "{broken", GOOD)   # each fake answer "takes" 1.0 s
    result = ask(SCHEMA, "q", generate=generate, time_budget_s=1.5)
    assert not result.ok
    assert len(calls) == 1               # a second attempt (1 s + ~1 s) would exceed 1.5 s
    assert "long wait" in result.error
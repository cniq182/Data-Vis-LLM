"""Ask for a chart and recover automatically from invalid specs (self-healing)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import openai
import json

from data.loader import DatasetSchema
from llm.client import Feedback, LLMResult, generate_spec
from render.spec import SpecError, parse_spec, validate

MAX_ATTEMPTS = 3

def _canonical(text: str) -> str:
    """Normalize an answer so that formatting differences don't count as changes."""
    try:
        return json.dumps(parse_spec(text), sort_keys=True)
    except SpecError:
        return text.strip()

Generator = Callable[
    [DatasetSchema, str, dict[str, Any] | None, Feedback | None], LLMResult
]


@dataclass(frozen=True)
class Attempt:
    raw_text: str
    error: str | None          # None means this attempt produced a valid spec
    latency_s: float
    total_tokens: int | None
    error_detail: str | None = None   # full error for the log (never sent to the model)


@dataclass(frozen=True)
class ChartResult:
    spec: dict[str, Any] | None
    attempts: list[Attempt]
    error: str | None = None           # user-facing message when no valid spec
    clarification: str | None = None   # model says the data cannot answer the request
    error_detail: str | None = None    # full technical error (e.g. network), for the log

    @property
    def ok(self) -> bool:
        return self.spec is not None

    @property
    def total_latency_s(self) -> float:
        return sum(a.latency_s for a in self.attempts)

def ask(
    schema: DatasetSchema,
    question: str,
    current_spec: dict[str, Any] | None = None,
    *,
    previous_clarification: str | None = None,
    generate: Generator = generate_spec,
    max_attempts: int = MAX_ATTEMPTS,
) -> ChartResult:
    """Generate a valid spec, feeding validation errors back to the model."""
    if previous_clarification:
        # The model has no memory: restate the clarification it gave last turn.
        question = (
            f'You previously asked the user: "{previous_clarification}"\n'
            f'The user replied: "{question}"'
        )

    attempts: list[Attempt] = []
    feedback: Feedback | None = None

    for _ in range(max_attempts):
        try:
            result = generate(schema, question, current_spec, feedback)
        except openai.APIError as exc:
            # Network or server problem: retrying the prompt will not help.
            return ChartResult(
                None, attempts,
                f"The language model could not be reached ({type(exc).__name__}).",
                error_detail=str(exc),
            )

        try:
            parsed = parse_spec(result.text)
            if isinstance(parsed.get("clarification"), str):
                attempts.append(Attempt(result.text, None, result.latency_s, result.total_tokens))
                return ChartResult(None, attempts, clarification=parsed["clarification"])
            spec = validate(parsed, schema.column_names)
        except SpecError as exc:
            attempts.append(Attempt(result.text, str(exc), result.latency_s, result.total_tokens, exc.detail))

            if feedback is not None and _canonical(result.text) == _canonical(feedback.previous_answer):
                # Same invalid answer as last time: another retry will not help.
                return ChartResult(
                    None, attempts,
                    "The model repeated the same invalid chart. Try rephrasing the question.",
                )
            feedback = Feedback(previous_answer=result.text, error=str(exc))
            continue

        # Valid spec: done.
        attempts.append(Attempt(result.text, None, result.latency_s, result.total_tokens))
        return ChartResult(spec, attempts)

    return ChartResult(
        None, attempts,
        f"No valid chart after {max_attempts} attempts. Try rephrasing the question.",
    )
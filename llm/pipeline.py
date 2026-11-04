"""Ask for a chart and recover automatically from invalid specs (self-healing)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import openai

from data.loader import DatasetSchema
from llm.client import Feedback, LLMResult, generate_spec
from render.spec import SpecError, parse_spec, validate

MAX_ATTEMPTS = 3

Generator = Callable[
    [DatasetSchema, str, dict[str, Any] | None, Feedback | None], LLMResult
]


@dataclass(frozen=True)
class Attempt:
    raw_text: str
    error: str | None          # None means this attempt produced a valid spec
    latency_s: float
    total_tokens: int | None


@dataclass(frozen=True)
class ChartResult:
    spec: dict[str, Any] | None
    attempts: list[Attempt]
    error: str | None = None   # user-facing message when no valid spec

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
    generate: Generator = generate_spec,
    max_attempts: int = MAX_ATTEMPTS,
) -> ChartResult:
    """Generate a valid spec, feeding validation errors back to the model."""
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
            )

        try:
            spec = validate(parse_spec(result.text), schema.column_names)
        except SpecError as exc:
            attempts.append(Attempt(result.text, str(exc), result.latency_s, result.total_tokens))
            feedback = Feedback(previous_answer=result.text, error=str(exc))
            continue

        attempts.append(Attempt(result.text, None, result.latency_s, result.total_tokens))
        return ChartResult(spec, attempts)

    return ChartResult(
        None, attempts,
        f"No valid chart after {max_attempts} attempts. Try rephrasing the question.",
    )
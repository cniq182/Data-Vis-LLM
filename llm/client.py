"""LLM access: turn a question and a dataset schema into a raw Vega-Lite spec."""
from __future__ import annotations

import json
import time
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from openai import OpenAI

from data.loader import DatasetSchema

MODEL = "cai"
TEMPERATURE = 0.0
TIMEOUT_S = 30.0
SECRETS_PATH = Path(".streamlit/secrets.toml")

SYSTEM_PROMPT = """You turn questions about a tabular dataset into Vega-Lite v5 specs.
Rules:
- Answer with ONE JSON object and nothing else: no explanations, no markdown.
- Never include a "data" key. The data is attached later by the application.
- Use only column names that appear in the schema, spelled exactly.
- Use Vega-Lite aggregate, timeUnit, bin and filter to transform data.
- If a current chart spec is given, modify it to satisfy the request
  instead of starting from scratch, and keep everything else unchanged."""


@dataclass(frozen=True)
class LLMResult:
    text: str                 # raw model output, to be parsed and validated
    model: str
    latency_s: float
    total_tokens: int | None

@dataclass(frozen=True)
class Feedback:
    """A rejected answer and the reason, sent back so the model can fix it."""
    previous_answer: str
    error: str

@lru_cache(maxsize=1)
def _client() -> OpenAI:
    secrets = tomllib.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    return OpenAI(
        api_key=secrets["CAMPUSAI_API_KEY"],
        base_url=secrets["CAMPUSAI_BASE_URL"],
        timeout=TIMEOUT_S,
    )


def build_user_message(
    schema: DatasetSchema,
    question: str,
    current_spec: dict[str, Any] | None,
    feedback: Feedback | None = None,
) -> str:
    parts = [f"Dataset schema:\n{json.dumps(schema.to_prompt_dict(), indent=2)}"]
    if current_spec is not None:
        parts.append(f"Current chart spec:\n{json.dumps(current_spec, indent=2)}")
    parts.append(f"Request: {question}")
    if feedback is not None:
        parts.append(
            f"Your previous answer was:\n{feedback.previous_answer}\n"
            f"It was rejected with this error:\n{feedback.error}\n"
            "Return a corrected spec."
        )
    return "\n\n".join(parts)


def generate_spec(
    schema: DatasetSchema,
    question: str,
    current_spec: dict[str, Any] | None = None,
    feedback: Feedback | None = None,
) -> LLMResult:
    """Ask the model for a Vega-Lite spec. Raises openai errors on network failure."""
    start = time.perf_counter()
    response = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(schema, question, current_spec, feedback)},
        ],
        temperature=TEMPERATURE,
    )
    return LLMResult(
        text=response.choices[0].message.content or "",
        model=MODEL,
        latency_s=time.perf_counter() - start,
        total_tokens=response.usage.total_tokens if response.usage else None,
    )
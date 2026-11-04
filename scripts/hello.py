"""Send a first message to each candidate model and measure latency."""
import time
import tomllib
from pathlib import Path

from openai import OpenAI

CANDIDATES = ["cai-instant", "cai-mini", "cai"]

secrets = tomllib.loads(Path(".streamlit/secrets.toml").read_text(encoding="utf-8"))
client = OpenAI(
    api_key=secrets["CAMPUSAI_API_KEY"],
    base_url=secrets["CAMPUSAI_BASE_URL"],
)

for alias in CANDIDATES:
    start = time.perf_counter()
    # POST /v1/chat/completions: the same call as the curl example.
    response = client.chat.completions.create(
        model=alias,
        messages=[{"role": "user", "content": "Say hello in one short sentence."}],
        temperature=0,
    )
    seconds = time.perf_counter() - start

    print(f"--- {alias} ---")
    print(f"real model : {response.model}")
    print(f"latency    : {seconds:.2f} s")
    print(f"tokens     : {response.usage.total_tokens if response.usage else 'n/a'}")
    print(f"answer     : {response.choices[0].message.content}")
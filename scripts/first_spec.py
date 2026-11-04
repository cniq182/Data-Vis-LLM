"""First end-to-end test: CSV -> schema -> LLM -> spec -> validation."""
import json
import time
import tomllib
from pathlib import Path

from openai import OpenAI

from data.loader import extract_schema, load_csv
from render.spec import SpecError, parse_spec, summarize, validate

MODEL = "cai"
QUESTION = "What is the total revenue per region?"

SYSTEM_PROMPT = """You turn questions about a tabular dataset into Vega-Lite v5 specs.
Rules:
- Answer with ONE JSON object and nothing else: no explanations, no markdown.
- Never include a "data" key. The data is attached later by the application.
- Use only column names that appear in the schema, spelled exactly.
- Use Vega-Lite aggregate, timeUnit, bin and filter to transform data."""

# 1. Read the CSV and extract the schema (the only thing the model sees).
df = load_csv(Path("sample_data/sales.csv").read_bytes())
schema = extract_schema(df)

user_message = (
    f"Dataset schema:\n{json.dumps(schema.to_prompt_dict(), indent=2)}\n\n"
    f"Question: {QUESTION}"
)

# 2. Call the model.
secrets = tomllib.loads(Path(".streamlit/secrets.toml").read_text(encoding="utf-8"))
client = OpenAI(api_key=secrets["CAMPUSAI_API_KEY"], base_url=secrets["CAMPUSAI_BASE_URL"])

start = time.perf_counter()
response = client.chat.completions.create(
    model=MODEL,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ],
    temperature=0,
)
seconds = time.perf_counter() - start
raw = response.choices[0].message.content or ""

print(f"latency: {seconds:.2f} s | tokens: {response.usage.total_tokens if response.usage else 'n/a'}")
print("--- raw answer ---")
print(raw)

# 3. Validate with the same code the app will use.
print("--- validation ---")
try:
    spec = validate(parse_spec(raw), schema.column_names)
    print("VALID:", summarize(spec))
except SpecError as exc:
    print("INVALID:", exc)
    
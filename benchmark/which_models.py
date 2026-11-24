"""Ask CampusAI which real model is behind each alias.

Run from the repo root, on DTU campus or VPN:
    python -m benchmark.which_models
"""

from llm.client import _client

ALIASES = ["cai", "cai-instant", "cai-mini"]

client = _client()

print("Models listed by the API:")
for m in client.models.list().data:
    print("  ", m.id)

print("\nAlias -> model that actually answered:")
for alias in ALIASES:
    response = client.chat.completions.create(
        model=alias,
        messages=[{"role": "user", "content": "Reply with the word OK."}],
        temperature=0,
    )
    print(f"   {alias:12} -> {response.model}")
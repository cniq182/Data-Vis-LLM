"""Send N small requests to ONE alias, to see which counter grows in the
CampusAI usage page ("Top models").

Run from the repo root, on DTU campus or VPN:
    python -m benchmark.probe_alias cai 10
"""

import sys

from llm.client import _client

alias = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 10

client = _client()
for i in range(n):
    client.chat.completions.create(
        model=alias,
        messages=[{"role": "user", "content": "Reply with the word OK."}],
        temperature=0,
    )
    print(f"{alias}: request {i + 1}/{n} done")
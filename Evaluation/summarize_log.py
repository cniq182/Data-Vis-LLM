import json
import sys
from pathlib import Path

session = sys.argv[1] if len(sys.argv) > 1 else "prepilot2"
path = Path("logs") / f"{session}.jsonl"

with path.open(encoding="utf-8") as f:
    for i, line in enumerate(f, start=1):
        r = json.loads(line)
        q = r["question"].strip()[:60]
        print(f"{i:>2}  {r['outcome']:<13} attempts={r['n_attempts']}  "
              f"{r['total_latency_s']:>5.1f}s  {q}")
        if r["outcome"] == "failure":
            print(f"      error: {r['error']}")
            for a in r.get("attempts", []):
                if a.get("error"):
                    print(f"      - {a['error'][:200]}")
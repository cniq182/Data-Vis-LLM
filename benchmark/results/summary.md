# autochart benchmark – summary

## Per model

| Model | n | Accuracy (auto) | Accuracy (reviewed) | 95% CI (reviewed) | Latency median (s) | Latency P90 (s) | Input tokens (mean) | Output tokens (mean) | Attempts (mean) | Chart type OK |
|---|---|---|---|---|---|---|---|---|---|---|
| cai | 20 | 95% (19/20) | 95% (19/20) | 76–99% | 4.3 | 12.1 | 2335 | 249 | 1.45 | 100% |
| cai-instant | 20 | 90% (18/20) | 95% (19/20) | 76–99% | 3.0 | 4.3 | 2008 | 140 | 1.25 | 100% |
| cai-mini | 20 | 90% (18/20) | 90% (18/20) | 70–97% | 3.2 | 10.1 | 2201 | 261 | 1.30 | 100% |

## Reviewed accuracy per category

| Category | n | cai | cai-instant | cai-mini |
|---|---|---|---|---|
| aggregation | 4 | 4/4 | 4/4 | 4/4 |
| temporal | 4 | 3/4 | 3/4 | 3/4 |
| filter | 4 | 4/4 | 4/4 | 4/4 |
| multi-turn | 4 | 4/4 | 4/4 | 4/4 |
| unanswerable | 4 | 4/4 | 4/4 | 3/4 |

## Failures after manual review

| Model | Case | Outcome | Type | Note |
|---|---|---|---|---|
| cai | tmp-03 | chart | silent error | timeUnit 'weekday' means week-of-year + day, not day of week: ~365 thin bars instead of 7. Valid Vega-Lite, so validation and self-healing cannot catch it (checked visually in the app). |
| cai-instant | tmp-03 | chart | silent error | same 'weekday' error as cai |
| cai-mini | tmp-03 | chart | silent error | same 'weekday' error; first attempt used invalid 'dayofweek' |
| cai-mini | clr-01 | chart | silent substitution | 'average profit' answered with mean(total) instead of asking for clarification |

Notes: latency = wall-clock time per case, all turns and retries included (multi-turn cases add up their turns). Tokens = sum over all LLM calls of the case. Accuracy (reviewed) = manual verdict where a failure was reviewed, automatic verdict otherwise. 1 run per model, temperature 0.

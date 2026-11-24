# autochart benchmark – summary

## All datasets together

| Model | Questions | Runs | Correct per run (auto) | Correct per run (reviewed) | Mean accuracy (reviewed) | 95% CI | Consistent cases | Latency median (s) | Latency P90 (s) | Input tokens (mean) | Output tokens (mean) | Attempts (mean) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cai | 40 | 3 | 38, 35, 39 | 38, 36, 39 | 94% | 82–98% | 35/40 | 6.4 | 21.7 | 2338 | 285 | 1.49 |
| cai-instant | 40 | 3 | 38, 37, 38 | 39, 38, 39 | 97% | 86–99% | 39/40 | 4.2 | 8.4 | 1955 | 145 | 1.25 |
| cai-mini | 40 | 3 | 35, 34, 33 | 35, 35, 33 | 86% | 72–93% | 35/40 | 3.7 | 12.3 | 2146 | 385 | 1.32 |

## Dataset bikes.csv

| Model | Questions | Runs | Correct per run (auto) | Correct per run (reviewed) | Mean accuracy (reviewed) | 95% CI | Consistent cases | Latency median (s) | Latency P90 (s) | Input tokens (mean) | Output tokens (mean) | Attempts (mean) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cai | 20 | 3 | 19, 18, 19 | 19, 18, 19 | 93% | 74–99% | 19/20 | 6.2 | 15.3 | 2391 | 268 | 1.48 |
| cai-instant | 20 | 3 | 18, 18, 18 | 19, 19, 19 | 95% | 76–99% | 20/20 | 3.4 | 6.0 | 2009 | 140 | 1.25 |
| cai-mini | 20 | 3 | 18, 17, 16 | 18, 17, 16 | 85% | 64–95% | 18/20 | 3.2 | 10.3 | 2259 | 296 | 1.33 |

## Dataset shop.csv

| Model | Questions | Runs | Correct per run (auto) | Correct per run (reviewed) | Mean accuracy (reviewed) | 95% CI | Consistent cases | Latency median (s) | Latency P90 (s) | Input tokens (mean) | Output tokens (mean) | Attempts (mean) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cai | 20 | 3 | 19, 17, 20 | 19, 18, 20 | 95% | 76–99% | 16/20 | 8.0 | 23.8 | 2286 | 302 | 1.50 |
| cai-instant | 20 | 3 | 20, 19, 20 | 20, 19, 20 | 98% | 81–100% | 19/20 | 4.8 | 9.3 | 1901 | 150 | 1.25 |
| cai-mini | 20 | 3 | 17, 17, 17 | 17, 18, 17 | 87% | 66–96% | 17/20 | 3.9 | 13.9 | 2032 | 474 | 1.30 |

## Reviewed accuracy per category (correct / questions x runs)

| Category | cai | cai-instant | cai-mini |
|---|---|---|---|
| aggregation | 24/24 | 24/24 | 24/24 |
| temporal | 21/24 | 20/24 | 16/24 |
| filter | 20/24 | 24/24 | 19/24 |
| multi-turn | 24/24 | 24/24 | 24/24 |
| unanswerable | 24/24 | 24/24 | 20/24 |

## Failures after manual review

| Model | Run | Case | Outcome | Type | Note |
|---|---|---|---|---|---|
| cai | 1 | tmp-03 | chart | silent error | timeUnit 'weekday' means week-of-year + day, not day of week: ~365 thin bars instead of 7. Valid Vega-Lite, so validation and self-healing cannot catch it (checked visually in the app). |
| cai | 2 | tmp-03 | chart | silent error | timeUnit 'weekday' means week-of-year + day, not day of week: ~365 thin bars instead of 7. Valid Vega-Lite, so validation and self-healing cannot catch it (checked visually in the app). |
| cai | 3 | tmp-03 | chart | silent error | timeUnit 'weekday' means week-of-year + day, not day of week: ~365 thin bars instead of 7. Valid Vega-Lite, so validation and self-healing cannot catch it (checked visually in the app). |
| cai | 2 | flt-02 | chart | render error | filter written as "bike_type == 'electric'" without 'datum.': passes validation but Vega fails at render time (Unrecognized signal name). Produced by self-healing after a rejected first attempt. |
| cai | 1 | s-flt-03 | failure | system failure | invalid filter in all attempts; the schema error message ('and'/'equal'/'gt' is a required property) does not help the model to fix it, so self-healing fails |
| cai | 2 | s-flt-03 | failure | system failure | invalid filter in all attempts; the schema error message ('and'/'equal'/'gt' is a required property) does not help the model to fix it, so self-healing fails |
| cai | 2 | s-flt-04 | failure | system failure | invalid filter in all 3 attempts (same misleading schema error as s-flt-03) |
| cai-instant | 1 | tmp-03 | chart | silent error | same 'weekday' error as cai |
| cai-instant | 2 | tmp-03 | chart | silent error | same 'weekday' error as cai |
| cai-instant | 3 | tmp-03 | chart | silent error | same 'weekday' error as cai |
| cai-instant | 2 | s-tmp-02 | chart | silent error | monthly revenue split into one line per country (colour = country): the total monthly revenue that was asked is not shown |
| cai-mini | 1 | tmp-03 | chart | silent error | same 'weekday' error; first attempt used invalid 'dayofweek' |
| cai-mini | 2 | tmp-03 | chart | silent error | same 'weekday' error; first attempt used invalid 'dayofweek' |
| cai-mini | 3 | tmp-03 | chart | silent error | same 'weekday' error; first attempt used invalid 'dayofweek' |
| cai-mini | 2 | flt-01 | failure | system failure | tried a map (longitude encoding) for districts without coordinates; 3 invalid attempts, no chart (run 1 gave a correct bar chart) |
| cai-mini | 3 | flt-01 | failure | system failure | tried a map (longitude encoding) for districts without coordinates; 3 invalid attempts, no chart (run 1 gave a correct bar chart) |
| cai-mini | 1 | clr-01 | chart | silent substitution | 'average profit' answered with mean(total) instead of asking for clarification |
| cai-mini | 2 | clr-01 | chart | silent substitution | 'average profit' answered with mean(total) instead of asking for clarification |
| cai-mini | 3 | clr-01 | chart | silent substitution | 'average profit' answered with mean(total) instead of asking for clarification |
| cai-mini | 3 | clr-02 | chart | silent substitution | 'which customer' answered with count per user_type instead of asking for clarification (no customer id) |
| cai-mini | 1 | s-tmp-02 | chart | silent error | timeUnit month instead of yearmonth: 2023 and 2024 merged |
| cai-mini | 2 | s-tmp-02 | chart | silent error | timeUnit month instead of yearmonth: 2023 and 2024 merged |
| cai-mini | 3 | s-tmp-02 | chart | silent error | no timeUnit: one point per order timestamp instead of revenue per month |
| cai-mini | 1 | s-tmp-03 | chart | misleading chart | month computed with calculate month(...), which is 0-based in Vega: November shown as 10, so a reader would answer October |
| cai-mini | 3 | s-tmp-03 | chart | misleading chart | month computed with calculate month(...), which is 0-based in Vega: November shown as 10, so a reader would answer October |
| cai-mini | 1 | s-flt-01 | chart | silent error | 'returned orders' filtered as customer_type = returning (returning customer) instead of status = returned |
| cai-mini | 2 | s-flt-01 | chart | silent error | 'returned orders' filtered as customer_type = returning (returning customer) instead of status = returned |
| cai-mini | 3 | s-flt-01 | chart | silent error | 'returned orders' filtered as customer_type = returning (returning customer) instead of status = returned |

Notes: run k = k-th execution of each question, temperature 0. Mean accuracy = mean over runs; the CI uses n = number of distinct questions, because repeating the same questions does not add new questions. Consistent cases = same outcome and chart meaning in every run. Latency = wall-clock time per question (all turns and retries), over all runs. Tokens = sum over all LLM calls of a question.

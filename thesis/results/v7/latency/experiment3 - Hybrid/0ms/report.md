# Latency Report (hybrid, 0ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 3.7473s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 2.770516 | 0.006600 | no |
| 2 | 2.604583 | 0.172534 | no |
| 3 | 3.185599 | 0.408482 | no |
| 4 | 3.028109 | 0.250993 | no |
| 5 | 2.783717 | 0.006601 | no |
| 6 | 2.714095 | 0.063022 | no |
| 7 | 3.131946 | 0.354830 | no |
| 8 | 2.921828 | 0.144712 | no |
| 9 | 2.699607 | 0.077510 | no |
| 10 | 2.753402 | 0.023715 | no |

## Sorted values (ascending order)

2.604583, 2.699607, 2.714095, 2.753402, 2.770516, 2.783717, 2.921828, 3.028109, 3.131946, 3.185599

## Median and dispersion

- Median: **2.777116s**
- Minimum: 2.604583s
- Maximum: 3.185599s
- Mean: 2.859340s
- Standard deviation (sample): 0.197059s
- Spread (min/max): 22.3074%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 22.3074% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

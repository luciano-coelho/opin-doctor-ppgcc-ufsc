# Latency Report (pqc, 14ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 13.7457s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 13.328915 | 0.546016 | no |
| 2 | 12.537777 | 0.245122 | no |
| 3 | 12.493231 | 0.289668 | no |
| 4 | 12.134393 | 0.648506 | no |
| 5 | 11.843594 | 0.939305 | no |
| 6 | 13.028021 | 0.245122 | no |
| 7 | 13.913525 | 1.130626 | no |
| 8 | 14.426413 | 1.643514 | no |
| 9 | 14.375406 | 1.592507 | no |
| 10 | 12.535008 | 0.247891 | no |

## Sorted values (ascending order)

11.843594, 12.134393, 12.493231, 12.535008, 12.537777, 13.028021, 13.328915, 13.913525, 14.375406, 14.426413

## Median and dispersion

- Median: **12.782899s**
- Minimum: 11.843594s
- Maximum: 14.426413s
- Mean: 13.061628s
- Standard deviation (sample): 0.919248s
- Spread (min/max): 21.8077%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 21.8077% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

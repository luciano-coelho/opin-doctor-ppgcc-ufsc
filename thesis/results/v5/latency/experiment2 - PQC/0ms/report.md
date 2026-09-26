# Latency Report (pqc, 0ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 16.5170s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 10.935299 | 0.803127 | no |
| 2 | 10.127523 | 0.004649 | no |
| 3 | 10.386451 | 0.254279 | no |
| 4 | 10.110513 | 0.021659 | no |
| 5 | 9.713507 | 0.418665 | no |
| 6 | 10.143860 | 0.011688 | no |
| 7 | 10.395026 | 0.262854 | no |
| 8 | 9.961689 | 0.170483 | no |
| 9 | 10.136821 | 0.004649 | no |
| 10 | 9.974408 | 0.157764 | no |

## Sorted values (ascending order)

9.713507, 9.961689, 9.974408, 10.110513, 10.127523, 10.136821, 10.143860, 10.386451, 10.395026, 10.935299

## Median and dispersion

- Median: **10.132172s**
- Minimum: 9.713507s
- Maximum: 10.935299s
- Mean: 10.188510s
- Standard deviation (sample): 0.329462s
- Spread (min/max): 12.5783%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 12.5783% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

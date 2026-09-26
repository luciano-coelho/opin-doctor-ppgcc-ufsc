# Latency Report (hybrid, 225ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 46.2357s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 45.552280 | 0.073099 | no |
| 2 | 45.365219 | 0.113962 | no |
| 3 | 45.406083 | 0.073099 | no |
| 4 | 45.313474 | 0.165708 | no |
| 5 | 45.035595 | 0.443587 | no |
| 6 | 45.360019 | 0.119163 | no |
| 7 | 46.096890 | 0.617708 | no |
| 8 | 49.284000 | 3.804818 | no |
| 9 | 49.554121 | 4.074939 | no |
| 10 | 46.389141 | 0.909959 | no |

## Sorted values (ascending order)

45.035595, 45.313474, 45.360019, 45.365219, 45.406083, 45.552280, 46.096890, 46.389141, 49.284000, 49.554121

## Median and dispersion

- Median: **45.479182s**
- Minimum: 45.035595s
- Maximum: 49.554121s
- Mean: 46.335682s
- Standard deviation (sample): 1.673902s
- Spread (min/max): 10.0332%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 10.0332% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

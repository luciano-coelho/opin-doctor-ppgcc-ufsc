# Latency Report (hybrid, 225ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 51.5046s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 47.351363 | 0.003925 | no |
| 2 | 47.343514 | 0.003924 | no |
| 3 | 47.189498 | 0.157940 | no |
| 4 | 47.277263 | 0.070175 | no |
| 5 | 47.258175 | 0.089263 | no |
| 6 | 47.565514 | 0.218076 | no |
| 7 | 47.222602 | 0.124836 | no |
| 8 | 49.467852 | 2.120414 | no |
| 9 | 52.148634 | 4.801196 | no |
| 10 | 48.820351 | 1.472913 | no |

## Sorted values (ascending order)

47.189498, 47.222602, 47.258175, 47.277263, 47.343514, 47.351363, 47.565514, 48.820351, 49.467852, 52.148634

## Median and dispersion

- Median: **47.347438s**
- Minimum: 47.189498s
- Maximum: 52.148634s
- Mean: 48.164477s
- Standard deviation (sample): 1.603559s
- Spread (min/max): 10.5090%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 10.5090% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

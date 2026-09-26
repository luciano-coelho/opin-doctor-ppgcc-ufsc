# Latency Report (pqc, 225ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 46.4858s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 45.973481 | 0.098663 | no |
| 2 | 45.778616 | 0.096202 | no |
| 3 | 46.046172 | 0.171354 | no |
| 4 | 45.816040 | 0.058778 | no |
| 5 | 45.919914 | 0.045096 | no |
| 6 | 45.800727 | 0.074091 | no |
| 7 | 45.891021 | 0.016203 | no |
| 8 | 46.240289 | 0.365471 | no |
| 9 | 45.730924 | 0.143894 | no |
| 10 | 45.858614 | 0.016204 | no |

## Sorted values (ascending order)

45.730924, 45.778616, 45.800727, 45.816040, 45.858614, 45.891021, 45.919914, 45.973481, 46.046172, 46.240289

## Median and dispersion

- Median: **45.874818s**
- Minimum: 45.730924s
- Maximum: 46.240289s
- Mean: 45.905580s
- Standard deviation (sample): 0.150800s
- Spread (min/max): 1.1138%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 1.1138% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

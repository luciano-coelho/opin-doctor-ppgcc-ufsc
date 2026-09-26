# Latency Report (pqc, 140ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 30.3695s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 30.061058 | 0.158301 | no |
| 2 | 29.824581 | 0.078176 | no |
| 3 | 29.904789 | 0.002032 | no |
| 4 | 29.523906 | 0.378851 | no |
| 5 | 31.518051 | 1.615294 | no |
| 6 | 29.740484 | 0.162273 | no |
| 7 | 29.769108 | 0.133649 | no |
| 8 | 29.900724 | 0.002033 | no |
| 9 | 29.907957 | 0.005200 | no |
| 10 | 29.913123 | 0.010366 | no |

## Sorted values (ascending order)

29.523906, 29.740484, 29.769108, 29.824581, 29.900724, 29.904789, 29.907957, 29.913123, 30.061058, 31.518051

## Median and dispersion

- Median: **29.902757s**
- Minimum: 29.523906s
- Maximum: 31.518051s
- Mean: 30.006378s
- Standard deviation (sample): 0.549832s
- Spread (min/max): 6.7543%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 6.7543% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

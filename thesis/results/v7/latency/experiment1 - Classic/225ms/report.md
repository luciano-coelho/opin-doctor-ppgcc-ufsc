# Latency Report (classic, 225ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 39.0923s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 38.368775 | 0.113003 | no |
| 2 | 38.481430 | 0.000348 | no |
| 3 | 38.485698 | 0.003920 | no |
| 4 | 38.455619 | 0.026159 | no |
| 5 | 38.440863 | 0.040915 | no |
| 6 | 38.414288 | 0.067490 | no |
| 7 | 38.482126 | 0.000348 | no |
| 8 | 38.490076 | 0.008298 | no |
| 9 | 38.512521 | 0.030743 | no |
| 10 | 38.542924 | 0.061146 | no |

## Sorted values (ascending order)

38.368775, 38.414288, 38.440863, 38.455619, 38.481430, 38.482126, 38.485698, 38.490076, 38.512521, 38.542924

## Median and dispersion

- Median: **38.481778s**
- Minimum: 38.368775s
- Maximum: 38.542924s
- Mean: 38.467432s
- Standard deviation (sample): 0.049881s
- Spread (min/max): 0.4539%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.4539% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

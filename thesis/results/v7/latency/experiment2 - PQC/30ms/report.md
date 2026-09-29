# Latency Report (pqc, 30ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 7.8528s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 6.992727 | 0.854620 | no |
| 2 | 7.872168 | 0.024821 | no |
| 3 | 7.869257 | 0.021910 | no |
| 4 | 7.846379 | 0.000968 | no |
| 5 | 8.169857 | 0.322510 | no |
| 6 | 7.848315 | 0.000968 | no |
| 7 | 7.871707 | 0.024360 | no |
| 8 | 7.496053 | 0.351294 | no |
| 9 | 6.930504 | 0.916843 | no |
| 10 | 7.790140 | 0.057207 | no |

## Sorted values (ascending order)

6.930504, 6.992727, 7.496053, 7.790140, 7.846379, 7.848315, 7.869257, 7.871707, 7.872168, 8.169857

## Median and dispersion

- Median: **7.847347s**
- Minimum: 6.930504s
- Maximum: 8.169857s
- Mean: 7.668711s
- Standard deviation (sample): 0.406100s
- Spread (min/max): 17.8826%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 17.8826% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

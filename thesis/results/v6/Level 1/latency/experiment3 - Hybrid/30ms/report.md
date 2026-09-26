# Latency Report (hybrid, 30ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 15.1968s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 14.434301 | 0.374535 | no |
| 2 | 15.205234 | 0.396399 | no |
| 3 | 14.041250 | 0.767586 | no |
| 4 | 15.328211 | 0.519375 | no |
| 5 | 14.570958 | 0.237878 | no |
| 6 | 15.046713 | 0.237877 | no |
| 7 | 14.509196 | 0.299640 | no |
| 8 | 13.998518 | 0.810318 | no |
| 9 | 15.673382 | 0.864546 | no |
| 10 | 15.244746 | 0.435910 | no |

## Sorted values (ascending order)

13.998518, 14.041250, 14.434301, 14.509196, 14.570958, 15.046713, 15.205234, 15.244746, 15.328211, 15.673382

## Median and dispersion

- Median: **14.808836s**
- Minimum: 13.998518s
- Maximum: 15.673382s
- Mean: 14.805251s
- Standard deviation (sample): 0.572834s
- Spread (min/max): 11.9646%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 11.9646% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

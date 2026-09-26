# Latency Report (hybrid, 0ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 15.1069s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 10.980175 | 0.250725 | no |
| 2 | 10.722479 | 0.006971 | no |
| 3 | 10.936096 | 0.206646 | no |
| 4 | 10.736420 | 0.006970 | no |
| 5 | 10.468293 | 0.261157 | no |
| 6 | 10.678557 | 0.050893 | no |
| 7 | 10.696530 | 0.032920 | no |
| 8 | 10.971033 | 0.241583 | no |
| 9 | 10.918060 | 0.188610 | no |
| 10 | 10.656708 | 0.072742 | no |

## Sorted values (ascending order)

10.468293, 10.656708, 10.678557, 10.696530, 10.722479, 10.736420, 10.918060, 10.936096, 10.971033, 10.980175

## Median and dispersion

- Median: **10.729450s**
- Minimum: 10.468293s
- Maximum: 10.980175s
- Mean: 10.776435s
- Standard deviation (sample): 0.168223s
- Spread (min/max): 4.8898%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 4.8898% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

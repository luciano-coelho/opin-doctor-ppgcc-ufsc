# Latency Report (hybrid, 225ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 44.8019s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 45.039851 | 0.016925 | no |
| 2 | 44.967859 | 0.088917 | no |
| 3 | 44.967162 | 0.089613 | no |
| 4 | 44.998000 | 0.058776 | no |
| 5 | 44.964536 | 0.092239 | no |
| 6 | 45.073700 | 0.016925 | no |
| 7 | 45.395755 | 0.338980 | no |
| 8 | 45.361710 | 0.304935 | no |
| 9 | 45.099171 | 0.042395 | no |
| 10 | 45.129964 | 0.073189 | no |

## Sorted values (ascending order)

44.964536, 44.967162, 44.967859, 44.998000, 45.039851, 45.073700, 45.099171, 45.129964, 45.361710, 45.395755

## Median and dispersion

- Median: **45.056776s**
- Minimum: 44.964536s
- Maximum: 45.395755s
- Mean: 45.099771s
- Standard deviation (sample): 0.158125s
- Spread (min/max): 0.9590%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.9590% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

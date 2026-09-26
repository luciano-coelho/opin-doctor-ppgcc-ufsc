# Latency Report (pqc, 320ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 59.1872s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 60.098389 | 1.311833 | no |
| 2 | 58.842878 | 0.056322 | no |
| 3 | 58.529362 | 0.257194 | no |
| 4 | 58.836522 | 0.049966 | no |
| 5 | 64.420355 | 5.633799 | no |
| 6 | 58.736589 | 0.049967 | no |
| 7 | 58.526830 | 0.259726 | no |
| 8 | 59.220688 | 0.434132 | no |
| 9 | 58.465956 | 0.320600 | no |
| 10 | 58.631649 | 0.154907 | no |

## Sorted values (ascending order)

58.465956, 58.526830, 58.529362, 58.631649, 58.736589, 58.836522, 58.842878, 59.220688, 60.098389, 64.420355

## Median and dispersion

- Median: **58.786556s**
- Minimum: 58.465956s
- Maximum: 64.420355s
- Mean: 59.430922s
- Standard deviation (sample): 1.818594s
- Spread (min/max): 10.1844%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 10.1844% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

# Latency Report (hybrid, 320ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 61.9064s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 62.011363 | 0.823082 | no |
| 2 | 60.868295 | 0.319986 | no |
| 3 | 61.489656 | 0.301375 | no |
| 4 | 61.569276 | 0.380995 | no |
| 5 | 61.038510 | 0.149771 | no |
| 6 | 62.161157 | 0.972876 | no |
| 7 | 60.569355 | 0.618926 | no |
| 8 | 60.912342 | 0.275939 | no |
| 9 | 61.338052 | 0.149771 | no |
| 10 | 60.791588 | 0.396693 | no |

## Sorted values (ascending order)

60.569355, 60.791588, 60.868295, 60.912342, 61.038510, 61.338052, 61.489656, 61.569276, 62.011363, 62.161157

## Median and dispersion

- Median: **61.188281s**
- Minimum: 60.569355s
- Maximum: 62.161157s
- Mean: 61.274959s
- Standard deviation (sample): 0.532148s
- Spread (min/max): 2.6281%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 2.6281% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

# Latency Report (hybrid, 30ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 8.6471s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 8.196751 | 0.159844 | no |
| 2 | 8.565925 | 0.209330 | no |
| 3 | 8.338416 | 0.018179 | no |
| 4 | 8.379613 | 0.023018 | no |
| 5 | 8.333809 | 0.022786 | no |
| 6 | 8.317195 | 0.039400 | no |
| 7 | 8.374774 | 0.018179 | no |
| 8 | 8.382831 | 0.026236 | no |
| 9 | 8.419971 | 0.063376 | no |
| 10 | 8.225445 | 0.131150 | no |

## Sorted values (ascending order)

8.196751, 8.225445, 8.317195, 8.333809, 8.338416, 8.374774, 8.379613, 8.382831, 8.419971, 8.565925

## Median and dispersion

- Median: **8.356595s**
- Minimum: 8.196751s
- Maximum: 8.565925s
- Mean: 8.353473s
- Standard deviation (sample): 0.102437s
- Spread (min/max): 4.5039%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 4.5039% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

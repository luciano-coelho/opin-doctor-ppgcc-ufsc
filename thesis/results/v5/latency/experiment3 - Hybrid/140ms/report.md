# Latency Report (hybrid, 140ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 33.1556s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 32.269760 | 0.596917 | no |
| 2 | 32.251235 | 0.615442 | no |
| 3 | 32.864202 | 0.002475 | no |
| 4 | 36.274152 | 3.407475 | no |
| 5 | 32.869153 | 0.002476 | no |
| 6 | 32.885283 | 0.018606 | no |
| 7 | 34.807035 | 1.940358 | no |
| 8 | 36.244664 | 3.377987 | no |
| 9 | 32.296335 | 0.570342 | no |
| 10 | 32.721739 | 0.144938 | no |

## Sorted values (ascending order)

32.251235, 32.269760, 32.296335, 32.721739, 32.864202, 32.869153, 32.885283, 34.807035, 36.244664, 36.274152

## Median and dispersion

- Median: **32.866677s**
- Minimum: 32.251235s
- Maximum: 36.274152s
- Mean: 33.548356s
- Standard deviation (sample): 1.606291s
- Spread (min/max): 12.4737%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 12.4737% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

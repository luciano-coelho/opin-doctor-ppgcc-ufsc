# Latency Report (pqc, 320ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 64.3243s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 59.703856 | 0.738661 | no |
| 2 | 58.727058 | 0.238137 | no |
| 3 | 58.688897 | 0.276298 | no |
| 4 | 58.690353 | 0.274842 | no |
| 5 | 58.938425 | 0.026770 | no |
| 6 | 58.359166 | 0.606029 | no |
| 7 | 59.416828 | 0.451633 | no |
| 8 | 59.002898 | 0.037703 | no |
| 9 | 58.991964 | 0.026770 | no |
| 10 | 59.010884 | 0.045689 | no |

## Sorted values (ascending order)

58.359166, 58.688897, 58.690353, 58.727058, 58.938425, 58.991964, 59.002898, 59.010884, 59.416828, 59.703856

## Median and dispersion

- Median: **58.965195s**
- Minimum: 58.359166s
- Maximum: 59.703856s
- Mean: 58.953033s
- Standard deviation (sample): 0.384262s
- Spread (min/max): 2.3042%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 2.3042% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

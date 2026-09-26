# Latency Report (pqc, 320ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 59.8349s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 60.396500 | 0.827283 | no |
| 2 | 59.207754 | 0.361463 | no |
| 3 | 59.941350 | 0.372132 | no |
| 4 | 61.389651 | 1.820434 | no |
| 5 | 59.113488 | 0.455730 | no |
| 6 | 59.518081 | 0.051136 | no |
| 7 | 59.450429 | 0.118789 | no |
| 8 | 59.620354 | 0.051136 | no |
| 9 | 60.014310 | 0.445093 | no |
| 10 | 59.368776 | 0.200442 | no |

## Sorted values (ascending order)

59.113488, 59.207754, 59.368776, 59.450429, 59.518081, 59.620354, 59.941350, 60.014310, 60.396500, 61.389651

## Median and dispersion

- Median: **59.569218s**
- Minimum: 59.113488s
- Maximum: 61.389651s
- Mean: 59.802069s
- Standard deviation (sample): 0.682367s
- Spread (min/max): 3.8505%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 3.8505% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

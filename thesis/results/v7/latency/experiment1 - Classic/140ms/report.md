# Latency Report (classic, 140ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 28.1786s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 27.842716 | 0.014057 | no |
| 2 | 27.937947 | 0.081174 | no |
| 3 | 27.837794 | 0.018979 | no |
| 4 | 27.863906 | 0.007133 | no |
| 5 | 27.885093 | 0.028320 | no |
| 6 | 27.846599 | 0.010174 | no |
| 7 | 27.901169 | 0.044396 | no |
| 8 | 27.825238 | 0.031535 | no |
| 9 | 27.951504 | 0.094731 | no |
| 10 | 27.849640 | 0.007133 | no |

## Sorted values (ascending order)

27.825238, 27.837794, 27.842716, 27.846599, 27.849640, 27.863906, 27.885093, 27.901169, 27.937947, 27.951504

## Median and dispersion

- Median: **27.856773s**
- Minimum: 27.825238s
- Maximum: 27.951504s
- Mean: 27.874161s
- Standard deviation (sample): 0.043551s
- Spread (min/max): 0.4538%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.4538% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

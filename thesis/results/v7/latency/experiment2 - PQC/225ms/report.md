# Latency Report (pqc, 225ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 44.3032s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 43.727294 | 0.027659 | no |
| 2 | 44.074279 | 0.374643 | no |
| 3 | 43.769727 | 0.070092 | no |
| 4 | 43.948567 | 0.248931 | no |
| 5 | 43.604327 | 0.095309 | no |
| 6 | 43.644481 | 0.055155 | no |
| 7 | 43.671977 | 0.027659 | no |
| 8 | 43.611535 | 0.088100 | no |
| 9 | 43.513231 | 0.186405 | no |
| 10 | 44.071109 | 0.371474 | no |

## Sorted values (ascending order)

43.513231, 43.604327, 43.611535, 43.644481, 43.671977, 43.727294, 43.769727, 43.948567, 44.071109, 44.074279

## Median and dispersion

- Median: **43.699635s**
- Minimum: 43.513231s
- Maximum: 44.074279s
- Mean: 43.763653s
- Standard deviation (sample): 0.200114s
- Spread (min/max): 1.2894%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 1.2894% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

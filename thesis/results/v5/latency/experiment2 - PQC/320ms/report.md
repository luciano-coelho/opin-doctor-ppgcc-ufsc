# Latency Report (pqc, 320ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 62.9989s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 62.535255 | 0.144807 | no |
| 2 | 62.419683 | 0.029235 | no |
| 3 | 62.477588 | 0.087140 | no |
| 4 | 62.361213 | 0.029235 | no |
| 5 | 62.345407 | 0.045041 | no |
| 6 | 62.340700 | 0.049748 | no |
| 7 | 62.682853 | 0.292405 | no |
| 8 | 62.305608 | 0.084840 | no |
| 9 | 62.567246 | 0.176798 | no |
| 10 | 62.284609 | 0.105839 | no |

## Sorted values (ascending order)

62.284609, 62.305608, 62.340700, 62.345407, 62.361213, 62.419683, 62.477588, 62.535255, 62.567246, 62.682853

## Median and dispersion

- Median: **62.390448s**
- Minimum: 62.284609s
- Maximum: 62.682853s
- Mean: 62.432016s
- Standard deviation (sample): 0.130237s
- Spread (min/max): 0.6394%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.6394% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

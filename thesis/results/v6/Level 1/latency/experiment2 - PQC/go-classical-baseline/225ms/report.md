# Latency Report (pqc, 225ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 45.3603s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 43.848750 | 0.032236 | no |
| 2 | 43.650608 | 0.165906 | no |
| 3 | 43.476822 | 0.339692 | no |
| 4 | 43.784279 | 0.032235 | no |
| 5 | 43.235018 | 0.581497 | no |
| 6 | 43.652011 | 0.164503 | no |
| 7 | 44.510367 | 0.693853 | no |
| 8 | 44.919201 | 1.102687 | no |
| 9 | 47.124096 | 3.307582 | no |
| 10 | 45.951175 | 2.134661 | no |

## Sorted values (ascending order)

43.235018, 43.476822, 43.650608, 43.652011, 43.784279, 43.848750, 44.510367, 44.919201, 45.951175, 47.124096

## Median and dispersion

- Median: **43.816514s**
- Minimum: 43.235018s
- Maximum: 47.124096s
- Mean: 44.415233s
- Standard deviation (sample): 1.252543s
- Spread (min/max): 8.9952%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 8.9952% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

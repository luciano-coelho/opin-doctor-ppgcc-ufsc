# Latency Report (hybrid, 30ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 15.4629s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 14.690800 | 0.023290 | no |
| 2 | 14.280953 | 0.386557 | no |
| 3 | 14.246373 | 0.421137 | no |
| 4 | 14.285542 | 0.381968 | no |
| 5 | 14.415667 | 0.251843 | no |
| 6 | 14.778529 | 0.111019 | no |
| 7 | 15.023455 | 0.355945 | no |
| 8 | 16.145301 | 1.477791 | no |
| 9 | 15.174500 | 0.506990 | no |
| 10 | 14.644221 | 0.023289 | no |

## Sorted values (ascending order)

14.246373, 14.280953, 14.285542, 14.415667, 14.644221, 14.690800, 14.778529, 15.023455, 15.174500, 16.145301

## Median and dispersion

- Median: **14.667510s**
- Minimum: 14.246373s
- Maximum: 16.145301s
- Mean: 14.768534s
- Standard deviation (sample): 0.578798s
- Spread (min/max): 13.3292%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 13.3292% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

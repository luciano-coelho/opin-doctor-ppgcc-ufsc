# Latency Report (hybrid, 320ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 62.0933s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 61.081127 | 0.356440 | no |
| 2 | 61.170159 | 0.267408 | no |
| 3 | 61.932612 | 0.495045 | no |
| 4 | 60.950068 | 0.487499 | no |
| 5 | 61.153109 | 0.284458 | no |
| 6 | 63.469621 | 2.032054 | no |
| 7 | 63.130752 | 1.693185 | no |
| 8 | 61.490605 | 0.053038 | no |
| 9 | 61.500332 | 0.062765 | no |
| 10 | 61.384528 | 0.053038 | no |

## Sorted values (ascending order)

60.950068, 61.081127, 61.153109, 61.170159, 61.384528, 61.490605, 61.500332, 61.932612, 63.130752, 63.469621

## Median and dispersion

- Median: **61.437567s**
- Minimum: 60.950068s
- Maximum: 63.469621s
- Mean: 61.726291s
- Standard deviation (sample): 0.877766s
- Spread (min/max): 4.1338%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 4.1338% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

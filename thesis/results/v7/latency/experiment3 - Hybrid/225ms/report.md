# Latency Report (hybrid, 225ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 47.1611s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 46.560879 | 0.144269 | no |
| 2 | 46.771201 | 0.354591 | no |
| 3 | 47.877645 | 1.461035 | no |
| 4 | 46.128636 | 0.287974 | no |
| 5 | 46.297667 | 0.118944 | no |
| 6 | 45.769027 | 0.647583 | no |
| 7 | 45.982958 | 0.433652 | no |
| 8 | 46.535554 | 0.118944 | no |
| 9 | 47.278607 | 0.861997 | no |
| 10 | 45.476259 | 0.940351 | no |

## Sorted values (ascending order)

45.476259, 45.769027, 45.982958, 46.128636, 46.297667, 46.535554, 46.560879, 46.771201, 47.278607, 47.877645

## Median and dispersion

- Median: **46.416610s**
- Minimum: 45.476259s
- Maximum: 47.877645s
- Mean: 46.467843s
- Standard deviation (sample): 0.714987s
- Spread (min/max): 5.2805%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 5.2805% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

# Latency Report (pqc, 0ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 9.7625s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 10.271528 | 0.463798 | no |
| 2 | 9.730513 | 0.077217 | no |
| 3 | 9.315238 | 0.492492 | no |
| 4 | 10.035237 | 0.227507 | no |
| 5 | 9.239603 | 0.568127 | no |
| 6 | 9.526071 | 0.281659 | no |
| 7 | 9.317095 | 0.490635 | no |
| 8 | 10.280991 | 0.473261 | no |
| 9 | 10.114127 | 0.306397 | no |
| 10 | 9.884947 | 0.077217 | no |

## Sorted values (ascending order)

9.239603, 9.315238, 9.317095, 9.526071, 9.730513, 9.884947, 10.035237, 10.114127, 10.271528, 10.280991

## Median and dispersion

- Median: **9.807730s**
- Minimum: 9.239603s
- Maximum: 10.280991s
- Mean: 9.771535s
- Standard deviation (sample): 0.403996s
- Spread (min/max): 11.2709%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 11.2709% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

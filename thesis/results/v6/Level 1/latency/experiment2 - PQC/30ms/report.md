# Latency Report (pqc, 30ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 13.7311s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 13.221073 | 0.037406 | no |
| 2 | 13.038356 | 0.220123 | no |
| 3 | 13.288884 | 0.030405 | no |
| 4 | 13.408170 | 0.149691 | no |
| 5 | 13.982100 | 0.723621 | no |
| 6 | 13.480138 | 0.221659 | no |
| 7 | 13.056604 | 0.201875 | no |
| 8 | 13.406305 | 0.147826 | no |
| 9 | 12.899200 | 0.359279 | no |
| 10 | 13.228074 | 0.030405 | no |

## Sorted values (ascending order)

12.899200, 13.038356, 13.056604, 13.221073, 13.228074, 13.288884, 13.406305, 13.408170, 13.480138, 13.982100

## Median and dispersion

- Median: **13.258479s**
- Minimum: 12.899200s
- Maximum: 13.982100s
- Mean: 13.300890s
- Standard deviation (sample): 0.301951s
- Spread (min/max): 8.3951%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 8.3951% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

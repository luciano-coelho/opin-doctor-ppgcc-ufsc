# Latency Report (pqc, 30ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 13.1593s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 13.502732 | 0.231002 | no |
| 2 | 13.205336 | 0.066394 | no |
| 3 | 12.996413 | 0.275317 | no |
| 4 | 12.804465 | 0.467265 | no |
| 5 | 12.818388 | 0.453342 | no |
| 6 | 13.338124 | 0.066394 | no |
| 7 | 14.129283 | 0.857553 | no |
| 8 | 13.202510 | 0.069220 | no |
| 9 | 13.338709 | 0.066979 | no |
| 10 | 13.722975 | 0.451245 | no |

## Sorted values (ascending order)

12.804465, 12.818388, 12.996413, 13.202510, 13.205336, 13.338124, 13.338709, 13.502732, 13.722975, 14.129283

## Median and dispersion

- Median: **13.271730s**
- Minimum: 12.804465s
- Maximum: 14.129283s
- Mean: 13.305893s
- Standard deviation (sample): 0.408038s
- Spread (min/max): 10.3465%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 10.3465% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

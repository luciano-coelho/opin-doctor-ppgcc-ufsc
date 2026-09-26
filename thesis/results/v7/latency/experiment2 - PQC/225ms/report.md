# Latency Report (pqc, 225ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 44.0002s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 43.683387 | 0.644182 | no |
| 2 | 44.401500 | 0.073931 | no |
| 3 | 43.341162 | 0.986407 | no |
| 4 | 43.641516 | 0.686053 | no |
| 5 | 44.100072 | 0.227497 | no |
| 6 | 44.253639 | 0.073930 | no |
| 7 | 44.834493 | 0.506924 | no |
| 8 | 44.469912 | 0.142343 | no |
| 9 | 44.909329 | 0.581760 | no |
| 10 | 46.098282 | 1.770713 | no |

## Sorted values (ascending order)

43.341162, 43.641516, 43.683387, 44.100072, 44.253639, 44.401500, 44.469912, 44.834493, 44.909329, 46.098282

## Median and dispersion

- Median: **44.327569s**
- Minimum: 43.341162s
- Maximum: 46.098282s
- Mean: 44.373329s
- Standard deviation (sample): 0.792429s
- Spread (min/max): 6.3614%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 6.3614% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

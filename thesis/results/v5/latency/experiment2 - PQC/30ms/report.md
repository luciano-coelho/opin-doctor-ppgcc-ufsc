# Latency Report (pqc, 30ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 14.4751s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 14.270914 | 0.540954 | no |
| 2 | 13.723415 | 0.006545 | no |
| 3 | 13.736504 | 0.006545 | no |
| 4 | 13.587146 | 0.142813 | no |
| 5 | 13.617349 | 0.112610 | no |
| 6 | 13.516274 | 0.213686 | no |
| 7 | 14.034385 | 0.304426 | no |
| 8 | 13.584763 | 0.145196 | no |
| 9 | 13.831957 | 0.101997 | no |
| 10 | 14.582710 | 0.852751 | no |

## Sorted values (ascending order)

13.516274, 13.584763, 13.587146, 13.617349, 13.723415, 13.736504, 13.831957, 14.034385, 14.270914, 14.582710

## Median and dispersion

- Median: **13.729959s**
- Minimum: 13.516274s
- Maximum: 14.582710s
- Mean: 13.848542s
- Standard deviation (sample): 0.346760s
- Spread (min/max): 7.8900%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 7.8900% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

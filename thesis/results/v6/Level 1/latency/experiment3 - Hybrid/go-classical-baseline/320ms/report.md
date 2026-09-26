# Latency Report (hybrid, 320ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 60.7309s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 60.697887 | 0.389649 | no |
| 2 | 61.322387 | 0.234851 | no |
| 3 | 61.612968 | 0.525432 | no |
| 4 | 62.116290 | 1.028754 | no |
| 5 | 60.747807 | 0.339729 | no |
| 6 | 61.071418 | 0.016118 | no |
| 7 | 61.173747 | 0.086211 | no |
| 8 | 60.811268 | 0.276268 | no |
| 9 | 60.859840 | 0.227696 | no |
| 10 | 61.103654 | 0.016118 | no |

## Sorted values (ascending order)

60.697887, 60.747807, 60.811268, 60.859840, 61.071418, 61.103654, 61.173747, 61.322387, 61.612968, 62.116290

## Median and dispersion

- Median: **61.087536s**
- Minimum: 60.697887s
- Maximum: 62.116290s
- Mean: 61.151727s
- Standard deviation (sample): 0.441176s
- Spread (min/max): 2.3368%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 2.3368% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

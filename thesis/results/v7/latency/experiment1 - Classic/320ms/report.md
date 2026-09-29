# Latency Report (classic, 320ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 60.6330s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 60.685124 | 0.167612 | no |
| 2 | 62.827662 | 1.974926 | no |
| 3 | 61.582142 | 0.729406 | no |
| 4 | 61.453030 | 0.600294 | no |
| 5 | 60.592925 | 0.259811 | no |
| 6 | 60.538762 | 0.313974 | no |
| 7 | 60.684262 | 0.168474 | no |
| 8 | 60.874067 | 0.021331 | no |
| 9 | 61.393701 | 0.540965 | no |
| 10 | 60.831405 | 0.021331 | no |

## Sorted values (ascending order)

60.538762, 60.592925, 60.684262, 60.685124, 60.831405, 60.874067, 61.393701, 61.453030, 61.582142, 62.827662

## Median and dispersion

- Median: **60.852736s**
- Minimum: 60.538762s
- Maximum: 62.827662s
- Mean: 61.146308s
- Standard deviation (sample): 0.702929s
- Spread (min/max): 3.7809%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 3.7809% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

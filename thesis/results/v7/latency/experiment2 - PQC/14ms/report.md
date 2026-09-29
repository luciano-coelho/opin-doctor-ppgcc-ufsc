# Latency Report (pqc, 14ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 5.0865s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 5.197813 | 0.291399 | no |
| 2 | 5.214526 | 0.308112 | no |
| 3 | 4.611467 | 0.294947 | no |
| 4 | 4.877806 | 0.028608 | no |
| 5 | 4.908841 | 0.002427 | no |
| 6 | 4.977591 | 0.071177 | no |
| 7 | 4.967611 | 0.061197 | no |
| 8 | 4.517252 | 0.389162 | no |
| 9 | 4.704778 | 0.201636 | no |
| 10 | 4.903987 | 0.002427 | no |

## Sorted values (ascending order)

4.517252, 4.611467, 4.704778, 4.877806, 4.903987, 4.908841, 4.967611, 4.977591, 5.197813, 5.214526

## Median and dispersion

- Median: **4.906414s**
- Minimum: 4.517252s
- Maximum: 5.214526s
- Mean: 4.888167s
- Standard deviation (sample): 0.227366s
- Spread (min/max): 15.4358%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 15.4358% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

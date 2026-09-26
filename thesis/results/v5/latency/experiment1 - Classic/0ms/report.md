# Latency Report (classic, 0ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 3.9466s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 4.216863 | 0.398281 | no |
| 2 | 3.612926 | 0.205656 | no |
| 3 | 3.872877 | 0.054295 | no |
| 4 | 4.393070 | 0.574488 | no |
| 5 | 3.395827 | 0.422755 | no |
| 6 | 3.249405 | 0.569177 | no |
| 7 | 3.748383 | 0.070199 | no |
| 8 | 4.086336 | 0.267754 | no |
| 9 | 3.764288 | 0.054294 | no |
| 10 | 4.117052 | 0.298470 | no |

## Sorted values (ascending order)

3.249405, 3.395827, 3.612926, 3.748383, 3.764288, 3.872877, 4.086336, 4.117052, 4.216863, 4.393070

## Median and dispersion

- Median: **3.818582s**
- Minimum: 3.249405s
- Maximum: 4.393070s
- Mean: 3.845703s
- Standard deviation (sample): 0.364827s
- Spread (min/max): 35.1961%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 35.1961% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

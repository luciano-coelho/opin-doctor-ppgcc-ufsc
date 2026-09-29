# Latency Report (classic, 0ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 2.9998s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 3.091451 | 0.477471 | no |
| 2 | 2.618178 | 0.004198 | no |
| 3 | 2.683848 | 0.069868 | no |
| 4 | 2.770435 | 0.156455 | no |
| 5 | 2.551536 | 0.062444 | no |
| 6 | 2.601801 | 0.012179 | no |
| 7 | 2.786717 | 0.172737 | no |
| 8 | 2.609782 | 0.004198 | no |
| 9 | 2.541326 | 0.072654 | no |
| 10 | 2.454286 | 0.159694 | no |

## Sorted values (ascending order)

2.454286, 2.541326, 2.551536, 2.601801, 2.609782, 2.618178, 2.683848, 2.770435, 2.786717, 3.091451

## Median and dispersion

- Median: **2.613980s**
- Minimum: 2.454286s
- Maximum: 3.091451s
- Mean: 2.670936s
- Standard deviation (sample): 0.179382s
- Spread (min/max): 25.9613%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 25.9613% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

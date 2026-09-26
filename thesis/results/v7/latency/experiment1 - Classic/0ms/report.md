# Latency Report (classic, 0ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 2.8810s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 3.236346 | 0.345087 | no |
| 2 | 2.928489 | 0.037230 | no |
| 3 | 3.034042 | 0.142783 | no |
| 4 | 2.647786 | 0.243473 | no |
| 5 | 2.848475 | 0.042784 | no |
| 6 | 2.854028 | 0.037231 | no |
| 7 | 2.573236 | 0.318023 | no |
| 8 | 3.112332 | 0.221073 | no |
| 9 | 3.119234 | 0.227975 | no |
| 10 | 2.677057 | 0.214202 | no |

## Sorted values (ascending order)

2.573236, 2.647786, 2.677057, 2.848475, 2.854028, 2.928489, 3.034042, 3.112332, 3.119234, 3.236346

## Median and dispersion

- Median: **2.891259s**
- Minimum: 2.573236s
- Maximum: 3.236346s
- Mean: 2.903103s
- Standard deviation (sample): 0.223562s
- Spread (min/max): 25.7695%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 25.7695% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

# Latency Report (hybrid, 14ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 12.7209s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 13.263860 | 0.973583 | no |
| 2 | 13.240046 | 0.997397 | no |
| 3 | 12.868676 | 1.368766 | no |
| 4 | 14.337731 | 0.100288 | no |
| 5 | 15.305140 | 1.067697 | no |
| 6 | 16.470893 | 2.233451 | no |
| 7 | 11.843072 | 2.394371 | no |
| 8 | 14.137154 | 0.100288 | no |
| 9 | 15.605321 | 1.367878 | no |
| 10 | 17.914788 | 3.677346 | no |

## Sorted values (ascending order)

11.843072, 12.868676, 13.240046, 13.263860, 14.137154, 14.337731, 15.305140, 15.605321, 16.470893, 17.914788

## Median and dispersion

- Median: **14.237443s**
- Minimum: 11.843072s
- Maximum: 17.914788s
- Mean: 14.498668s
- Standard deviation (sample): 1.838150s
- Spread (min/max): 51.2681%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 51.2681% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

# Latency Report (pqc, 0ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 9.9305s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 9.534794 | 0.051601 | no |
| 2 | 11.134470 | 1.548075 | no |
| 3 | 10.133467 | 0.547072 | no |
| 4 | 9.737889 | 0.151494 | no |
| 5 | 9.847844 | 0.261449 | no |
| 6 | 9.576845 | 0.009550 | no |
| 7 | 9.503090 | 0.083305 | no |
| 8 | 9.595944 | 0.009549 | no |
| 9 | 9.541022 | 0.045373 | no |
| 10 | 8.920976 | 0.665419 | no |

## Sorted values (ascending order)

8.920976, 9.503090, 9.534794, 9.541022, 9.576845, 9.595944, 9.737889, 9.847844, 10.133467, 11.134470

## Median and dispersion

- Median: **9.586395s**
- Minimum: 8.920976s
- Maximum: 11.134470s
- Mean: 9.752634s
- Standard deviation (sample): 0.574011s
- Spread (min/max): 24.8122%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 24.8122% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

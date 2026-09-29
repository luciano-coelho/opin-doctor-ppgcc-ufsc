# Latency Report (pqc, 0ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 2.8938s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 2.455906 | 0.054483 | no |
| 2 | 2.564872 | 0.054483 | no |
| 3 | 2.661175 | 0.150786 | no |
| 4 | 2.310652 | 0.199737 | no |
| 5 | 2.061984 | 0.448405 | no |
| 6 | 2.652625 | 0.142236 | no |
| 7 | 2.942698 | 0.432309 | no |
| 8 | 2.415501 | 0.094888 | no |
| 9 | 2.272089 | 0.238300 | no |
| 10 | 2.603986 | 0.093597 | no |

## Sorted values (ascending order)

2.061984, 2.272089, 2.310652, 2.415501, 2.455906, 2.564872, 2.603986, 2.652625, 2.661175, 2.942698

## Median and dispersion

- Median: **2.510389s**
- Minimum: 2.061984s
- Maximum: 2.942698s
- Mean: 2.494149s
- Standard deviation (sample): 0.246908s
- Spread (min/max): 42.7120%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 42.7120% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

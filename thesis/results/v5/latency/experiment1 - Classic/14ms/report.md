# Latency Report (classic, 14ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 6.0342s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 5.978419 | 0.010587 | no |
| 2 | 6.379523 | 0.411691 | no |
| 3 | 5.179771 | 0.788061 | no |
| 4 | 5.347834 | 0.619998 | no |
| 5 | 5.214561 | 0.753271 | no |
| 6 | 5.228548 | 0.739283 | no |
| 7 | 7.012761 | 1.044930 | no |
| 8 | 5.957244 | 0.010587 | no |
| 9 | 6.124757 | 0.156925 | no |
| 10 | 6.257939 | 0.290108 | no |

## Sorted values (ascending order)

5.179771, 5.214561, 5.228548, 5.347834, 5.957244, 5.978419, 6.124757, 6.257939, 6.379523, 7.012761

## Median and dispersion

- Median: **5.967831s**
- Minimum: 5.179771s
- Maximum: 7.012761s
- Mean: 5.868136s
- Standard deviation (sample): 0.613766s
- Spread (min/max): 35.3875%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 35.3875% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

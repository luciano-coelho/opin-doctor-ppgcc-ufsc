# Latency Report (pqc, 0ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 12.8899s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 10.152048 | 0.692067 | no |
| 2 | 9.806480 | 1.037635 | no |
| 3 | 9.672633 | 1.171482 | no |
| 4 | 9.864383 | 0.979732 | no |
| 5 | 9.940903 | 0.903212 | no |
| 6 | 11.536182 | 0.692067 | no |
| 7 | 11.912527 | 1.068412 | no |
| 8 | 15.543365 | 4.699250 | no |
| 9 | 16.782979 | 5.938864 | no |
| 10 | 13.628671 | 2.784556 | no |

## Sorted values (ascending order)

9.672633, 9.806480, 9.864383, 9.940903, 10.152048, 11.536182, 11.912527, 13.628671, 15.543365, 16.782979

## Median and dispersion

- Median: **10.844115s**
- Minimum: 9.672633s
- Maximum: 16.782979s
- Mean: 11.884017s
- Standard deviation (sample): 2.595230s
- Spread (min/max): 73.5099%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 73.5099% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

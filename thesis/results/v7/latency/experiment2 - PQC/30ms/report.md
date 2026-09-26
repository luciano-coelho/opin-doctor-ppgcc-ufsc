# Latency Report (pqc, 30ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 13.2478s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 14.436291 | 1.090477 | no |
| 2 | 12.947549 | 0.398265 | no |
| 3 | 12.883945 | 0.461869 | no |
| 4 | 12.912497 | 0.433317 | no |
| 5 | 12.952632 | 0.393182 | no |
| 6 | 12.932884 | 0.412930 | no |
| 7 | 13.754654 | 0.408840 | no |
| 8 | 15.571856 | 2.226042 | no |
| 9 | 14.115930 | 0.770116 | no |
| 10 | 13.738996 | 0.393182 | no |

## Sorted values (ascending order)

12.883945, 12.912497, 12.932884, 12.947549, 12.952632, 13.738996, 13.754654, 14.115930, 14.436291, 15.571856

## Median and dispersion

- Median: **13.345814s**
- Minimum: 12.883945s
- Maximum: 15.571856s
- Mean: 13.624723s
- Standard deviation (sample): 0.892321s
- Spread (min/max): 20.8625%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 20.8625% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

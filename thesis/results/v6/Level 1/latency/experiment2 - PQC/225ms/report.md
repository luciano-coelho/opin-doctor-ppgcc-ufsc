# Latency Report (pqc, 225ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 44.9000s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 43.588028 | 0.106939 | no |
| 2 | 43.632521 | 0.062446 | no |
| 3 | 44.034290 | 0.339323 | no |
| 4 | 43.757413 | 0.062446 | no |
| 5 | 43.426204 | 0.268763 | no |
| 6 | 43.954968 | 0.260001 | no |
| 7 | 43.302200 | 0.392767 | no |
| 8 | 43.329099 | 0.365868 | no |
| 9 | 47.229766 | 3.534799 | no |
| 10 | 51.107624 | 7.412657 | no |

## Sorted values (ascending order)

43.302200, 43.329099, 43.426204, 43.588028, 43.632521, 43.757413, 43.954968, 44.034290, 47.229766, 51.107624

## Median and dispersion

- Median: **43.694967s**
- Minimum: 43.302200s
- Maximum: 51.107624s
- Mean: 44.736211s
- Standard deviation (sample): 2.520201s
- Spread (min/max): 18.0255%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 18.0255% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

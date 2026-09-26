# Latency Report (pqc, 14ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 11.6188s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 11.005062 | 0.076707 | no |
| 2 | 11.084252 | 0.002483 | no |
| 3 | 10.892855 | 0.188914 | no |
| 4 | 11.127224 | 0.045455 | no |
| 5 | 11.079286 | 0.002483 | no |
| 6 | 10.569481 | 0.512288 | no |
| 7 | 11.453004 | 0.371235 | no |
| 8 | 11.167620 | 0.085851 | no |
| 9 | 11.124637 | 0.042868 | no |
| 10 | 11.007435 | 0.074334 | no |

## Sorted values (ascending order)

10.569481, 10.892855, 11.005062, 11.007435, 11.079286, 11.084252, 11.124637, 11.127224, 11.167620, 11.453004

## Median and dispersion

- Median: **11.081769s**
- Minimum: 10.569481s
- Maximum: 11.453004s
- Mean: 11.051086s
- Standard deviation (sample): 0.223414s
- Spread (min/max): 8.3592%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 8.3592% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

# Latency Report (pqc, 14ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 11.3557s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 12.126849 | 0.052875 | no |
| 2 | 11.986798 | 0.087176 | no |
| 3 | 12.199387 | 0.125413 | no |
| 4 | 11.771516 | 0.302458 | no |
| 5 | 11.923957 | 0.150017 | no |
| 6 | 12.846994 | 0.773020 | no |
| 7 | 12.697939 | 0.623965 | no |
| 8 | 11.134521 | 0.939453 | no |
| 9 | 12.021099 | 0.052875 | no |
| 10 | 12.737293 | 0.663319 | no |

## Sorted values (ascending order)

11.134521, 11.771516, 11.923957, 11.986798, 12.021099, 12.126849, 12.199387, 12.697939, 12.737293, 12.846994

## Median and dispersion

- Median: **12.073974s**
- Minimum: 11.134521s
- Maximum: 12.846994s
- Mean: 12.144635s
- Standard deviation (sample): 0.516659s
- Spread (min/max): 15.3799%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 15.3799% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

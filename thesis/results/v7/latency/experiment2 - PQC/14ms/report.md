# Latency Report (pqc, 14ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 10.7149s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 11.273439 | 0.120518 | no |
| 2 | 12.380511 | 1.227590 | no |
| 3 | 10.936508 | 0.216413 | no |
| 4 | 11.269066 | 0.116145 | no |
| 5 | 11.906190 | 0.753269 | no |
| 6 | 11.741589 | 0.588668 | no |
| 7 | 11.036776 | 0.116145 | no |
| 8 | 10.663501 | 0.489420 | no |
| 9 | 10.600567 | 0.552354 | no |
| 10 | 10.959902 | 0.193019 | no |

## Sorted values (ascending order)

10.600567, 10.663501, 10.936508, 10.959902, 11.036776, 11.269066, 11.273439, 11.741589, 11.906190, 12.380511

## Median and dispersion

- Median: **11.152921s**
- Minimum: 10.600567s
- Maximum: 12.380511s
- Mean: 11.276805s
- Standard deviation (sample): 0.571321s
- Spread (min/max): 16.7910%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 16.7910% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

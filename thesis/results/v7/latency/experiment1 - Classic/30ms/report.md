# Latency Report (classic, 30ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 8.0338s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 7.820232 | 0.110441 | no |
| 2 | 7.881447 | 0.049226 | no |
| 3 | 7.874085 | 0.056588 | no |
| 4 | 7.922292 | 0.008381 | no |
| 5 | 8.053964 | 0.123291 | no |
| 6 | 8.125431 | 0.194758 | no |
| 7 | 8.498459 | 0.567786 | no |
| 8 | 7.939055 | 0.008382 | no |
| 9 | 7.955553 | 0.024880 | no |
| 10 | 7.822334 | 0.108339 | no |

## Sorted values (ascending order)

7.820232, 7.822334, 7.874085, 7.881447, 7.922292, 7.939055, 7.955553, 8.053964, 8.125431, 8.498459

## Median and dispersion

- Median: **7.930673s**
- Minimum: 7.820232s
- Maximum: 8.498459s
- Mean: 7.989285s
- Standard deviation (sample): 0.203163s
- Spread (min/max): 8.6727%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 8.6727% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

# Latency Report (classic, 30ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 7.8171s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 8.080668 | 0.003835 | no |
| 2 | 7.729735 | 0.347098 | no |
| 3 | 7.786352 | 0.290481 | no |
| 4 | 8.327847 | 0.251015 | no |
| 5 | 7.980675 | 0.096158 | no |
| 6 | 8.471138 | 0.394305 | no |
| 7 | 8.139439 | 0.062606 | no |
| 8 | 7.762250 | 0.314583 | no |
| 9 | 8.072997 | 0.003835 | no |
| 10 | 8.151826 | 0.074993 | no |

## Sorted values (ascending order)

7.729735, 7.762250, 7.786352, 7.980675, 8.072997, 8.080668, 8.139439, 8.151826, 8.327847, 8.471138

## Median and dispersion

- Median: **8.076833s**
- Minimum: 7.729735s
- Maximum: 8.471138s
- Mean: 8.050293s
- Standard deviation (sample): 0.243602s
- Spread (min/max): 9.5916%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 9.5916% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

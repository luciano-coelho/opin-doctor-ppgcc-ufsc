# Latency Report (classic, 225ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 41.4745s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 40.745265 | 0.480960 | no |
| 2 | 41.237666 | 0.011441 | no |
| 3 | 41.237366 | 0.011141 | no |
| 4 | 41.220600 | 0.005625 | no |
| 5 | 41.231850 | 0.005625 | no |
| 6 | 41.323800 | 0.097575 | no |
| 7 | 41.177335 | 0.048890 | no |
| 8 | 41.219568 | 0.006657 | no |
| 9 | 41.241671 | 0.015446 | no |
| 10 | 41.195991 | 0.030234 | no |

## Sorted values (ascending order)

40.745265, 41.177335, 41.195991, 41.219568, 41.220600, 41.231850, 41.237366, 41.237666, 41.241671, 41.323800

## Median and dispersion

- Median: **41.226225s**
- Minimum: 40.745265s
- Maximum: 41.323800s
- Mean: 41.183111s
- Standard deviation (sample): 0.158521s
- Spread (min/max): 1.4199%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 1.4199% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

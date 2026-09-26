# Latency Report (classic, 14ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 4.7042s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 4.718007 | 0.024795 | no |
| 2 | 4.846345 | 0.153133 | no |
| 3 | 4.670076 | 0.023136 | no |
| 4 | 4.726420 | 0.033208 | no |
| 5 | 4.558583 | 0.134629 | no |
| 6 | 4.665885 | 0.027327 | no |
| 7 | 4.499482 | 0.193730 | no |
| 8 | 4.651421 | 0.041791 | no |
| 9 | 4.716348 | 0.023136 | no |
| 10 | 4.827919 | 0.134707 | no |

## Sorted values (ascending order)

4.499482, 4.558583, 4.651421, 4.665885, 4.670076, 4.716348, 4.718007, 4.726420, 4.827919, 4.846345

## Median and dispersion

- Median: **4.693212s**
- Minimum: 4.499482s
- Maximum: 4.846345s
- Mean: 4.688049s
- Standard deviation (sample): 0.106597s
- Spread (min/max): 7.7090%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 7.7090% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

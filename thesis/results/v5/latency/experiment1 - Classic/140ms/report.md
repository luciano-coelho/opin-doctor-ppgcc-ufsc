# Latency Report (classic, 140ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 27.3279s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 27.083944 | 0.280380 | no |
| 2 | 26.716286 | 0.087278 | no |
| 3 | 26.771524 | 0.032040 | no |
| 4 | 26.846693 | 0.043129 | no |
| 5 | 26.788036 | 0.015528 | no |
| 6 | 26.900888 | 0.097324 | no |
| 7 | 26.687322 | 0.116242 | no |
| 8 | 26.835315 | 0.031751 | no |
| 9 | 26.819091 | 0.015527 | no |
| 10 | 26.620743 | 0.182821 | no |

## Sorted values (ascending order)

26.620743, 26.687322, 26.716286, 26.771524, 26.788036, 26.819091, 26.835315, 26.846693, 26.900888, 27.083944

## Median and dispersion

- Median: **26.803564s**
- Minimum: 26.620743s
- Maximum: 27.083944s
- Mean: 26.806984s
- Standard deviation (sample): 0.127758s
- Spread (min/max): 1.7400%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 1.7400% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

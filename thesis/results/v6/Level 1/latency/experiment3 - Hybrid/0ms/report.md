# Latency Report (hybrid, 0ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 10.5654s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 11.212198 | 0.563237 | no |
| 2 | 10.873980 | 0.225019 | no |
| 3 | 10.192777 | 0.456184 | no |
| 4 | 11.335964 | 0.687003 | no |
| 5 | 10.342423 | 0.306538 | no |
| 6 | 10.675666 | 0.026705 | no |
| 7 | 9.982603 | 0.666358 | no |
| 8 | 10.064541 | 0.584420 | no |
| 9 | 10.639190 | 0.009771 | no |
| 10 | 10.658733 | 0.009772 | no |

## Sorted values (ascending order)

9.982603, 10.064541, 10.192777, 10.342423, 10.639190, 10.658733, 10.675666, 10.873980, 11.212198, 11.335964

## Median and dispersion

- Median: **10.648961s**
- Minimum: 9.982603s
- Maximum: 11.335964s
- Mean: 10.597808s
- Standard deviation (sample): 0.459738s
- Spread (min/max): 13.5572%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 13.5572% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

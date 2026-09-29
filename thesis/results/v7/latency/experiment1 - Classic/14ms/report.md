# Latency Report (classic, 14ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 5.1706s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 5.017237 | 0.024986 | no |
| 2 | 4.912459 | 0.079792 | no |
| 3 | 4.957433 | 0.034818 | no |
| 4 | 4.979561 | 0.012690 | no |
| 5 | 5.185946 | 0.193695 | no |
| 6 | 5.004940 | 0.012689 | no |
| 7 | 5.187998 | 0.195747 | no |
| 8 | 4.977242 | 0.015009 | no |
| 9 | 5.108448 | 0.116197 | no |
| 10 | 4.933520 | 0.058731 | no |

## Sorted values (ascending order)

4.912459, 4.933520, 4.957433, 4.977242, 4.979561, 5.004940, 5.017237, 5.108448, 5.185946, 5.187998

## Median and dispersion

- Median: **4.992251s**
- Minimum: 4.912459s
- Maximum: 5.187998s
- Mean: 5.026478s
- Standard deviation (sample): 0.099901s
- Spread (min/max): 5.6090%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 5.6090% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

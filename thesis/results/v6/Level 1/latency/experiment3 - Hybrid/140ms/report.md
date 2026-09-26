# Latency Report (hybrid, 140ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 33.0914s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 32.200464 | 0.698242 | no |
| 2 | 33.283745 | 0.385039 | no |
| 3 | 32.892134 | 0.006572 | no |
| 4 | 32.972669 | 0.073963 | no |
| 5 | 35.355165 | 2.456459 | no |
| 6 | 32.167214 | 0.731492 | no |
| 7 | 32.905278 | 0.006572 | no |
| 8 | 33.760042 | 0.861336 | no |
| 9 | 32.662118 | 0.236588 | no |
| 10 | 32.042351 | 0.856355 | no |

## Sorted values (ascending order)

32.042351, 32.167214, 32.200464, 32.662118, 32.892134, 32.905278, 32.972669, 33.283745, 33.760042, 35.355165

## Median and dispersion

- Median: **32.898706s**
- Minimum: 32.042351s
- Maximum: 35.355165s
- Mean: 33.024118s
- Standard deviation (sample): 0.976647s
- Spread (min/max): 10.3389%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 10.3389% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

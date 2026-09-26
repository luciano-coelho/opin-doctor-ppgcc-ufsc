# Latency Report (hybrid, 0ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 10.0825s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 10.043509 | 0.226222 | no |
| 2 | 10.342141 | 0.072410 | no |
| 3 | 10.321473 | 0.051742 | no |
| 4 | 10.375782 | 0.106051 | no |
| 5 | 10.097896 | 0.171835 | no |
| 6 | 10.217989 | 0.051742 | no |
| 7 | 9.824694 | 0.445037 | no |
| 8 | 10.404311 | 0.134580 | no |
| 9 | 10.639472 | 0.369741 | no |
| 10 | 10.125640 | 0.144091 | no |

## Sorted values (ascending order)

9.824694, 10.043509, 10.097896, 10.125640, 10.217989, 10.321473, 10.342141, 10.375782, 10.404311, 10.639472

## Median and dispersion

- Median: **10.269731s**
- Minimum: 9.824694s
- Maximum: 10.639472s
- Mean: 10.239291s
- Standard deviation (sample): 0.227772s
- Spread (min/max): 8.2932%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 8.2932% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

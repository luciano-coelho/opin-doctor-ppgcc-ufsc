# Latency Report (hybrid, 30ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 15.2832s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 14.319473 | 0.328031 | no |
| 2 | 14.653534 | 0.006030 | no |
| 3 | 14.197446 | 0.450059 | no |
| 4 | 15.167127 | 0.519623 | no |
| 5 | 14.520719 | 0.126786 | no |
| 6 | 14.641475 | 0.006030 | no |
| 7 | 14.497666 | 0.149838 | no |
| 8 | 14.848237 | 0.200732 | no |
| 9 | 15.032821 | 0.385317 | no |
| 10 | 14.659117 | 0.011613 | no |

## Sorted values (ascending order)

14.197446, 14.319473, 14.497666, 14.520719, 14.641475, 14.653534, 14.659117, 14.848237, 15.032821, 15.167127

## Median and dispersion

- Median: **14.647505s**
- Minimum: 14.197446s
- Maximum: 15.167127s
- Mean: 14.653761s
- Standard deviation (sample): 0.299494s
- Spread (min/max): 6.8300%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 6.8300% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

# Latency Report (hybrid, 14ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 12.5383s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 12.034517 | 0.240683 | no |
| 2 | 12.266025 | 0.009174 | no |
| 3 | 12.213491 | 0.061708 | no |
| 4 | 13.788387 | 1.513188 | no |
| 5 | 12.592585 | 0.317386 | no |
| 6 | 12.014760 | 0.260439 | no |
| 7 | 12.032244 | 0.242955 | no |
| 8 | 12.324459 | 0.049259 | no |
| 9 | 14.404796 | 2.129596 | no |
| 10 | 12.284374 | 0.009175 | no |

## Sorted values (ascending order)

12.014760, 12.032244, 12.034517, 12.213491, 12.266025, 12.284374, 12.324459, 12.592585, 13.788387, 14.404796

## Median and dispersion

- Median: **12.275199s**
- Minimum: 12.014760s
- Maximum: 14.404796s
- Mean: 12.595564s
- Standard deviation (sample): 0.822632s
- Spread (min/max): 19.8925%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 19.8925% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

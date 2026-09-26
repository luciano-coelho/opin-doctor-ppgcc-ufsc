# Latency Report (hybrid, 140ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 32.5527s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 31.529365 | 0.828824 | no |
| 2 | 32.044034 | 0.314155 | no |
| 3 | 33.055423 | 0.697234 | no |
| 4 | 32.024554 | 0.333635 | no |
| 5 | 34.167672 | 1.809483 | no |
| 6 | 32.273982 | 0.084207 | no |
| 7 | 32.442397 | 0.084208 | no |
| 8 | 32.271902 | 0.086287 | no |
| 9 | 32.507940 | 0.149751 | no |
| 10 | 32.513480 | 0.155291 | no |

## Sorted values (ascending order)

31.529365, 32.024554, 32.044034, 32.271902, 32.273982, 32.442397, 32.507940, 32.513480, 33.055423, 34.167672

## Median and dispersion

- Median: **32.358189s**
- Minimum: 31.529365s
- Maximum: 34.167672s
- Mean: 32.483075s
- Standard deviation (sample): 0.712548s
- Spread (min/max): 8.3678%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 8.3678% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

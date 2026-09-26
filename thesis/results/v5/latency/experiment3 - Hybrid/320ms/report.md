# Latency Report (hybrid, 320ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 64.9400s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 64.412850 | 0.075880 | no |
| 2 | 64.117095 | 0.219875 | no |
| 3 | 64.167196 | 0.169774 | no |
| 4 | 64.439979 | 0.103009 | no |
| 5 | 64.221940 | 0.115030 | no |
| 6 | 64.180901 | 0.156069 | no |
| 7 | 64.331419 | 0.005551 | no |
| 8 | 64.342521 | 0.005551 | no |
| 9 | 64.494370 | 0.157400 | no |
| 10 | 64.342592 | 0.005622 | no |

## Sorted values (ascending order)

64.117095, 64.167196, 64.180901, 64.221940, 64.331419, 64.342521, 64.342592, 64.412850, 64.439979, 64.494370

## Median and dispersion

- Median: **64.336970s**
- Minimum: 64.117095s
- Maximum: 64.494370s
- Mean: 64.305086s
- Standard deviation (sample): 0.127292s
- Spread (min/max): 0.5884%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.5884% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

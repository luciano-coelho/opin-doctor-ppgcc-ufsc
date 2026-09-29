# Latency Report (classic, 225ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 43.4491s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 43.262143 | 0.122049 | no |
| 2 | 43.387953 | 0.003761 | no |
| 3 | 43.432314 | 0.048122 | no |
| 4 | 43.604329 | 0.220137 | no |
| 5 | 43.380431 | 0.003761 | no |
| 6 | 43.508190 | 0.123998 | no |
| 7 | 43.343532 | 0.040660 | no |
| 8 | 43.372595 | 0.011597 | no |
| 9 | 43.449970 | 0.065778 | no |
| 10 | 43.366028 | 0.018164 | no |

## Sorted values (ascending order)

43.262143, 43.343532, 43.366028, 43.372595, 43.380431, 43.387953, 43.432314, 43.449970, 43.508190, 43.604329

## Median and dispersion

- Median: **43.384192s**
- Minimum: 43.262143s
- Maximum: 43.604329s
- Mean: 43.410748s
- Standard deviation (sample): 0.094556s
- Spread (min/max): 0.7910%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.7910% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

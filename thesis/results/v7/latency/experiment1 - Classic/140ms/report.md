# Latency Report (classic, 140ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 25.1908s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 24.859146 | 0.000115 | no |
| 2 | 24.871958 | 0.012697 | no |
| 3 | 24.830757 | 0.028504 | no |
| 4 | 24.840031 | 0.019230 | no |
| 5 | 24.913245 | 0.053984 | no |
| 6 | 24.941145 | 0.081884 | no |
| 7 | 24.817256 | 0.042005 | no |
| 8 | 24.859376 | 0.000115 | no |
| 9 | 24.791771 | 0.067490 | no |
| 10 | 24.914169 | 0.054908 | no |

## Sorted values (ascending order)

24.791771, 24.817256, 24.830757, 24.840031, 24.859146, 24.859376, 24.871958, 24.913245, 24.914169, 24.941145

## Median and dispersion

- Median: **24.859261s**
- Minimum: 24.791771s
- Maximum: 24.941145s
- Mean: 24.863885s
- Standard deviation (sample): 0.047238s
- Spread (min/max): 0.6025%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.6025% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

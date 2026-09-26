# Latency Report (classic, 320ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 54.0186s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 53.720716 | 0.051141 | no |
| 2 | 53.636480 | 0.033095 | no |
| 3 | 53.661080 | 0.008495 | no |
| 4 | 53.691098 | 0.021523 | no |
| 5 | 53.673268 | 0.003693 | no |
| 6 | 53.692116 | 0.022541 | no |
| 7 | 53.611204 | 0.058371 | no |
| 8 | 53.606035 | 0.063540 | no |
| 9 | 53.677687 | 0.008112 | no |
| 10 | 53.665882 | 0.003693 | no |

## Sorted values (ascending order)

53.606035, 53.611204, 53.636480, 53.661080, 53.665882, 53.673268, 53.677687, 53.691098, 53.692116, 53.720716

## Median and dispersion

- Median: **53.669575s**
- Minimum: 53.606035s
- Maximum: 53.720716s
- Mean: 53.663557s
- Standard deviation (sample): 0.036408s
- Spread (min/max): 0.2139%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.2139% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

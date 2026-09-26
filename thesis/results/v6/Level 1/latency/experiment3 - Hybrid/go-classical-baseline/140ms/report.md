# Latency Report (hybrid, 140ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 33.2032s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 32.571674 | 0.116755 | no |
| 2 | 32.860389 | 0.405470 | no |
| 3 | 32.892451 | 0.437532 | no |
| 4 | 32.091460 | 0.363459 | no |
| 5 | 33.151824 | 0.696905 | no |
| 6 | 32.703569 | 0.248650 | no |
| 7 | 31.800380 | 0.654539 | no |
| 8 | 32.338164 | 0.116755 | no |
| 9 | 31.957242 | 0.497677 | no |
| 10 | 31.864068 | 0.590851 | no |

## Sorted values (ascending order)

31.800380, 31.864068, 31.957242, 32.091460, 32.338164, 32.571674, 32.703569, 32.860389, 32.892451, 33.151824

## Median and dispersion

- Median: **32.454919s**
- Minimum: 31.800380s
- Maximum: 33.151824s
- Mean: 32.423122s
- Standard deviation (sample): 0.480487s
- Spread (min/max): 4.2498%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 4.2498% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

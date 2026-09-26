# Latency Report (hybrid, 14ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 12.4672s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 11.883657 | 0.381726 | no |
| 2 | 12.011016 | 0.254367 | no |
| 3 | 12.714001 | 0.448618 | no |
| 4 | 12.218501 | 0.046882 | no |
| 5 | 12.241216 | 0.024167 | no |
| 6 | 12.034725 | 0.230658 | no |
| 7 | 12.426858 | 0.161475 | no |
| 8 | 12.289550 | 0.024167 | no |
| 9 | 13.234040 | 0.968657 | no |
| 10 | 12.567041 | 0.301658 | no |

## Sorted values (ascending order)

11.883657, 12.011016, 12.034725, 12.218501, 12.241216, 12.289550, 12.426858, 12.567041, 12.714001, 13.234040

## Median and dispersion

- Median: **12.265383s**
- Minimum: 11.883657s
- Maximum: 13.234040s
- Mean: 12.362061s
- Standard deviation (sample): 0.398629s
- Spread (min/max): 11.3634%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 11.3634% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

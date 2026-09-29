# Latency Report (hybrid, 320ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 62.9169s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 62.836992 | 0.560122 | no |
| 2 | 62.902717 | 0.494397 | no |
| 3 | 62.791537 | 0.605577 | no |
| 4 | 65.099580 | 1.702466 | no |
| 5 | 63.602513 | 0.205399 | no |
| 6 | 64.274133 | 0.877020 | no |
| 7 | 63.142053 | 0.255061 | no |
| 8 | 63.405088 | 0.007974 | no |
| 9 | 64.089499 | 0.692386 | no |
| 10 | 63.389139 | 0.007975 | no |

## Sorted values (ascending order)

62.791537, 62.836992, 62.902717, 63.142053, 63.389139, 63.405088, 63.602513, 64.089499, 64.274133, 65.099580

## Median and dispersion

- Median: **63.397114s**
- Minimum: 62.791537s
- Maximum: 65.099580s
- Mean: 63.553325s
- Standard deviation (sample): 0.740510s
- Spread (min/max): 3.6757%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 3.6757% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

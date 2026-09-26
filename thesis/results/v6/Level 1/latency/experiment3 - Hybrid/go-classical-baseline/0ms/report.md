# Latency Report (hybrid, 0ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **0ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 10.9764s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 10.606860 | 0.290264 | no |
| 2 | 11.071974 | 0.755378 | no |
| 3 | 10.748647 | 0.432051 | no |
| 4 | 10.356606 | 0.040010 | no |
| 5 | 10.276586 | 0.040010 | no |
| 6 | 9.990589 | 0.326007 | no |
| 7 | 10.489996 | 0.173400 | no |
| 8 | 10.153020 | 0.163576 | no |
| 9 | 10.136106 | 0.180490 | no |
| 10 | 10.231114 | 0.085482 | no |

## Sorted values (ascending order)

9.990589, 10.136106, 10.153020, 10.231114, 10.276586, 10.356606, 10.489996, 10.606860, 10.748647, 11.071974

## Median and dispersion

- Median: **10.316596s**
- Minimum: 9.990589s
- Maximum: 11.071974s
- Mean: 10.406150s
- Standard deviation (sample): 0.327873s
- Spread (min/max): 10.8240%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 10.8240% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

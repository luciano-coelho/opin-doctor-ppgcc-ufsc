# Latency Report (classic, 320ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 58.0027s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 57.519801 | 0.040372 | no |
| 2 | 57.554663 | 0.005510 | no |
| 3 | 57.590385 | 0.030212 | no |
| 4 | 57.593947 | 0.033774 | no |
| 5 | 57.565684 | 0.005510 | no |
| 6 | 57.479734 | 0.080439 | no |
| 7 | 57.495389 | 0.064784 | no |
| 8 | 57.639658 | 0.079484 | no |
| 9 | 57.668976 | 0.108803 | no |
| 10 | 57.535700 | 0.024473 | no |

## Sorted values (ascending order)

57.479734, 57.495389, 57.519801, 57.535700, 57.554663, 57.565684, 57.590385, 57.593947, 57.639658, 57.668976

## Median and dispersion

- Median: **57.560173s**
- Minimum: 57.479734s
- Maximum: 57.668976s
- Mean: 57.564394s
- Standard deviation (sample): 0.060542s
- Spread (min/max): 0.3292%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.3292% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

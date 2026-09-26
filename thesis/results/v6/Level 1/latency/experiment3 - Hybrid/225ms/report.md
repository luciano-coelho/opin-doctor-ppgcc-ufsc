# Latency Report (hybrid, 225ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **225ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 51.3241s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 47.559651 | 0.394265 | no |
| 2 | 48.438223 | 1.272837 | no |
| 3 | 46.999373 | 0.166013 | no |
| 4 | 46.234739 | 0.930647 | no |
| 5 | 48.540428 | 1.375042 | no |
| 6 | 47.331400 | 0.166014 | no |
| 7 | 46.956645 | 0.208741 | no |
| 8 | 47.599376 | 0.433990 | no |
| 9 | 46.102183 | 1.063204 | no |
| 10 | 46.111947 | 1.053439 | no |

## Sorted values (ascending order)

46.102183, 46.111947, 46.234739, 46.956645, 46.999373, 47.331400, 47.559651, 47.599376, 48.438223, 48.540428

## Median and dispersion

- Median: **47.165386s**
- Minimum: 46.102183s
- Maximum: 48.540428s
- Mean: 47.187396s
- Standard deviation (sample): 0.885358s
- Spread (min/max): 5.2888%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 5.2888% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

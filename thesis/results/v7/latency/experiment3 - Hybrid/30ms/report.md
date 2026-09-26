# Latency Report (hybrid, 30ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 14.8292s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 14.461954 | 0.030264 | no |
| 2 | 14.229589 | 0.262629 | no |
| 3 | 14.526915 | 0.034697 | no |
| 4 | 14.265968 | 0.226250 | no |
| 5 | 14.662406 | 0.170188 | no |
| 6 | 14.930001 | 0.437783 | no |
| 7 | 14.304280 | 0.187938 | no |
| 8 | 14.522483 | 0.030264 | no |
| 9 | 14.207280 | 0.284938 | no |
| 10 | 15.810934 | 1.318715 | no |

## Sorted values (ascending order)

14.207280, 14.229589, 14.265968, 14.304280, 14.461954, 14.522483, 14.526915, 14.662406, 14.930001, 15.810934

## Median and dispersion

- Median: **14.492218s**
- Minimum: 14.207280s
- Maximum: 15.810934s
- Mean: 14.592181s
- Standard deviation (sample): 0.482978s
- Spread (min/max): 11.2876%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 11.2876% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

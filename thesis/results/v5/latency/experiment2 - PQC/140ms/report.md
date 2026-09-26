# Latency Report (pqc, 140ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 32.8760s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 31.636078 | 0.050569 | no |
| 2 | 35.964445 | 4.378936 | no |
| 3 | 37.094958 | 5.509449 | no |
| 4 | 36.497585 | 4.912076 | no |
| 5 | 31.534939 | 0.050570 | no |
| 6 | 32.411704 | 0.826195 | no |
| 7 | 31.001001 | 0.584508 | no |
| 8 | 31.506807 | 0.078702 | no |
| 9 | 31.247380 | 0.338129 | no |
| 10 | 31.480250 | 0.105259 | no |

## Sorted values (ascending order)

31.001001, 31.247380, 31.480250, 31.506807, 31.534939, 31.636078, 32.411704, 35.964445, 36.497585, 37.094958

## Median and dispersion

- Median: **31.585509s**
- Minimum: 31.001001s
- Maximum: 37.094958s
- Mean: 33.037515s
- Standard deviation (sample): 2.443480s
- Spread (min/max): 19.6573%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 19.6573% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

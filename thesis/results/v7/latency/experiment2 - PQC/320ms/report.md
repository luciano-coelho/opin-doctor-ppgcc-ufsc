# Latency Report (pqc, 320ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **320ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 61.1264s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 61.145948 | 0.022507 | no |
| 2 | 61.126090 | 0.002649 | no |
| 3 | 61.151101 | 0.027660 | no |
| 4 | 61.094610 | 0.028831 | no |
| 5 | 61.073849 | 0.049592 | no |
| 6 | 61.101720 | 0.021721 | no |
| 7 | 61.099701 | 0.023740 | no |
| 8 | 61.236288 | 0.112847 | no |
| 9 | 61.491221 | 0.367780 | no |
| 10 | 61.120792 | 0.002649 | no |

## Sorted values (ascending order)

61.073849, 61.094610, 61.099701, 61.101720, 61.120792, 61.126090, 61.145948, 61.151101, 61.236288, 61.491221

## Median and dispersion

- Median: **61.123441s**
- Minimum: 61.073849s
- Maximum: 61.491221s
- Mean: 61.164132s
- Standard deviation (sample): 0.123401s
- Spread (min/max): 0.6834%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 0.6834% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

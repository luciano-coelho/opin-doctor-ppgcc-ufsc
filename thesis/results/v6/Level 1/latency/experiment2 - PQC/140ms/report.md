# Latency Report (pqc, 140ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 34.2500s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 35.504207 | 5.265819 | no |
| 2 | 30.031309 | 0.207079 | no |
| 3 | 35.038657 | 4.800269 | no |
| 4 | 31.651156 | 1.412768 | no |
| 5 | 30.129232 | 0.109156 | no |
| 6 | 29.948847 | 0.289541 | no |
| 7 | 30.286150 | 0.047762 | no |
| 8 | 30.190625 | 0.047763 | no |
| 9 | 30.031065 | 0.207323 | no |
| 10 | 30.477955 | 0.239567 | no |

## Sorted values (ascending order)

29.948847, 30.031065, 30.031309, 30.129232, 30.190625, 30.286150, 30.477955, 31.651156, 35.038657, 35.504207

## Median and dispersion

- Median: **30.238388s**
- Minimum: 29.948847s
- Maximum: 35.504207s
- Mean: 31.328920s
- Standard deviation (sample): 2.137452s
- Spread (min/max): 18.5495%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 18.5495% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

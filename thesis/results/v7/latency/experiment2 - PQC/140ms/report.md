# Latency Report (pqc, 140ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 28.1402s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 28.766664 | 0.578293 | no |
| 2 | 28.200238 | 0.011867 | no |
| 3 | 28.083548 | 0.104823 | no |
| 4 | 28.176504 | 0.011867 | no |
| 5 | 28.398042 | 0.209671 | no |
| 6 | 28.159936 | 0.028435 | no |
| 7 | 27.614712 | 0.573659 | no |
| 8 | 28.202024 | 0.013653 | no |
| 9 | 27.783180 | 0.405191 | no |
| 10 | 28.287262 | 0.098891 | no |

## Sorted values (ascending order)

27.614712, 27.783180, 28.083548, 28.159936, 28.176504, 28.200238, 28.202024, 28.287262, 28.398042, 28.766664

## Median and dispersion

- Median: **28.188371s**
- Minimum: 27.614712s
- Maximum: 28.766664s
- Mean: 28.167211s
- Standard deviation (sample): 0.314327s
- Spread (min/max): 4.1715%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 4.1715% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

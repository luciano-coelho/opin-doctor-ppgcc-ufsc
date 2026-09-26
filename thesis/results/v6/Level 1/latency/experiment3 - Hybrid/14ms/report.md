# Latency Report (hybrid, 14ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 12.0843s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 12.031950 | 0.196044 | no |
| 2 | 11.910632 | 0.317362 | no |
| 3 | 11.443032 | 0.784961 | no |
| 4 | 13.018529 | 0.790535 | no |
| 5 | 12.321603 | 0.093609 | no |
| 6 | 12.374229 | 0.146235 | no |
| 7 | 12.134384 | 0.093609 | no |
| 8 | 12.056844 | 0.171150 | no |
| 9 | 12.831909 | 0.603915 | no |
| 10 | 12.667169 | 0.439175 | no |

## Sorted values (ascending order)

11.443032, 11.910632, 12.031950, 12.056844, 12.134384, 12.321603, 12.374229, 12.667169, 12.831909, 13.018529

## Median and dispersion

- Median: **12.227994s**
- Minimum: 11.443032s
- Maximum: 13.018529s
- Mean: 12.279028s
- Standard deviation (sample): 0.469043s
- Spread (min/max): 13.7682%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 13.7682% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

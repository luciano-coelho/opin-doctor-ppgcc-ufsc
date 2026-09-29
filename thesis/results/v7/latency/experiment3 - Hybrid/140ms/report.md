# Latency Report (hybrid, 140ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 29.3024s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 29.453274 | 0.258176 | no |
| 2 | 29.331024 | 0.135926 | no |
| 3 | 29.456165 | 0.261067 | no |
| 4 | 29.103445 | 0.091653 | no |
| 5 | 29.026628 | 0.168470 | no |
| 6 | 29.258052 | 0.062954 | no |
| 7 | 29.120946 | 0.074152 | no |
| 8 | 29.151143 | 0.043955 | no |
| 9 | 29.128550 | 0.066548 | no |
| 10 | 29.239052 | 0.043954 | no |

## Sorted values (ascending order)

29.026628, 29.103445, 29.120946, 29.128550, 29.151143, 29.239052, 29.258052, 29.331024, 29.453274, 29.456165

## Median and dispersion

- Median: **29.195098s**
- Minimum: 29.026628s
- Maximum: 29.456165s
- Mean: 29.226828s
- Standard deviation (sample): 0.148232s
- Spread (min/max): 1.4798%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 1.4798% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

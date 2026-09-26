# Latency Report (classic, 30ms, 10 runs)

Experiment (profile): **classic**
Applied latency (scenario): **30ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 7.3044s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 7.111269 | 0.065377 | no |
| 2 | 7.182522 | 0.005876 | no |
| 3 | 7.481675 | 0.305029 | no |
| 4 | 7.154975 | 0.021671 | no |
| 5 | 7.170770 | 0.005876 | no |
| 6 | 7.215858 | 0.039212 | no |
| 7 | 7.149905 | 0.026741 | no |
| 8 | 7.151269 | 0.025377 | no |
| 9 | 7.215659 | 0.039013 | no |
| 10 | 7.377737 | 0.201091 | no |

## Sorted values (ascending order)

7.111269, 7.149905, 7.151269, 7.154975, 7.170770, 7.182522, 7.215659, 7.215858, 7.377737, 7.481675

## Median and dispersion

- Median: **7.176646s**
- Minimum: 7.111269s
- Maximum: 7.481675s
- Mean: 7.221164s
- Standard deviation (sample): 0.116854s
- Spread (min/max): 5.2087%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 5.2087% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

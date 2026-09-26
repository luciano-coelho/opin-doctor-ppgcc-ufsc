# Latency Report (pqc, 140ms, 10 runs)

Experiment (profile): **pqc**
Applied latency (scenario): **140ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 33.7857s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 29.934914 | 0.172576 | no |
| 2 | 30.215425 | 0.107935 | no |
| 3 | 30.122711 | 0.015221 | no |
| 4 | 30.092269 | 0.015221 | no |
| 5 | 29.640727 | 0.466763 | no |
| 6 | 31.312588 | 1.205098 | no |
| 7 | 30.146971 | 0.039481 | no |
| 8 | 30.044717 | 0.062773 | no |
| 9 | 31.771838 | 1.664348 | no |
| 10 | 30.047209 | 0.060281 | no |

## Sorted values (ascending order)

29.640727, 29.934914, 30.044717, 30.047209, 30.092269, 30.122711, 30.146971, 30.215425, 31.312588, 31.771838

## Median and dispersion

- Median: **30.107490s**
- Minimum: 29.640727s
- Maximum: 31.771838s
- Mean: 30.332937s
- Standard deviation (sample): 0.665244s
- Spread (min/max): 7.1898%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 7.1898% among the 10 runs. Within the expected range for real-time measurement (network/OS), not artificially flattened -- no outlier was removed from the median calculation.

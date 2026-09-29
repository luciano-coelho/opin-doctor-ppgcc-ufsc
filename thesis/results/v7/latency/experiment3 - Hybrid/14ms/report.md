# Latency Report (hybrid, 14ms, 10 runs)

Experiment (profile): **hybrid**
Applied latency (scenario): **14ms**

Warmup (run 0, discarded, not included in any statistic): T_fluxo = 5.9691s, no retry.

## The 10 runs -- individual values (collection order)

| # | T_fluxo (s) | Absolute deviation from median (s) | Retry? |
|---|---|---|---|
| 1 | 5.437213 | 0.108496 | no |
| 2 | 5.427241 | 0.118467 | no |
| 3 | 5.338940 | 0.206768 | no |
| 4 | 5.727795 | 0.182087 | no |
| 5 | 5.645961 | 0.100252 | no |
| 6 | 5.432982 | 0.112726 | no |
| 7 | 5.592398 | 0.046690 | no |
| 8 | 5.791819 | 0.246111 | no |
| 9 | 5.499019 | 0.046690 | no |
| 10 | 6.474464 | 0.928756 | no |

## Sorted values (ascending order)

5.338940, 5.427241, 5.432982, 5.437213, 5.499019, 5.592398, 5.645961, 5.727795, 5.791819, 6.474464

## Median and dispersion

- Median: **5.545708s**
- Minimum: 5.338940s
- Maximum: 6.474464s
- Mean: 5.636783s
- Standard deviation (sample): 0.328133s
- Spread (min/max): 21.2687%

## Anomalies

No run needed a retry (PAR TTL or login race) in this scenario.

## Observations

Spread of 21.2687% among the 10 runs. **Elevated spread -- investigate before accepting this scenario as complete.**

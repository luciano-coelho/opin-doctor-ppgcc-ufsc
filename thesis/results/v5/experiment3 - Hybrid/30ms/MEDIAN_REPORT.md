# Median Report (hybrid, 30ms, 10 runs)

Generated at: 2026-08-29T00:44:53.343899+00:00

Median, min, max and %-spread (`(max-min)/min * 100`) across the 10 runs for the size metrics named in scope (see thesis/results/v5/DECISIONS.md). Every other field in a run's baseline_metrics.json is preserved per-run under `runs/` but not aggregated here.

## Scalar metrics

| Metric | Median | Min | Max | Spread |
|---|---|---|---|---|
| `jwt_size_avg_bytes` | 7324.81 | 7324.81 | 7324.81 | 0.0% |
| `total_bytes_exchanged` | 254900.0 | 254900 | 254900 | 0.0% |
| `client_cert_der_bytes` | 6859.0 | 6859 | 6859 | 0.0% |
| `handshake_bytes_p50_bytes` | 25880.0 | 25880.0 | 25880.0 | 0.0% |

## bytes_by_participant

| Participant | Leg | Median | Min | Max | Spread |
|---|---|---|---|---|---|
| AS | sent_bytes | 31058.0 | 31058 | 31058 | 0.0% |
| AS | received_bytes | 59375.0 | 59375 | 59375 | 0.0% |
| Client | sent_bytes | 64878.0 | 64878 | 64878 | 0.0% |
| Client | received_bytes | 190022.0 | 190022 | 190022 | 0.0% |
| PKI/CRL | sent_bytes | 37768.0 | 37768 | 37768 | 0.0% |
| PKI/CRL | received_bytes | 664.0 | 664 | 664 | 0.0% |
| RS | sent_bytes | 121196.0 | 121196 | 121196 | 0.0% |
| RS | received_bytes | 4839.0 | 4839 | 4839 | 0.0% |

## Flagged (>5% min/max spread)

None -- every metric stayed within 5% across all runs.

## Run retries

None -- every run succeeded on the first attempt.

# Median Report (classic, 0ms, 10 runs)

Generated at: 2026-09-12T11:39:28.787324+00:00

Median, min, max and %-spread (`(max-min)/min * 100`) across the 10 runs for the size metrics named in scope (see thesis/results/v5/DECISIONS.md). Every other field in a run's baseline_metrics.json is preserved per-run under `runs/` but not aggregated here.

## Scalar metrics

| Metric | Median | Min | Max | Spread |
|---|---|---|---|---|
| `jwt_size_avg_bytes` | 1385.42 | 1385.42 | 1385.42 | 0.0% |
| `total_bytes_exchanged` | 66828.0 | 66828 | 66828 | 0.0% |
| `client_cert_der_bytes` | 1494.0 | 1494 | 1494 | 0.0% |
| `handshake_bytes_p50_bytes` | 5119.0 | 5119.0 | 5119.0 | 0.0% |

## bytes_by_participant

| Participant | Leg | Median | Min | Max | Spread |
|---|---|---|---|---|---|
| Client | sent_bytes | 17754.0 | 17754 | 17754 | 0.0% |
| Client | received_bytes | 49074.0 | 49074 | 49074 | 0.0% |
| Other | sent_bytes | 40222.0 | 40222 | 40222 | 0.0% |
| Other | received_bytes | 17022.0 | 17022 | 17022 | 0.0% |
| PKI/CRL | sent_bytes | 8852.0 | 8852 | 8852 | 0.0% |
| PKI/CRL | received_bytes | 732.0 | 732 | 732 | 0.0% |

## Flagged (>5% min/max spread)

None -- every metric stayed within 5% across all runs.

## Run retries

None -- every run succeeded on the first attempt.

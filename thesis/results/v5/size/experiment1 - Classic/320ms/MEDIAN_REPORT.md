# Median Report (classic, 320ms, 10 runs)

Generated at: 2026-08-28T23:29:03.468647+00:00

Median, min, max and %-spread (`(max-min)/min * 100`) across the 10 runs for the size metrics named in scope (see thesis/results/v5/DECISIONS.md). Every other field in a run's baseline_metrics.json is preserved per-run under `runs/` but not aggregated here.

## Scalar metrics

| Metric | Median | Min | Max | Spread |
|---|---|---|---|---|
| `jwt_size_avg_bytes` | 1385.42 | 1385.42 | 1385.42 | 0.0% |
| `total_bytes_exchanged` | 66452.0 | 66452 | 66452 | 0.0% |
| `client_cert_der_bytes` | 1494.0 | 1494 | 1494 | 0.0% |
| `handshake_bytes_p50_bytes` | 9785.0 | 9785.0 | 9785.0 | 0.0% |

## bytes_by_participant

| Participant | Leg | Median | Min | Max | Spread |
|---|---|---|---|---|---|
| AS | sent_bytes | 14188.0 | 14188 | 14188 | 0.0% |
| AS | received_bytes | 11875.0 | 11875 | 11875 | 0.0% |
| Client | sent_bytes | 17378.0 | 17378 | 17378 | 0.0% |
| Client | received_bytes | 49074.0 | 49074 | 49074 | 0.0% |
| PKI/CRL | sent_bytes | 8852.0 | 8852 | 8852 | 0.0% |
| PKI/CRL | received_bytes | 664.0 | 664 | 664 | 0.0% |
| RS | sent_bytes | 26034.0 | 26034 | 26034 | 0.0% |
| RS | received_bytes | 4839.0 | 4839 | 4839 | 0.0% |

## Flagged (>5% min/max spread)

None -- every metric stayed within 5% across all runs.

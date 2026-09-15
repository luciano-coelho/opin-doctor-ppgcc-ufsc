# Median Report (pqc, 14ms, 10 runs)

Generated at: 2026-09-12T12:31:56.990427+00:00

Median, min, max and %-spread (`(max-min)/min * 100`) across the 10 runs for the size metrics named in scope (see thesis/results/v5/DECISIONS.md). Every other field in a run's baseline_metrics.json is preserved per-run under `runs/` but not aggregated here.

## Scalar metrics

| Metric | Median | Min | Max | Spread |
|---|---|---|---|---|
| `jwt_size_avg_bytes` | 5458.81 | 5458.81 | 5458.81 | 0.0% |
| `total_bytes_exchanged` | 185013.0 | 185013 | 185013 | 0.0% |
| `client_cert_der_bytes` | 2953.0 | 2953 | 2953 | 0.0% |
| `handshake_bytes_p50_bytes` | 16605.0 | 16605.0 | 16605.0 | 0.0% |

## bytes_by_participant

| Participant | Leg | Median | Min | Max | Spread |
|---|---|---|---|---|---|
| Client | sent_bytes | 47579.0 | 47579 | 47579 | 0.0% |
| Client | received_bytes | 137434.0 | 137434 | 137434 | 0.0% |
| Other | sent_bytes | 120822.0 | 120822 | 120822 | 0.0% |
| Other | received_bytes | 46847.0 | 46847 | 46847 | 0.0% |
| PKI/CRL | sent_bytes | 16612.0 | 16612 | 16612 | 0.0% |
| PKI/CRL | received_bytes | 732.0 | 732 | 732 | 0.0% |

## Flagged (>5% min/max spread)

None -- every metric stayed within 5% across all runs.

## Run retries

None -- every run succeeded on the first attempt.

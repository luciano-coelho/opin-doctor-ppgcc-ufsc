# Median Report (pqc, 225ms, 10 runs)

Generated at: 2026-08-29T00:18:17.168307+00:00

Median, min, max and %-spread (`(max-min)/min * 100`) across the 10 runs for the size metrics named in scope (see thesis/results/v5/DECISIONS.md). Every other field in a run's baseline_metrics.json is preserved per-run under `runs/` but not aggregated here.

## Scalar metrics

| Metric | Median | Min | Max | Spread |
|---|---|---|---|---|
| `jwt_size_avg_bytes` | 5458.81 | 5458.81 | 5458.81 | 0.0% |
| `total_bytes_exchanged` | 184637.0 | 184637 | 184637 | 0.0% |
| `client_cert_der_bytes` | 2953.0 | 2953 | 2953 | 0.0% |
| `handshake_bytes_p50_bytes` | 19756.0 | 19756.0 | 19756.0 | 0.0% |

## bytes_by_participant

| Participant | Leg | Median | Min | Max | Spread |
|---|---|---|---|---|---|
| AS | sent_bytes | 29570.0 | 29570 | 29570 | 0.0% |
| AS | received_bytes | 41700.0 | 41700 | 41700 | 0.0% |
| Client | sent_bytes | 47203.0 | 47203 | 47203 | 0.0% |
| Client | received_bytes | 137434.0 | 137434 | 137434 | 0.0% |
| PKI/CRL | sent_bytes | 16612.0 | 16612 | 16612 | 0.0% |
| PKI/CRL | received_bytes | 664.0 | 664 | 664 | 0.0% |
| RS | sent_bytes | 91252.0 | 91252 | 91252 | 0.0% |
| RS | received_bytes | 4839.0 | 4839 | 4839 | 0.0% |

## Flagged (>5% min/max spread)

None -- every metric stayed within 5% across all runs.

## Run retries

None -- every run succeeded on the first attempt.

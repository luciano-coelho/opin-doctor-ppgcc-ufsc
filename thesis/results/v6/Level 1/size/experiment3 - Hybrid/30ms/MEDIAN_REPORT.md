# Median Report (hybrid, 30ms, 10 runs)

Generated at: 2026-09-11T05:37:25.092647+00:00

Median, min, max and %-spread (`(max-min)/min * 100`) across the 10 runs for the size metrics named in scope (see thesis/results/v5/DECISIONS.md). Every other field in a run's baseline_metrics.json is preserved per-run under `runs/` but not aggregated here.

## Scalar metrics

| Metric | Median | Min | Max | Spread |
|---|---|---|---|---|
| `jwt_size_avg_bytes` | 7324.81 | 7324.81 | 7324.81 | 0.0% |
| `total_bytes_exchanged` | 255276.0 | 255276 | 255276 | 0.0% |
| `client_cert_der_bytes` | 6859.0 | 6859 | 6859 | 0.0% |
| `handshake_bytes_p50_bytes` | 18023.0 | 18023.0 | 18023.0 | 0.0% |

## bytes_by_participant

| Participant | Leg | Median | Min | Max | Spread |
|---|---|---|---|---|---|
| Client | sent_bytes | 65254.0 | 65254 | 65254 | 0.0% |
| Client | received_bytes | 190022.0 | 190022 | 190022 | 0.0% |
| Other | sent_bytes | 152254.0 | 152254 | 152254 | 0.0% |
| Other | received_bytes | 64522.0 | 64522 | 64522 | 0.0% |
| PKI/CRL | sent_bytes | 37768.0 | 37768 | 37768 | 0.0% |
| PKI/CRL | received_bytes | 732.0 | 732 | 732 | 0.0% |

## Flagged (>5% min/max spread)

None -- every metric stayed within 5% across all runs.

## Run retries

1 run(s) needed a retry (see thesis/results/v5/DECISIONS.md, Decision 5):

- run 3, attempt 1: RuntimeError: No consent/confirm page reached; body[:500]=<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Error</title>
</head>
<body>
<pre>InvalidGrant: invalid_grant<br> &nbsp; &nbsp;at InsurerAdapter.getConsent (file:///home/node/app/utils/opin/adapter.js:53:13)<br> &nbsp; &nbsp;at process.processTicksAndRejections (node:internal/process/task_queues:104:5)<br> &nbsp; &nbsp;at async file:///home/node/app/utils/opin/routes.js:94:25</pre>
</body>
</html>


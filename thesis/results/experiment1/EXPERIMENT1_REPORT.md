# Experiment 1 Report -- Classical Baseline vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run against the classical-cryptography baseline (thesis/scripts/baseline_automation.py).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 71628 | 37 | 13 | 1159.54 |
| 14ms | 71764 | 37 | 13 | 1159.54 |
| 30ms | 70638 | 36 | 12 | 1177 |
| 140ms | 71037 | 37 | 13 | 1159.54 |
| 225ms | 72886 | 38 | 14 | 1144.57 |
| 320ms | 72890 | 38 | 14 | 1144.57 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 56 | 15.41 | 29.0 | 18.84 | 56.5 |
| 14ms | 56 | 33.96 | 48.35 | 43.54 | 150.0 |
| 30ms | 56 | 59.61 | 85.2 | 77.3 | 282.25 |
| 140ms | 93 | 326.95 | 559.0 | 292.58 | 1062.0 |
| 225ms | 60 | 446.83 | 515.0 | 461.68 | 1699.75 |
| 320ms | 136 | 694.88 | 1281.0 | 610.63 | 2340.5 |

## Bytes by participant

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 29696 | 29696 | 29696 | 29700 | 29698 | 29698 |
| Client | 71628 | 71764 | 70638 | 71037 | 72886 | 72890 |
| Directory | 1640 | 1776 | 650 | 1776 | 2902 | 2902 |
| PKI/CRL | 20614 | 20614 | 20614 | 20610 | 20608 | 20612 |
| RS | 19678 | 19678 | 19678 | 18951 | 19678 | 19678 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 97.5 | 530.5 | 187.0 | 463.5 | 1740.0 | 625.5 |
| P95 | 604.9 | 676.5 | 849.65 | 804.65 | 4953.75 | 965.85 |
| P99 | 676.18 | 677.7 | 937.13 | 810.53 | 5406.75 | 992.37 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 12.5 | 83.0 | 164.0 | 790.0 | 1384.0 | 1945.0 |
| P95 | 12.95 | 83.9 | 164.9 | 856.6 | 1387.6 | 1945.9 |
| P99 | 12.99 | 83.98 | 164.98 | 862.52 | 1387.92 | 1945.98 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 49.5 | 135.0 | 248.5 | 1082 | 1590.5 | 2285.5 |
| P95 | 58.05 | 139.5 | 258.85 | 1082 | 1703.45 | 2517.25 |
| P99 | 58.81 | 139.9 | 259.77 | 1082 | 1713.49 | 2537.85 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 27 | 115 | 221 | 909 | 1424 | 2022 |
| P95 | 27 | 115 | 221 | 909 | 1424 | 2022 |
| P99 | 27 | 115 | 221 | 909 | 1424 | 2022 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 91.5 | 138.0 | 271.0 | 1058.5 | 1650.5 | 2322.0 |
| P95 | 109.95 | 138.0 | 275.5 | 1066.15 | 1651.85 | 2330.1 |
| P99 | 111.59 | 138.0 | 275.9 | 1066.83 | 1651.97 | 2330.82 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 93.5 | 145.0 | 260.5 | 1053.5 | 1674.5 | 2349.0 |
| P95 | 95.75 | 153.1 | 261.85 | 1058.45 | 1694.75 | 2360.7 |
| P99 | 95.95 | 153.82 | 261.97 | 1058.89 | 1696.55 | 2361.74 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 96.0 | 162.0 | 257.0 | 1073.0 | 1685.0 | 2319.0 |
| P95 | 104.1 | 162.9 | 265.1 | 1094.6 | 1695.8 | 2337.0 |
| P99 | 104.82 | 162.98 | 265.82 | 1096.52 | 1696.76 | 2338.6 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 91.5 | 134.5 | 256.5 | 1062.5 | 1658.5 | 2352.0 |
| P95 | 102.75 | 136.75 | 259.65 | 1072.85 | 1664.35 | 2379.9 |
| P99 | 103.75 | 136.95 | 259.93 | 1073.77 | 1664.87 | 2382.38 |

### `/organisations/{id}/softwarestatements/{id}/assertion`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 17 | 74 | - | 580 | 958.0 | 1321.0 |
| P95 | 17 | 74 | - | 580 | 961.6 | 1321.0 |
| P99 | 17 | 74 | - | 580 | 961.92 | 1321.0 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 28.0 | 92.5 | 182.0 | 762.0 | 1177.0 | 1650.5 |
| P95 | 32.5 | 92.95 | 182.9 | 775.5 | 1181.5 | 1653.65 |
| P99 | 32.9 | 92.99 | 182.98 | 776.7 | 1181.9 | 1653.93 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 261.0 | 147.0 | 352.0 | 660.5 | 1776.0 | 541.0 |
| P95 | 970.85 | 2853.35 | 1080.1 | 2075.4 | 2235.9 | 1517.85 |
| P99 | 1050.17 | 3231.47 | 1164.82 | 2217.48 | 2266.38 | 1611.57 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 23.0 | 92.0 | 182.5 | 745.5 | 1313.5 | 1667.5 |
| P95 | 96.2 | 239.9 | 440.95 | 1678.95 | 2891.75 | 3668.25 |
| P99 | 100.04 | 247.18 | 441.79 | 1702.19 | 3024.75 | 3669.65 |

## Methodological notes

- **Keep-alive connections**: the mTLS handshake cost is counted once per TCP connection, not once per HTTP request. A connection kept alive across several requests (including, in a few cases, across a scenario boundary) reports the same cached handshake timestamp for every request it serves -- expected behavior of the gateway instrumentation (mock-service-os/mock_mtls/main.go), not a measurement error.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively. This exists because of the point above: a handful of genuinely slow keep-alive connections replay the same extreme value across several requests, so a plain P99-based threshold is self-defeating in samples this small (P99 already sits near the duplicated extreme values, so "3x P99" never clears its own threshold) -- the median stays representative as long as the outlier cluster is a minority of the sample, which held for every scenario here. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **Known person_api_core failure**: `person_api_core_test-module_v2.0.0` failed in all 6 scenarios on the same pre-existing, unrelated issue -- a schema validation failure on the `address` field of the mock's person data (0 of 2 valid schemas), reproduced identically each time (1095 log entries). This is a mock data/schema issue, not a cryptography- or latency-related finding, and doesn't affect the `opin-consent-api-status-test-v3` results this experiment is built on (6/6 PASSED).
- **320ms instability**: this scenario needed 4 attempts to complete cleanly. Three transient, non-repeating failures appeared first (an aborted mTLS handshake, an internal 401 on the auth server's consent-revalidation call, a gateway<->auth proxy EOF/502) followed by a SessionNotFound recurrence that only cleared with a fresh private-browsing window. Root cause attributed to browser-side session/cookie state accumulated over the ~20 manual logins performed across this session's testing, not a deterministic bug in the environment -- container health (CPU/memory) was verified normal throughout, and no failure mode repeated on retry.

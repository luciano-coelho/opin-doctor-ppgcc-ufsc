# Experiment 1 Report -- Classical Baseline vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run against the classical-cryptography baseline (thesis/scripts/baseline_automation.py).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 71744 | 37 | 13 | 1159.54 |
| 14ms | 71750 | 37 | 13 | 1159.54 |
| 30ms | 70622 | 36 | 12 | 1177 |
| 140ms | 71756 | 37 | 13 | 1159.54 |
| 225ms | 71475 | 37 | 13 | 1159.54 |
| 320ms | 70816 | 37 | 13 | 1159.54 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 60 | 24.16 | 50.2 | 82.68 | 190.1 |
| 14ms | 56 | 45.27 | 64.0 | 52.45 | 180.25 |
| 30ms | 55 | 74.24 | 107.1 | 81.67 | 299.4 |
| 140ms | 56 | 221.29 | 297.25 | 291.96 | 1035.5 |
| 225ms | 63 | 304.14 | 469.8 | 470.25 | 1629.0 |
| 320ms | 57 | 453.89 | 656.0 | 655.86 | 2301.0 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since the classical baseline doesn't change algorithms between them.

| Latency | Samples | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 59 | 11326.69 | 11263.0 | 13976.0 | 14740.32 |
| 14ms | 56 | 11502.16 | 11234.5 | 13976.0 | 14768.7 |
| 30ms | 55 | 11495.45 | 11003.0 | 13976.0 | 14777.08 |
| 140ms | 56 | 11541.5 | 11234.5 | 13976.0 | 14770.9 |
| 225ms | 63 | 11464.27 | 11003.0 | 13976.0 | 14702.48 |
| 320ms | 56 | 11524.43 | 11234.5 | 13976.0 | 14768.7 |

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 29696 | 29698 | 29696 | 29704 | 29696 | 29698 |
| Client (test tool, total traffic) | 71744 | 71750 | 70622 | 71756 | 71475 | 70816 |
| Directory | 1776 | 1776 | 650 | 1776 | 1504 | 1776 |
| PKI/CRL | 20610 | 20614 | 20614 | 20614 | 20613 | 20612 |
| RS | 19662 | 19662 | 19662 | 19662 | 19662 | 18730 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 388.0 | 124.0 | 314.5 | 218.0 | 302.0 | 384.5 |
| P95 | 1485.0 | 617.9 | 627.3 | 813.15 | 4007.0 | 769.1 |
| P99 | 1600.2 | 686.78 | 667.86 | 894.63 | 4506.2 | 784.22 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 31.5 | 92.0 | 171.0 | 713.5 | 1139.0 | 1936.5 |
| P95 | 39.15 | 93.8 | 176.4 | 714.85 | 1139.9 | 1936.95 |
| P99 | 39.83 | 93.96 | 176.88 | 714.97 | 1139.98 | 1936.99 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 1180.0 | 163.0 | 245.0 | 894.0 | 1392.0 | 1970.5 |
| P95 | 2167.3 | 175.6 | 245.0 | 898.5 | 1392.9 | 1970.95 |
| P99 | 2255.06 | 176.72 | 245.0 | 898.9 | 1392.98 | 1970.99 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 43 | 155 | 219 | 877 | 1383 | 1952 |
| P95 | 43 | 155 | 219 | 877 | 1383 | 1952 |
| P99 | 43 | 155 | 219 | 877 | 1383 | 1952 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 188.0 | 170.5 | 266.5 | 1020.5 | 1632.5 | 2283.0 |
| P95 | 250.1 | 173.65 | 269.65 | 1022.75 | 1642.85 | 2288.4 |
| P99 | 255.62 | 173.93 | 269.93 | 1022.95 | 1643.77 | 2288.88 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 124.0 | 186.5 | 270.5 | 1018.5 | 1628.0 | 2281.0 |
| P95 | 151.9 | 186.95 | 274.55 | 1019.85 | 1636.1 | 2282.8 |
| P99 | 154.38 | 186.99 | 274.91 | 1019.97 | 1636.82 | 2282.96 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 114.5 | 167.0 | 268.0 | 1019.0 | 1617.0 | 2279.0 |
| P95 | 123.95 | 171.5 | 269.8 | 1021.7 | 1619.7 | 2279.9 |
| P99 | 124.79 | 171.9 | 269.96 | 1021.94 | 1619.94 | 2279.98 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 132.5 | 178.5 | 253.5 | 1016.5 | 1608.5 | 2287 |
| P95 | 137.45 | 185.25 | 256.65 | 1018.75 | 1611.65 | 2287 |
| P99 | 137.89 | 185.85 | 256.93 | 1018.95 | 1611.93 | 2287 |

### `/organisations/{id}/softwarestatements/{id}/assertion`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 44 | 89 | - | 587 | 927 | 1298 |
| P95 | 44 | 89 | - | 587 | 927 | 1298 |
| P99 | 44 | 89 | - | 587 | 927 | 1298 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 57.5 | 109.5 | 183.5 | 728.5 | 1152.0 | 1627.0 |
| P95 | 64.25 | 116.25 | 185.75 | 730.75 | 1152.0 | 1630.6 |
| P99 | 64.85 | 116.85 | 185.95 | 730.95 | 1152.0 | 1630.92 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 1053.0 | 143.0 | 323.5 | 356.5 | 497.0 | 977.5 |
| P95 | 2320.3 | 707.85 | 809.3 | 916.65 | 778.95 | 2234.9 |
| P99 | 2459.26 | 782.37 | 864.26 | 980.13 | 784.59 | 2397.38 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 43.0 | 105.5 | 186.5 | 726.0 | 1381.5 | 1785.5 |
| P95 | 217.75 | 316.55 | 447.1 | 1609.9 | 2554.0 | 3584.65 |
| P99 | 233.15 | 318.51 | 451.02 | 1611.58 | 2554.0 | 3584.93 |

## Methodological notes

- **Keep-alive connections**: the mTLS handshake cost is counted once per TCP connection, not once per HTTP request. A connection kept alive across several requests (including, in a few cases, across a scenario boundary) reports the same cached handshake timestamp for every request it serves -- expected behavior of the gateway instrumentation (mock-service-os/mock_mtls/main.go), not a measurement error.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively. This exists because of the point above: a handful of genuinely slow keep-alive connections replay the same extreme value across several requests, so a plain P99-based threshold is self-defeating in samples this small (P99 already sits near the duplicated extreme values, so "3x P99" never clears its own threshold) -- the median stays representative as long as the outlier cluster is a minority of the sample, which held for every scenario here. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **Known person_api_core failure**: `person_api_core_test-module_v2.0.0` failed in all 6 scenarios on the same pre-existing, unrelated issue -- a schema validation failure on the `address` field of the mock's person data (0 of 2 valid schemas), reproduced identically each time (1095 log entries). This is a mock data/schema issue, not a cryptography- or latency-related finding, and doesn't affect the `opin-consent-api-status-test-v3` results this experiment is built on (6/6 PASSED).
- **Environment stability**: during earlier test passes, the highest-latency scenario (320ms) occasionally needed a retry after transient failures (an aborted mTLS handshake, an internal 401 on the auth server's consent-revalidation call, a gateway<->auth proxy EOF/502, or a SessionNotFound tied to accumulated browser session state after many manual logins in one sitting). None of these repeated deterministically, and container health (CPU/memory) was consistently normal when checked -- the data in this report is from a run where every scenario, including 320ms, completed cleanly on the first attempt.

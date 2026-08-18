# Experiment 2 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 184637 | 28 | 26 | 5458.81 |
| 14ms | 184637 | 28 | 26 | 5458.81 |
| 30ms | 184637 | 28 | 26 | 5458.81 |
| 140ms | 184637 | 28 | 26 | 5458.81 |
| 225ms | 184637 | 28 | 26 | 5458.81 |
| 320ms | 184637 | 28 | 26 | 5458.81 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 13.25 | 17.85 | 45.08 | 132.3 |
| 14ms | 38 | 40.83 | 45.25 | 82.5 | 251.95 |
| 30ms | 38 | 80.33 | 101.75 | 115.29 | 388.65 |
| 140ms | 38 | 334 | 465.5 | 362.71 | 1249.3 |
| 225ms | 38 | 488 | 553.25 | 541.03 | 1739.65 |
| 320ms | 38 | 691.17 | 755.5 | 758.13 | 2383.2 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |
| 14ms | 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |
| 30ms | 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |
| 140ms | 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |
| 225ms | 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |
| 320ms | 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 71270 | 71270 | 71270 | 71270 | 71270 | 71270 |
| Client (opin_flow.py, total traffic) | 184637 | 184637 | 184637 | 184637 | 184637 | 184637 |
| PKI/CRL | 17276 | 17276 | 17276 | 17276 | 17276 | 17276 |
| RS | 96091 | 96091 | 96091 | 96091 | 96091 | 96091 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 7.21 | 21.76 | 37.36 | 151.17 | 231.59 | 327.59 |
| P95 | 8.94 | 22.85 | 40.09 | 152.46 | 232.0 | 329.75 |
| P99 | 9.09 | 22.95 | 40.34 | 152.58 | 232.04 | 329.95 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 39.22 | 109.48 | 203.69 | 816.21 | 1268.01 | 1794.29 |
| P95 | 50.05 | 118.69 | 225.87 | 895.95 | 1368.95 | 1939.24 |
| P99 | 51.01 | 119.5 | 227.85 | 903.04 | 1377.92 | 1952.12 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 133.85 | 223.03 | 261.7 | 933.2 | 1447.97 | 2026.42 |
| P95 | 133.91 | 236.79 | 266.52 | 945.59 | 1450.39 | 2038.91 |
| P99 | 133.92 | 238.01 | 266.95 | 946.69 | 1450.61 | 2040.02 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 43.74 | 77.84 | 130.39 | 451.02 | 704.63 | 1006.38 |
| P95 | 43.74 | 77.84 | 130.39 | 451.02 | 704.63 | 1006.38 |
| P99 | 43.74 | 77.84 | 130.39 | 451.02 | 704.63 | 1006.38 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 60.81 | 153.55 | 176.53 | 615.35 | 971.0 | 1329.99 |
| P95 | 63.9 | 172.34 | 186.55 | 621.56 | 972.13 | 1334.21 |
| P99 | 64.18 | 174.01 | 187.44 | 622.11 | 972.23 | 1334.58 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 62.89 | 160.77 | 178.6 | 645.18 | 955.99 | 1341.29 |
| P95 | 65.12 | 176.07 | 180.49 | 659.66 | 963.08 | 1347.94 |
| P99 | 65.32 | 177.43 | 180.66 | 660.95 | 963.71 | 1348.53 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 79.98 | 171.6 | 172.04 | 625.43 | 967.68 | 1343.99 |
| P95 | 80.09 | 175.94 | 172.32 | 626.18 | 971.72 | 1349.54 |
| P99 | 80.1 | 176.32 | 172.34 | 626.25 | 972.07 | 1350.03 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 71.44 | 156.24 | 178.72 | 622.82 | 957.8 | 1349.62 |
| P95 | 81.67 | 180.09 | 180.11 | 630.31 | 964.62 | 1353.95 |
| P99 | 82.58 | 182.21 | 180.24 | 630.98 | 965.23 | 1354.34 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 39.96 | 77.22 | 125.58 | 448.4 | 707.1 | 1149.28 |
| P95 | 46.92 | 83.07 | 127.18 | 451.62 | 708.52 | 1288.81 |
| P99 | 47.54 | 83.59 | 127.32 | 451.91 | 708.65 | 1301.21 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 39.03 | 95.52 | 142.98 | 589.92 | 967.58 | 1319.86 |
| P95 | 44.82 | 107.15 | 143.37 | 601.33 | 983.52 | 1336.77 |
| P99 | 45.34 | 108.18 | 143.41 | 602.35 | 984.94 | 1338.27 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 104.1 | 173.32 | 221.24 | 766.64 | 1198.7 | 1668.5 |
| P95 | 185.23 | 298.52 | 383.43 | 1459.43 | 1923.42 | 2658.18 |
| P99 | 186.93 | 303.09 | 387.13 | 1493.32 | 1923.55 | 2659.2 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

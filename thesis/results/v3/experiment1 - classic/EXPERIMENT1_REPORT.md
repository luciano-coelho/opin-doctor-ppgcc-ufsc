# Experiment 1 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 67864 | 28 | 26 | 1385.42 |
| 14ms | 67870 | 28 | 26 | 1385.42 |
| 30ms | 67870 | 28 | 26 | 1385.42 |
| 140ms | 67866 | 28 | 26 | 1385.42 |
| 225ms | 67866 | 28 | 26 | 1385.42 |
| 320ms | 67866 | 28 | 26 | 1385.42 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 67 | 0.73 | 1.0 | 14.96 | 46.9 |
| 14ms | 67 | 37.21 | 64.4 | 49.46 | 151.8 |
| 30ms | 70 | 64.35 | 94.25 | 86 | 261.55 |
| 140ms | 70 | 260.45 | 301.0 | 338.71 | 1097.6 |
| 225ms | 70 | 414 | 473.4 | 552.01 | 1770.05 |
| 320ms | 70 | 595.78 | 665.8 | 774.03 | 2603.55 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 20 | 10739.65 | 11455.0 | 12091.0 | 12091.0 |
| 14ms | 21 | 10736.1 | 11455.0 | 12053.0 | 12083.4 |
| 30ms | 22 | 10797.68 | 11455.0 | 12089.1 | 12091.0 |
| 140ms | 22 | 10797.68 | 11455.0 | 12089.1 | 12091.0 |
| 225ms | 22 | 10777.86 | 11455.0 | 12089.1 | 12091.0 |
| 320ms | 25 | 10781.72 | 10913.0 | 12083.4 | 12091.0 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 26143 | 26143 | 26143 | 26143 | 26143 | 26143 |
| Client (opin_flow.py, total traffic) | 67864 | 67870 | 67870 | 67866 | 67866 | 67866 |
| PKI/CRL | 10704 | 10710 | 10710 | 10706 | 10706 | 10706 |
| RS | 31017 | 31017 | 31017 | 31017 | 31017 | 31017 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 363.54 | 49.14 | 53.62 | 373.5 | 319.35 | 756.77 |
| P95 | 668.15 | 72.19 | 79.7 | 618.78 | 584.8 | 1367.16 |
| P99 | 695.23 | 74.24 | 82.02 | 640.58 | 608.39 | 1421.41 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 52.93 | 132.21 | 215.52 | 802.52 | 1266.23 | 1793.89 |
| P95 | 63.17 | 142.81 | 228.38 | 867.15 | 1374.23 | 1940.66 |
| P99 | 64.08 | 143.75 | 229.52 | 872.89 | 1383.83 | 1953.71 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 76.29 | 182.18 | 327.17 | 894.14 | 1402.04 | 2018.43 |
| P95 | 95.41 | 229.62 | 414.84 | 895.0 | 1404.87 | 2064.99 |
| P99 | 97.11 | 233.84 | 422.63 | 895.08 | 1405.12 | 2069.13 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 21.73 | 71.34 | 110.21 | 437.92 | 690.56 | 980.8 |
| P95 | 21.73 | 71.34 | 110.21 | 437.92 | 690.56 | 980.8 |
| P99 | 21.73 | 71.34 | 110.21 | 437.92 | 690.56 | 980.8 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 30.75 | 76.22 | 140.53 | 578.47 | 918.5 | 1299.42 |
| P95 | 31.26 | 76.9 | 141.58 | 580.77 | 918.76 | 1300.1 |
| P99 | 31.31 | 76.96 | 141.67 | 580.97 | 918.78 | 1300.17 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 29.17 | 80.41 | 143.91 | 584.67 | 921.15 | 1326.01 |
| P95 | 33.29 | 80.6 | 145.21 | 585.05 | 922.85 | 1333.72 |
| P99 | 33.65 | 80.62 | 145.33 | 585.08 | 923.0 | 1334.41 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 26.34 | 79.86 | 139.02 | 580.73 | 923.18 | 1304.94 |
| P95 | 27.97 | 81.15 | 139.37 | 581.64 | 925.84 | 1305.37 |
| P99 | 28.11 | 81.26 | 139.4 | 581.72 | 926.07 | 1305.41 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 28.09 | 79.47 | 144.26 | 585.99 | 925.39 | 1300.91 |
| P95 | 28.31 | 81.26 | 147.96 | 588.39 | 927.63 | 1301.51 |
| P99 | 28.33 | 81.41 | 148.29 | 588.61 | 927.83 | 1301.56 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 12.62 | 43.39 | 70.88 | 289.36 | 461.55 | 653.1 |
| P95 | 16.18 | 49.48 | 72.36 | 290.99 | 462.4 | 654.44 |
| P99 | 16.5 | 50.02 | 72.49 | 291.13 | 462.47 | 654.56 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 454.48 | 458.57 | 264.19 | 658.06 | 4310.36 | 587.53 |
| P95 | 762.87 | 717.47 | 315.99 | 838.33 | 7396.25 | 762.8 |
| P99 | 790.29 | 740.48 | 320.59 | 854.36 | 7670.55 | 778.38 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 23.22 | 102.91 | 173.75 | 727.71 | 1263.64 | 1647.65 |
| P95 | 43.79 | 166.2 | 279.52 | 1165.3 | 1856.97 | 2880.59 |
| P99 | 45.45 | 167.39 | 279.59 | 1165.87 | 1859.32 | 2919.63 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

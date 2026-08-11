# Experiment 1 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 67606 | 28 | 26 | 1385.42 |
| 14ms | 67606 | 28 | 26 | 1385.42 |
| 30ms | 67602 | 28 | 26 | 1385.42 |
| 140ms | 67606 | 28 | 26 | 1385.42 |
| 225ms | 67602 | 28 | 26 | 1385.42 |
| 320ms | 67602 | 28 | 26 | 1385.42 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 58 | 17 | 26.3 | 15.26 | 48.0 |
| 14ms | 58 | 43 | 57.8 | 54.22 | 172.15 |
| 30ms | 58 | 81.33 | 118.8 | 106.31 | 324.45 |
| 140ms | 58 | 298.81 | 310.5 | 382.72 | 1164.95 |
| 225ms | 58 | 452 | 475.55 | 612.02 | 1852.05 |
| 320ms | 58 | 660.8 | 666.55 | 850.98 | 2637.75 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 10 | 10211.8 | 10198.0 | 10748.1 | 10777.62 |
| 14ms | 9 | 10229.67 | 10381.0 | 10827.0 | 10895.8 |
| 30ms | 10 | 10320.7 | 10398.5 | 11037.85 | 11119.57 |
| 140ms | 16 | 10410.25 | 10511.0 | 10905.75 | 11041.95 |
| 225ms | 10 | 10267.7 | 10398.5 | 10908.15 | 11042.43 |
| 320ms | 10 | 10225.8 | 10398.5 | 10725.7 | 10824.34 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 26063 | 26063 | 26063 | 26063 | 26063 | 26063 |
| Client (opin_flow.py, total traffic) | 67606 | 67606 | 67602 | 67606 | 67602 | 67602 |
| PKI/CRL | 10670 | 10670 | 10666 | 10670 | 10666 | 10666 |
| RS | 30873 | 30873 | 30873 | 30873 | 30873 | 30873 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 26.77 | 54.31 | 311.07 | 53.24 | 318.52 | 363.09 |
| P95 | 26.93 | 76.16 | 567.17 | 76.0 | 582.96 | 608.95 |
| P99 | 26.94 | 78.1 | 589.93 | 78.02 | 606.46 | 630.8 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 39.64 | 102.83 | 192.8 | 806.64 | 1269.49 | 1795.81 |
| P95 | 44.75 | 109.29 | 204.68 | 864.48 | 1371.45 | 1937.94 |
| P99 | 45.2 | 109.86 | 205.73 | 869.63 | 1380.51 | 1950.57 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 54.47 | 147.37 | 294.4 | 909.81 | 1402.03 | 1967.87 |
| P95 | 55.47 | 152.09 | 319.14 | 911.42 | 1406.41 | 1970.51 |
| P99 | 55.56 | 152.51 | 321.34 | 911.56 | 1406.8 | 1970.74 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 17.69 | 59.79 | 118.86 | 439.64 | 691.76 | 981.36 |
| P95 | 17.69 | 59.79 | 118.86 | 439.64 | 691.76 | 981.36 |
| P99 | 17.69 | 59.79 | 118.86 | 439.64 | 691.76 | 981.36 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 22.31 | 80.04 | 194.45 | 588.75 | 927.14 | 1302.88 |
| P95 | 23.55 | 81.3 | 197.42 | 590.94 | 929.14 | 1303.15 |
| P99 | 23.67 | 81.41 | 197.68 | 591.14 | 929.32 | 1303.17 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 28.88 | 84.8 | 184.97 | 592.2 | 941.09 | 1306.55 |
| P95 | 33.62 | 85.79 | 190.79 | 592.57 | 955.35 | 1307.51 |
| P99 | 34.04 | 85.87 | 191.31 | 592.61 | 956.62 | 1307.59 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 27.52 | 80.27 | 160.53 | 590.16 | 928.68 | 1302.25 |
| P95 | 30.15 | 81.21 | 162.32 | 595.21 | 933.18 | 1304.98 |
| P99 | 30.39 | 81.29 | 162.48 | 595.65 | 933.58 | 1305.22 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 30.87 | 82.52 | 154.32 | 587.7 | 931.11 | 1304.17 |
| P95 | 33.98 | 83.53 | 154.74 | 591.9 | 931.7 | 1304.77 |
| P99 | 34.25 | 83.62 | 154.78 | 592.27 | 931.76 | 1304.82 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 10.26 | 37.56 | 81.81 | 303.72 | 459.8 | 653.03 |
| P95 | 10.6 | 38.38 | 86.73 | 315.23 | 460.53 | 653.84 |
| P99 | 10.63 | 38.46 | 87.17 | 316.25 | 460.6 | 653.91 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 169.24 | 205.21 | 4857.23 | 240.58 | 482.94 | 1066.08 |
| P95 | 217.97 | 248.62 | 8513.48 | 314.08 | 813.46 | 1819.56 |
| P99 | 222.3 | 252.48 | 8838.48 | 320.62 | 842.84 | 1886.54 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 21.25 | 96.35 | 213.01 | 733.85 | 1156.75 | 1631.5 |
| P95 | 37.55 | 169.18 | 335.65 | 1172.58 | 1851.52 | 2884.95 |
| P99 | 38.17 | 171.12 | 336.09 | 1172.62 | 1852.21 | 2923.71 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

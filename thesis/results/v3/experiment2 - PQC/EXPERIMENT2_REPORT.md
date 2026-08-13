# Experiment 2 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 178026 | 28 | 26 | 5458.81 |
| 14ms | 178031 | 28 | 26 | 5458.81 |
| 30ms | 178025 | 28 | 26 | 5458.81 |
| 140ms | 178029 | 28 | 26 | 5458.81 |
| 225ms | 178027 | 28 | 26 | 5458.81 |
| 320ms | 178027 | 28 | 26 | 5458.81 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 8.33 | 12.25 | 129.26 | 217.85 |
| 14ms | 38 | 37.67 | 42.75 | 60.61 | 202.1 |
| 30ms | 38 | 70 | 73.75 | 91.97 | 287.1 |
| 140ms | 38 | 289.17 | 290.75 | 333.26 | 1067.95 |
| 225ms | 38 | 458.33 | 461.25 | 522.66 | 1687.75 |
| 320ms | 38 | 648 | 649.75 | 731.82 | 2337.2 |

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
| Client (opin_flow.py, total traffic) | 178026 | 178031 | 178025 | 178029 | 178027 | 178027 |
| PKI/CRL | 10665 | 10670 | 10664 | 10668 | 10666 | 10666 |
| RS | 96091 | 96091 | 96091 | 96091 | 96091 | 96091 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 304.69 | 22.92 | 309.31 | 23.44 | 301.13 | 308.87 |
| P95 | 557.94 | 23.85 | 565.56 | 24.4 | 549.41 | 563.38 |
| P99 | 580.45 | 23.94 | 588.33 | 24.48 | 571.48 | 586.01 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 36.37 | 105.1 | 188.53 | 792.41 | 1265.62 | 1777.9 |
| P95 | 48.81 | 113.25 | 201.93 | 858.04 | 1378.57 | 1922.87 |
| P99 | 49.92 | 113.98 | 203.12 | 863.87 | 1388.61 | 1935.76 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 1426.91 | 194.76 | 268.28 | 897.02 | 1403.55 | 1974.83 |
| P95 | 2622.55 | 197.53 | 271.84 | 899.2 | 1406.39 | 1977.18 |
| P99 | 2728.83 | 197.77 | 272.15 | 899.39 | 1406.65 | 1977.39 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 46.37 | 99.11 | 118.03 | 439.43 | 692.02 | 980.52 |
| P95 | 46.37 | 99.11 | 118.03 | 439.43 | 692.02 | 980.52 |
| P99 | 46.37 | 99.11 | 118.03 | 439.43 | 692.02 | 980.52 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 171.47 | 94.14 | 154.95 | 591.57 | 926.07 | 1301.72 |
| P95 | 265.63 | 94.98 | 159.81 | 593.91 | 926.48 | 1305.05 |
| P99 | 274.0 | 95.05 | 160.25 | 594.12 | 926.52 | 1305.35 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 83.35 | 100.3 | 158.43 | 589.24 | 930.67 | 1306.46 |
| P95 | 98.32 | 102.1 | 160.92 | 591.83 | 931.73 | 1308.71 |
| P99 | 99.66 | 102.26 | 161.14 | 592.06 | 931.83 | 1308.91 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 76.36 | 89.51 | 154.1 | 597.61 | 928.02 | 1300.9 |
| P95 | 83.28 | 89.99 | 154.15 | 608.12 | 929.67 | 1301.11 |
| P99 | 83.9 | 90.03 | 154.16 | 609.05 | 929.82 | 1301.12 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 110.64 | 100.31 | 149.94 | 585.44 | 938.23 | 1299.47 |
| P95 | 118.12 | 101.87 | 153.13 | 586.05 | 942.69 | 1301.24 |
| P99 | 118.78 | 102.01 | 153.41 | 586.1 | 943.09 | 1301.39 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 31.76 | 82.83 | 112.83 | 435.64 | 694.99 | 973.1 |
| P95 | 40.34 | 87.11 | 115.88 | 436.08 | 699.73 | 974.27 |
| P99 | 41.11 | 87.5 | 116.15 | 436.12 | 700.15 | 974.38 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 631.33 | 122.96 | 544.48 | 400.36 | 523.65 | 630.75 |
| P95 | 1045.51 | 128.45 | 726.24 | 648.54 | 828.83 | 765.48 |
| P99 | 1082.33 | 128.94 | 742.39 | 670.6 | 855.96 | 777.45 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 119.71 | 136.63 | 199.89 | 743.01 | 1159.11 | 1638.4 |
| P95 | 161.3 | 231.56 | 332.75 | 1195.26 | 1884.45 | 2615.28 |
| P99 | 166.39 | 233.28 | 334.52 | 1196.92 | 1889.52 | 2615.41 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

# Experiment 1 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 67600 | 28 | 26 | 1385.42 |
| 14ms | 67606 | 28 | 26 | 1385.42 |
| 30ms | 67606 | 28 | 26 | 1385.42 |
| 140ms | 67602 | 28 | 26 | 1385.42 |
| 225ms | 67606 | 28 | 26 | 1385.42 |
| 320ms | 67602 | 28 | 26 | 1385.42 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 30.2 | 37.2 | 39.32 | 119.5 |
| 14ms | 38 | 61 | 63.8 | 64.18 | 191.05 |
| 30ms | 38 | 105 | 129.75 | 101.95 | 327.4 |
| 140ms | 38 | 328 | 349.25 | 341.18 | 1105.85 |
| 225ms | 38 | 506.33 | 539.5 | 531.5 | 1720.65 |
| 320ms | 38 | 758.17 | 1005.75 | 733.55 | 2393.55 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 9969.5 | 9785.0 | 10407.25 | 10414.25 |
| 14ms | 6 | 9969.5 | 9785.0 | 10407.25 | 10414.25 |
| 30ms | 6 | 9969.5 | 9785.0 | 10407.25 | 10414.25 |
| 140ms | 6 | 9969.5 | 9785.0 | 10407.25 | 10414.25 |
| 225ms | 6 | 9969.5 | 9785.0 | 10407.25 | 10414.25 |
| 320ms | 6 | 9969.5 | 9785.0 | 10407.25 | 10414.25 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 26063 | 26063 | 26063 | 26063 | 26063 | 26063 |
| Client (opin_flow.py, total traffic) | 67600 | 67606 | 67606 | 67602 | 67606 | 67602 |
| PKI/CRL | 10664 | 10670 | 10670 | 10666 | 10670 | 10666 |
| RS | 30873 | 30873 | 30873 | 30873 | 30873 | 30873 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 302.23 | 24.38 | 24.49 | 305.9 | 22.37 | 312.48 |
| P95 | 554.28 | 25.09 | 26.2 | 560.94 | 22.6 | 572.11 |
| P99 | 576.68 | 25.15 | 26.35 | 583.61 | 22.62 | 595.19 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 58.18 | 125.25 | 260.97 | 839.58 | 1488.98 | 1857.77 |
| P95 | 76.05 | 134.58 | 316.98 | 888.83 | 1494.75 | 2039.45 |
| P99 | 77.63 | 135.41 | 321.96 | 893.21 | 1495.26 | 2055.6 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 202.07 | 314.41 | 294.25 | 975.69 | 1487.95 | 2041.27 |
| P95 | 276.0 | 411.18 | 294.56 | 980.36 | 1501.33 | 2057.31 |
| P99 | 282.58 | 419.78 | 294.59 | 980.78 | 1502.52 | 2058.73 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 77.37 | 81.46 | 118.72 | 452.2 | 723.65 | 993.84 |
| P95 | 77.37 | 81.46 | 118.72 | 452.2 | 723.65 | 993.84 |
| P99 | 77.37 | 81.46 | 118.72 | 452.2 | 723.65 | 993.84 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 60.64 | 112.9 | 171.94 | 629.27 | 959.2 | 1344.4 |
| P95 | 73.5 | 114.09 | 175.71 | 640.03 | 965.87 | 1347.84 |
| P99 | 74.64 | 114.2 | 176.04 | 640.99 | 966.46 | 1348.15 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 51.26 | 123.24 | 183.16 | 677.18 | 964.45 | 1353.1 |
| P95 | 51.59 | 124.46 | 184.22 | 728.0 | 975.41 | 1362.01 |
| P99 | 51.62 | 124.57 | 184.31 | 732.51 | 976.38 | 1362.8 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 84.87 | 105.97 | 175.03 | 637.94 | 952.36 | 1323.52 |
| P95 | 94.53 | 113.86 | 181.91 | 641.09 | 955.97 | 1327.02 |
| P99 | 95.39 | 114.56 | 182.53 | 641.37 | 956.29 | 1327.33 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 79.43 | 167.59 | 181.71 | 623.71 | 958.42 | 1383.38 |
| P95 | 94.98 | 200.63 | 184.92 | 625.98 | 960.01 | 1430.95 |
| P99 | 96.36 | 203.57 | 185.21 | 626.18 | 960.15 | 1435.18 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 36.48 | 53.27 | 77.14 | 347.88 | 474.73 | 660.1 |
| P95 | 38.11 | 63.04 | 80.24 | 371.88 | 481.03 | 663.82 |
| P99 | 38.26 | 63.91 | 80.52 | 374.01 | 481.59 | 664.15 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 1021.97 | 93.17 | 115.52 | 390.96 | 100.69 | 520.5 |
| P95 | 1316.4 | 106.78 | 131.53 | 645.13 | 109.88 | 886.34 |
| P99 | 1342.58 | 107.99 | 132.95 | 667.72 | 110.7 | 918.86 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 92.59 | 153.12 | 213.96 | 773.56 | 1231.48 | 1658.57 |
| P95 | 131.91 | 208.42 | 359.12 | 1241.02 | 1947.11 | 2660.92 |
| P99 | 134.27 | 209.58 | 360.52 | 1242.36 | 1951.67 | 2662.27 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

# Experiment 2 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 178009 | 28 | 26 | 5458.81 |
| 14ms | 178011 | 28 | 26 | 5458.81 |
| 30ms | 178009 | 28 | 26 | 5458.81 |
| 140ms | 178011 | 28 | 26 | 5458.81 |
| 225ms | 178011 | 28 | 26 | 5458.81 |
| 320ms | 178011 | 28 | 26 | 5458.81 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 56 | 29.14 | 54.1 | 31.46 | 116.25 |
| 14ms | 58 | 54.22 | 65.4 | 127.9 | 299.65 |
| 30ms | 58 | 83.67 | 100.0 | 97.6 | 301.05 |
| 140ms | 58 | 225.89 | 301.4 | 392.9 | 1167.0 |
| 225ms | 58 | 338.78 | 469.6 | 625.34 | 1863.05 |
| 320ms | 58 | 466.33 | 672.0 | 871.84 | 2602.9 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 10 | 13672.9 | 15440.0 | 16115.25 | 16127.85 |
| 14ms | 10 | 13627.5 | 15440.0 | 15934.8 | 16091.76 |
| 30ms | 10 | 13667.6 | 15440.0 | 16115.25 | 16127.85 |
| 140ms | 10 | 13648.4 | 15440.0 | 16115.25 | 16127.85 |
| 225ms | 10 | 13648.4 | 15440.0 | 16115.25 | 16127.85 |
| 320ms | 10 | 13648.4 | 15440.0 | 16115.25 | 16127.85 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 71270 | 71270 | 71270 | 71270 | 71270 | 71270 |
| Client (opin_flow.py, total traffic) | 178009 | 178011 | 178009 | 178011 | 178011 | 178011 |
| PKI/CRL | 10664 | 10666 | 10664 | 10666 | 10666 | 10666 |
| RS | 96075 | 96075 | 96075 | 96075 | 96075 | 96075 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 301.71 | 314.19 | 311.17 | 341.22 | 320.08 | 353.48 |
| P95 | 550.49 | 560.52 | 567.58 | 556.83 | 584.34 | 557.29 |
| P99 | 572.61 | 582.42 | 590.37 | 576.0 | 607.83 | 575.4 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 37.95 | 128.83 | 192.15 | 797.14 | 1265.25 | 1783.98 |
| P95 | 48.39 | 145.34 | 205.53 | 865.07 | 1368.44 | 1930.46 |
| P99 | 49.32 | 146.81 | 206.72 | 871.1 | 1377.62 | 1943.48 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 203.39 | 1290.02 | 261.27 | 910.84 | 1406.03 | 1972.33 |
| P95 | 306.26 | 2290.62 | 278.25 | 914.19 | 1410.99 | 1973.47 |
| P99 | 315.4 | 2379.56 | 279.76 | 914.49 | 1411.43 | 1973.57 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 47.8 | 79.25 | 123.09 | 440.42 | 697.98 | 985.63 |
| P95 | 47.8 | 79.25 | 123.09 | 440.42 | 697.98 | 985.63 |
| P99 | 47.8 | 79.25 | 123.09 | 440.42 | 697.98 | 985.63 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 50.87 | 192.79 | 147.96 | 597.44 | 929.34 | 1308.09 |
| P95 | 51.79 | 274.08 | 149.24 | 599.2 | 932.74 | 1309.13 |
| P99 | 51.88 | 281.3 | 149.36 | 599.36 | 933.04 | 1309.22 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 51.56 | 128.16 | 154.63 | 594.44 | 931.14 | 1306.46 |
| P95 | 63.96 | 145.64 | 159.6 | 596.88 | 935.88 | 1310.11 |
| P99 | 65.06 | 147.19 | 160.04 | 597.1 | 936.31 | 1310.44 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 37.37 | 109.88 | 147.23 | 590.84 | 929.7 | 1304.48 |
| P95 | 41.74 | 119.29 | 147.86 | 591.92 | 932.93 | 1304.88 |
| P99 | 42.13 | 120.13 | 147.92 | 592.02 | 933.22 | 1304.92 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 28.29 | 109.07 | 148.04 | 602.23 | 925.6 | 1303.43 |
| P95 | 29.5 | 120.7 | 150.64 | 611.04 | 926.23 | 1306.04 |
| P99 | 29.61 | 121.74 | 150.87 | 611.82 | 926.29 | 1306.27 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 21.83 | 75.75 | 110.32 | 433.7 | 693.33 | 981.83 |
| P95 | 21.84 | 77.8 | 110.37 | 433.96 | 694.59 | 985.79 |
| P99 | 21.84 | 77.98 | 110.38 | 433.98 | 694.71 | 986.15 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 586.1 | 632.44 | 388.24 | 567.23 | 814.55 | 458.41 |
| P95 | 1002.04 | 1069.98 | 647.16 | 913.24 | 1380.34 | 690.88 |
| P99 | 1039.02 | 1108.87 | 670.18 | 943.99 | 1430.63 | 711.54 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 74.37 | 226.2 | 199.24 | 749.39 | 1165.73 | 1633.13 |
| P95 | 118.95 | 283.17 | 333.0 | 1207.04 | 1867.59 | 2619.57 |
| P99 | 123.04 | 284.89 | 334.53 | 1207.72 | 1867.89 | 2620.61 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

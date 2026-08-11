# Experiment 2 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 178031 | 28 | 26 | 5458.81 |
| 14ms | 178031 | 28 | 26 | 5458.81 |
| 30ms | 178025 | 28 | 26 | 5458.81 |
| 140ms | 178027 | 28 | 26 | 5458.81 |
| 225ms | 178031 | 28 | 26 | 5458.81 |
| 320ms | 178027 | 28 | 26 | 5458.81 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 18.83 | 29.75 | 32.87 | 108.05 |
| 14ms | 38 | 45.67 | 50.25 | 61.58 | 198.65 |
| 30ms | 38 | 76 | 79.25 | 91.32 | 281.15 |
| 140ms | 38 | 297 | 314.0 | 333.89 | 1040.05 |
| 225ms | 38 | 461.67 | 467.0 | 513.11 | 1650.9 |
| 320ms | 38 | 652.5 | 656.5 | 742.03 | 2367.7 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 15611.83 | 15500.0 | 15995.75 | 16075.95 |
| 14ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |
| 30ms | 6 | 15611.83 | 15500.0 | 15995.75 | 16075.95 |
| 140ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |
| 225ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |
| 320ms | 6 | 15611.83 | 15500.0 | 15995.75 | 16075.95 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 71270 | 71270 | 71270 | 71270 | 71270 | 71270 |
| Client (opin_flow.py, total traffic) | 178031 | 178031 | 178025 | 178027 | 178031 | 178027 |
| PKI/CRL | 10670 | 10670 | 10664 | 10666 | 10670 | 10666 |
| RS | 96091 | 96091 | 96091 | 96091 | 96091 | 96091 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 25.93 | 25.21 | 344.46 | 347.52 | 90.74 | 328.31 |
| P95 | 26.83 | 26.15 | 561.37 | 570.64 | 100.4 | 573.57 |
| P99 | 26.91 | 26.23 | 580.65 | 590.47 | 101.26 | 595.37 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 49.99 | 101.6 | 191.83 | 809.1 | 1264.62 | 1787.25 |
| P95 | 54.32 | 106.14 | 207.82 | 883.59 | 1366.77 | 1931.94 |
| P99 | 54.7 | 106.54 | 209.24 | 890.21 | 1375.85 | 1944.8 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 126.75 | 165.24 | 255.28 | 908.03 | 1392.94 | 1964.08 |
| P95 | 155.54 | 178.78 | 262.92 | 910.03 | 1393.7 | 1965.18 |
| P99 | 158.1 | 179.98 | 263.6 | 910.21 | 1393.77 | 1965.28 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 39.73 | 67.21 | 117.94 | 437.73 | 698.15 | 980.66 |
| P95 | 39.73 | 67.21 | 117.94 | 437.73 | 698.15 | 980.66 |
| P99 | 39.73 | 67.21 | 117.94 | 437.73 | 698.15 | 980.66 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 56.18 | 95.39 | 169.95 | 589.48 | 920.78 | 1305.03 |
| P95 | 59.28 | 96.41 | 173.99 | 598.88 | 920.88 | 1306.01 |
| P99 | 59.55 | 96.5 | 174.35 | 599.71 | 920.89 | 1306.1 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 51.88 | 90.78 | 191.31 | 592.26 | 931.19 | 1307.77 |
| P95 | 60.12 | 94.13 | 210.68 | 592.67 | 933.01 | 1309.44 |
| P99 | 60.86 | 94.42 | 212.4 | 592.71 | 933.17 | 1309.59 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 35.32 | 83.09 | 157.62 | 586.95 | 930.22 | 1308.71 |
| P95 | 35.37 | 84.42 | 161.66 | 589.54 | 933.63 | 1313.61 |
| P99 | 35.38 | 84.54 | 162.02 | 589.77 | 933.94 | 1314.04 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 43.64 | 91.88 | 155.81 | 585.35 | 928.86 | 1306.6 |
| P95 | 45.08 | 98.58 | 160.27 | 587.64 | 933.84 | 1308.92 |
| P99 | 45.21 | 99.18 | 160.66 | 587.85 | 934.28 | 1309.13 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 21.44 | 60.4 | 109.3 | 438.14 | 687.66 | 971.7 |
| P95 | 22.48 | 61.95 | 110.43 | 440.63 | 688.65 | 971.74 |
| P99 | 22.57 | 62.09 | 110.53 | 440.85 | 688.73 | 971.74 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 257.45 | 1199.56 | 523.48 | 1194.99 | 1354.19 | 771.26 |
| P95 | 385.77 | 2171.71 | 693.0 | 1435.24 | 1459.7 | 959.84 |
| P99 | 397.17 | 2258.13 | 708.07 | 1456.59 | 1469.08 | 976.6 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 66.5 | 127.17 | 195.24 | 742.46 | 1150.87 | 1625.47 |
| P95 | 120.04 | 215.29 | 331.93 | 1184.41 | 1843.83 | 2614.76 |
| P99 | 121.29 | 216.25 | 334.87 | 1184.81 | 1844.11 | 2616.98 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

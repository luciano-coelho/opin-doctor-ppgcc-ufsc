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
| 0ms | 38 | 17.83 | 30.0 | 199.53 | 429.0 |
| 14ms | 38 | 45.5 | 50.75 | 76.42 | 227.0 |
| 30ms | 38 | 72.17 | 75.0 | 106.13 | 322.5 |
| 140ms | 38 | 318 | 385.25 | 348.11 | 1110.65 |
| 225ms | 38 | 472.5 | 492.25 | 545.05 | 1721.75 |
| 320ms | 38 | 660.33 | 675.25 | 752.76 | 2397.3 |

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
| P50 | 4.34 | 19.59 | 48.32 | 147.04 | 231.45 | 327.88 |
| P95 | 6.04 | 19.71 | 59.29 | 147.72 | 232.03 | 329.01 |
| P99 | 6.2 | 19.72 | 60.26 | 147.78 | 232.08 | 329.11 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 37.4 | 116.54 | 214.12 | 811.31 | 1283.36 | 1809.51 |
| P95 | 37.4 | 121.59 | 252.44 | 878.81 | 1380.93 | 1948.62 |
| P99 | 37.4 | 122.04 | 255.85 | 884.82 | 1389.6 | 1960.98 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 89.47 | 219.64 | 303.28 | 955.24 | 1482.6 | 2018.11 |
| P95 | 89.47 | 231.58 | 325.73 | 962.12 | 1483.86 | 2022.17 |
| P99 | 89.47 | 232.64 | 327.73 | 962.73 | 1483.97 | 2022.53 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 74.2 | 71.66 | 128.09 | 459.46 | 744.69 | 990.87 |
| P95 | 74.2 | 71.66 | 128.09 | 459.46 | 744.69 | 990.87 |
| P99 | 74.2 | 71.66 | 128.09 | 459.46 | 744.69 | 990.87 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 263.05 | 110.88 | 177.21 | 615.62 | 959.33 | 1336.16 |
| P95 | 432.16 | 113.42 | 177.58 | 617.48 | 962.05 | 1341.78 |
| P99 | 447.19 | 113.64 | 177.61 | 617.64 | 962.3 | 1342.28 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 138.19 | 132.41 | 174.97 | 633.5 | 1159.56 | 1340.64 |
| P95 | 162.77 | 135.07 | 177.02 | 655.84 | 1343.47 | 1346.49 |
| P99 | 164.95 | 135.3 | 177.2 | 657.82 | 1359.81 | 1347.01 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 148.45 | 116.65 | 170.49 | 638.09 | 967.12 | 1346.2 |
| P95 | 168.27 | 124.44 | 172.5 | 645.75 | 982.62 | 1346.61 |
| P99 | 170.03 | 125.13 | 172.68 | 646.43 | 984.0 | 1346.64 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 151.91 | 110.7 | 174.68 | 618.98 | 1001.95 | 1333.27 |
| P95 | 174.38 | 118.25 | 181.24 | 621.59 | 1027.57 | 1344.49 |
| P99 | 176.38 | 118.92 | 181.83 | 621.82 | 1029.85 | 1345.49 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 39.56 | 78.93 | 121.44 | 440.67 | 819.54 | 984.12 |
| P95 | 50.09 | 85.19 | 125.41 | 443.85 | 913.81 | 986.07 |
| P99 | 51.02 | 85.75 | 125.76 | 444.14 | 922.19 | 986.24 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 33.59 | 78.45 | 159.89 | 588.68 | 931.91 | 1319.56 |
| P95 | 42.91 | 82.86 | 177.39 | 589.54 | 935.17 | 1333.94 |
| P99 | 43.74 | 83.25 | 178.94 | 589.62 | 935.46 | 1335.22 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 52.48 | 148.31 | 222.6 | 758.04 | 1177.25 | 1671.9 |
| P95 | 52.48 | 291.88 | 367.28 | 1243.27 | 1925.64 | 2689.98 |
| P99 | 52.48 | 299.7 | 371.23 | 1247.56 | 1930.92 | 2691.99 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

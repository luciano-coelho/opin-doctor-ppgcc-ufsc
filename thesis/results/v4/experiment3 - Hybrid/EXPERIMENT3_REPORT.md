# Experiment 3 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py in hybrid mode (direct AS/RS traffic, no Conformance Suite -- CRYPTO_PROFILE=classic|pqc originally justified in thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8; the hybrid profile and everything specific to it -- Strong Nesting response signing, hybrid JWKS, hybrid mTLS certificates -- is documented in thesis/results/v4/DECISIONS.md, see in particular Decision 2 (Strong Nesting signing architecture) and Decision 6 (hybrid mTLS certificates, the dual nested combiner)).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 218738 | 28 | 26 | 5933.96 |
| 14ms | 218738 | 28 | 26 | 5933.96 |
| 30ms | 218738 | 28 | 26 | 5933.96 |
| 140ms | 218738 | 28 | 26 | 5933.96 |
| 225ms | 218738 | 28 | 26 | 5933.96 |
| 320ms | 218738 | 28 | 26 | 5933.96 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 31.33 | 38.25 | 34.34 | 101.15 |
| 14ms | 38 | 60.17 | 68.5 | 73.32 | 252.65 |
| 30ms | 38 | 98.17 | 118.25 | 101.16 | 366.05 |
| 140ms | 38 | 303.67 | 313.25 | 346.87 | 1210.15 |
| 225ms | 38 | 470.5 | 476.5 | 540.89 | 1865.15 |
| 320ms | 38 | 674.83 | 713.75 | 763.74 | 2630.9 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 14ms | 6 | 25997.67 | 25880.0 | 26402.0 | 26489.2 |
| 30ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 140ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 225ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 320ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 78231 | 78231 | 78231 | 78231 | 78231 | 78231 |
| Client (opin_flow.py, total traffic) | 218738 | 218738 | 218738 | 218738 | 218738 | 218738 |
| PKI/CRL | 38432 | 38432 | 38432 | 38432 | 38432 | 38432 |
| RS | 102075 | 102075 | 102075 | 102075 | 102075 | 102075 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 3.17 | 19.24 | 35.3 | 142.87 | 229.44 | 322.84 |
| P95 | 3.2 | 21.58 | 35.73 | 143.47 | 229.93 | 323.26 |
| P99 | 3.21 | 21.78 | 35.76 | 143.53 | 229.97 | 323.29 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 69.49 | 127.0 | 220.75 | 730.54 | 1155.91 | 1634.83 |
| P95 | 70.86 | 127.23 | 224.57 | 731.11 | 1159.52 | 1635.18 |
| P99 | 70.98 | 127.25 | 224.91 | 731.16 | 1159.84 | 1635.21 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 128.96 | 221.24 | 300.11 | 915.09 | 1417.58 | 1977.65 |
| P95 | 151.39 | 222.91 | 328.28 | 928.9 | 1421.0 | 1981.72 |
| P99 | 153.39 | 223.06 | 330.78 | 930.13 | 1421.3 | 1982.08 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 32.53 | 78.94 | 122.77 | 444.71 | 692.41 | 980.91 |
| P95 | 32.53 | 78.94 | 122.77 | 444.71 | 692.41 | 980.91 |
| P99 | 32.53 | 78.94 | 122.77 | 444.71 | 692.41 | 980.91 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 48.6 | 98.16 | 154.43 | 587.24 | 921.76 | 1315.36 |
| P95 | 51.26 | 102.1 | 154.91 | 589.03 | 922.3 | 1326.25 |
| P99 | 51.5 | 102.45 | 154.96 | 589.19 | 922.34 | 1327.22 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 46.66 | 97.58 | 172.85 | 586.9 | 932.76 | 1311.64 |
| P95 | 52.42 | 99.25 | 191.32 | 587.23 | 937.39 | 1313.43 |
| P99 | 52.94 | 99.4 | 192.96 | 587.26 | 937.8 | 1313.59 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 36.08 | 90.97 | 152.85 | 584.26 | 929.04 | 1313.95 |
| P95 | 36.86 | 91.07 | 156.22 | 584.78 | 931.26 | 1315.3 |
| P99 | 36.93 | 91.08 | 156.52 | 584.83 | 931.46 | 1315.42 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 48.36 | 92.92 | 147.2 | 581.86 | 920.52 | 1303.46 |
| P95 | 52.08 | 98.11 | 147.91 | 583.21 | 921.91 | 1304.28 |
| P99 | 52.41 | 98.58 | 147.97 | 583.33 | 922.04 | 1304.35 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 21.49 | 68.48 | 115.03 | 440.83 | 690.9 | 979.28 |
| P95 | 22.14 | 69.59 | 118.6 | 442.42 | 691.58 | 984.16 |
| P99 | 22.2 | 69.69 | 118.92 | 442.56 | 691.64 | 984.6 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 50.99 | 79.34 | 151.54 | 575.12 | 916.84 | 1297.28 |
| P95 | 53.81 | 85.76 | 160.71 | 576.22 | 918.64 | 1297.64 |
| P99 | 54.06 | 86.33 | 161.52 | 576.32 | 918.8 | 1297.67 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 64.81 | 165.34 | 256.43 | 881.95 | 1394.67 | 1962.08 |
| P95 | 106.52 | 455.51 | 436.48 | 1351.69 | 2095.74 | 2995.04 |
| P99 | 106.55 | 482.12 | 442.32 | 1355.54 | 2095.87 | 3001.58 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

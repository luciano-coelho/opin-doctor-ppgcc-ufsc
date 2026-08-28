# Experiment 3 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py in hybrid mode (direct AS/RS traffic, no Conformance Suite -- CRYPTO_PROFILE=classic|pqc originally justified in thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8; the hybrid profile and everything specific to it -- Strong Nesting response signing, hybrid JWKS, hybrid mTLS certificates -- is documented in thesis/results/v4/DECISIONS.md, see in particular Decision 2 (Strong Nesting signing architecture) and Decision 6 (hybrid mTLS certificates, the dual nested combiner)).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 254900 | 28 | 26 | 7324.81 |
| 14ms | 254900 | 28 | 26 | 7324.81 |
| 30ms | 254900 | 28 | 26 | 7324.81 |
| 140ms | 254900 | 28 | 26 | 7324.81 |
| 225ms | 254900 | 28 | 26 | 7324.81 |
| 320ms | 254900 | 28 | 26 | 7324.81 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 30 | 44.0 | 134.18 | 200.2 |
| 14ms | 38 | 56.33 | 68.0 | 65.53 | 223.55 |
| 30ms | 38 | 92.67 | 100.0 | 97.58 | 324.25 |
| 140ms | 38 | 301.33 | 309.0 | 344.58 | 1186.0 |
| 225ms | 38 | 467.67 | 471.75 | 549.08 | 1868.6 |
| 320ms | 38 | 657.17 | 665.25 | 770 | 2608.5 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 14ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 30ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 140ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 225ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |
| 320ms | 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 90433 | 90433 | 90433 | 90433 | 90433 | 90433 |
| Client (opin_flow.py, total traffic) | 254900 | 254900 | 254900 | 254900 | 254900 | 254900 |
| PKI/CRL | 38432 | 38432 | 38432 | 38432 | 38432 | 38432 |
| RS | 126035 | 126035 | 126035 | 126035 | 126035 | 126035 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 3.02 | 17.34 | 33.46 | 143.67 | 229.55 | 323.78 |
| P95 | 3.15 | 18.28 | 33.53 | 143.75 | 230.37 | 324.31 |
| P99 | 3.16 | 18.36 | 33.53 | 143.76 | 230.45 | 324.36 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 35.55 | 110.38 | 196.95 | 729.87 | 1263.48 | 1784.55 |
| P95 | 41.31 | 113.02 | 199.26 | 735.42 | 1363.93 | 1929.99 |
| P99 | 41.82 | 113.25 | 199.47 | 735.91 | 1372.86 | 1942.92 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 1477.34 | 193.99 | 275.04 | 902.15 | 1403.55 | 2001.68 |
| P95 | 2674.85 | 199.36 | 281.38 | 905.17 | 1404.52 | 2013.97 |
| P99 | 2781.29 | 199.84 | 281.94 | 905.44 | 1404.61 | 2015.07 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 55.42 | 81.75 | 140.23 | 439.3 | 697.94 | 984.33 |
| P95 | 55.42 | 81.75 | 140.23 | 439.3 | 697.94 | 984.33 |
| P99 | 55.42 | 81.75 | 140.23 | 439.3 | 697.94 | 984.33 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 106.07 | 91.8 | 152.73 | 588.91 | 927.71 | 1306.86 |
| P95 | 157.35 | 92.37 | 153.53 | 591.53 | 931.24 | 1307.67 |
| P99 | 161.91 | 92.42 | 153.6 | 591.76 | 931.55 | 1307.74 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 75.04 | 96.18 | 158.08 | 587.1 | 942.34 | 1308.46 |
| P95 | 89.29 | 96.61 | 158.85 | 589.42 | 950.48 | 1310.6 |
| P99 | 90.55 | 96.65 | 158.92 | 589.62 | 951.2 | 1310.79 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 70.31 | 90.1 | 158.56 | 581.23 | 923.15 | 1302.37 |
| P95 | 76.65 | 90.37 | 159.95 | 581.46 | 926.41 | 1303.51 |
| P99 | 77.22 | 90.4 | 160.07 | 581.48 | 926.7 | 1303.61 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 66.37 | 93.46 | 154.68 | 586.72 | 926.65 | 1303.23 |
| P95 | 74.81 | 95.01 | 159.79 | 588.99 | 927.24 | 1305.25 |
| P99 | 75.56 | 95.15 | 160.25 | 589.19 | 927.29 | 1305.43 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 36.23 | 71.74 | 117.48 | 441.06 | 696.66 | 979.49 |
| P95 | 39.63 | 73.66 | 121.08 | 443.12 | 703.22 | 982.77 |
| P99 | 39.93 | 73.83 | 121.41 | 443.3 | 703.8 | 983.07 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 26.1 | 75.37 | 135.27 | 579.71 | 913.2 | 1298.28 |
| P95 | 40.8 | 78.0 | 137.47 | 583.71 | 914.21 | 1300.38 |
| P99 | 42.11 | 78.23 | 137.67 | 584.07 | 914.3 | 1300.57 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 106.77 | 149.79 | 235.72 | 883.12 | 1392.51 | 1951.94 |
| P95 | 140.02 | 239.78 | 369.83 | 1348.1 | 2102.69 | 2939.82 |
| P99 | 141.25 | 240.76 | 371.58 | 1350.92 | 2103.39 | 2941.21 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

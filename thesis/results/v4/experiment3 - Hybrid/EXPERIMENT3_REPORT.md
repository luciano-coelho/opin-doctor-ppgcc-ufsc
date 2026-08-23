# Experiment 3 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py in hybrid mode (direct AS/RS traffic, no Conformance Suite -- CRYPTO_PROFILE=classic|pqc originally justified in thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8; the hybrid profile and everything specific to it -- Strong Nesting response signing, hybrid JWKS, hybrid mTLS certificates -- is documented in thesis/results/v4/DECISIONS.md, see in particular Decision 2 (Strong Nesting signing architecture) and Decision 6 (hybrid mTLS certificates, the dual nested combiner)).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 144186 | 28 | 26 | 4123.88 |
| 14ms | 144186 | 28 | 26 | 4123.88 |
| 30ms | 144190 | 28 | 26 | 4123.88 |
| 140ms | 144188 | 28 | 26 | 4123.88 |
| 225ms | 144188 | 28 | 26 | 4123.88 |
| 320ms | 144192 | 28 | 26 | 4123.88 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 19.67 | 28.5 | 110.39 | 144.5 |
| 14ms | 38 | 43.5 | 48.5 | 120.05 | 235.15 |
| 30ms | 38 | 83.5 | 94.25 | 191.66 | 573.15 |
| 140ms | 38 | 295.67 | 299.75 | 396.66 | 1361.8 |
| 225ms | 38 | 470.83 | 477.5 | 579.61 | 1926.7 |
| 320ms | 38 | 658.5 | 661.5 | 814.82 | 2709.75 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |
| 14ms | 6 | 25036.67 | 24991.0 | 25188.0 | 25188.0 |
| 30ms | 6 | 25109.33 | 24991.0 | 25515.0 | 25602.2 |
| 140ms | 6 | 25109.33 | 24991.0 | 25515.0 | 25602.2 |
| 225ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |
| 320ms | 6 | 25109.33 | 24991.0 | 25515.0 | 25602.2 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 31247 | 31247 | 31247 | 31247 | 31247 | 31247 |
| Client (opin_flow.py, total traffic) | 144186 | 144186 | 144190 | 144188 | 144188 | 144192 |
| PKI/CRL | 10704 | 10704 | 10708 | 10706 | 10706 | 10710 |
| RS | 102235 | 102235 | 102235 | 102235 | 102235 | 102235 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 303.73 | 304.13 | 310.64 | 303.15 | 304.32 | 315.59 |
| P95 | 557.63 | 552.35 | 564.25 | 554.0 | 555.15 | 569.14 |
| P99 | 580.2 | 574.41 | 586.79 | 576.3 | 577.45 | 591.68 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 77.59 | 125.12 | 232.03 | 945.28 | 1505.31 | 2113.93 |
| P95 | 99.86 | 149.07 | 276.29 | 1144.43 | 1810.45 | 2550.85 |
| P99 | 101.84 | 151.19 | 280.22 | 1162.13 | 1837.57 | 2589.69 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 1315.42 | 1073.24 | 1613.67 | 1869.0 | 2325.89 | 3336.27 |
| P95 | 2423.24 | 1880.87 | 2835.71 | 2727.06 | 3121.85 | 4556.53 |
| P99 | 2521.71 | 1952.66 | 2944.34 | 2803.34 | 3192.6 | 4665.0 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 22.26 | 70.41 | 120.35 | 442.39 | 716.17 | 996.77 |
| P95 | 22.26 | 70.41 | 120.35 | 442.39 | 716.17 | 996.77 |
| P99 | 22.26 | 70.41 | 120.35 | 442.39 | 716.17 | 996.77 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 97.77 | 134.45 | 201.4 | 623.53 | 970.42 | 1342.74 |
| P95 | 143.49 | 173.58 | 246.39 | 652.64 | 1002.98 | 1371.76 |
| P99 | 147.55 | 177.06 | 250.39 | 655.23 | 1005.88 | 1374.34 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 64.43 | 106.29 | 168.13 | 600.34 | 933.71 | 1332.0 |
| P95 | 72.71 | 114.63 | 170.33 | 608.53 | 938.02 | 1347.06 |
| P99 | 73.45 | 115.37 | 170.53 | 609.26 | 938.4 | 1348.4 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 47.61 | 101.49 | 163.85 | 596.22 | 937.34 | 1322.33 |
| P95 | 52.3 | 104.92 | 171.16 | 600.1 | 941.43 | 1328.99 |
| P99 | 52.72 | 105.23 | 171.81 | 600.44 | 941.8 | 1329.59 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 56.4 | 105.14 | 164.62 | 618.02 | 946.32 | 1321.84 |
| P95 | 62.76 | 113.75 | 176.16 | 631.24 | 947.84 | 1332.01 |
| P99 | 63.33 | 114.52 | 177.19 | 632.41 | 947.97 | 1332.92 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 21.02 | 46.25 | 81.04 | 293.19 | 466.56 | 654.39 |
| P95 | 29.09 | 51.11 | 88.16 | 295.86 | 470.25 | 658.16 |
| P99 | 29.81 | 51.54 | 88.79 | 296.1 | 470.58 | 658.49 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 411.41 | 417.98 | 546.74 | 441.38 | 530.48 | 467.97 |
| P95 | 671.76 | 666.14 | 802.26 | 712.54 | 892.03 | 707.38 |
| P99 | 694.9 | 688.2 | 824.98 | 736.64 | 924.17 | 728.66 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 61.42 | 147.55 | 207.56 | 765.26 | 1187.31 | 1661.41 |
| P95 | 111.06 | 231.64 | 311.42 | 1199.13 | 1876.98 | 2665.24 |
| P99 | 117.14 | 232.04 | 311.95 | 1199.62 | 1877.55 | 2670.25 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

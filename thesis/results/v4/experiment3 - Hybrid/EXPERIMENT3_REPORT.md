# Experiment 3 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py in hybrid mode (direct AS/RS traffic, no Conformance Suite -- CRYPTO_PROFILE=classic|pqc originally justified in thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8; the hybrid profile and everything specific to it -- Strong Nesting response signing, hybrid JWKS, hybrid mTLS certificates -- is documented in thesis/results/v4/DECISIONS.md, see in particular Decision 2 (Strong Nesting signing architecture) and Decision 6 (hybrid mTLS certificates, the dual nested combiner)).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 191250 | 28 | 26 | 5933.96 |
| 14ms | 191251 | 28 | 26 | 5933.96 |
| 30ms | 191256 | 28 | 26 | 5933.96 |
| 140ms | 191252 | 28 | 26 | 5933.96 |
| 225ms | 191252 | 28 | 26 | 5933.96 |
| 320ms | 191252 | 28 | 26 | 5933.96 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 27.17 | 39.5 | 113.63 | 270.85 |
| 14ms | 38 | 58 | 67.25 | 130.53 | 273.95 |
| 30ms | 38 | 98 | 112.5 | 224.61 | 489.75 |
| 140ms | 38 | 323 | 339.75 | 520.13 | 1606.8 |
| 225ms | 38 | 481.33 | 505.25 | 652.16 | 2082.7 |
| 320ms | 38 | 675.67 | 686.25 | 883.32 | 2796.0 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 25103.5 | 24991.0 | 25488.75 | 25568.95 |
| 14ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |
| 30ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |
| 140ms | 6 | 25103.5 | 24991.0 | 25488.75 | 25568.95 |
| 225ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |
| 320ms | 6 | 25103.5 | 24991.0 | 25488.75 | 25568.95 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 78311 | 78311 | 78311 | 78311 | 78311 | 78311 |
| Client (opin_flow.py, total traffic) | 191250 | 191251 | 191256 | 191252 | 191252 | 191252 |
| PKI/CRL | 10704 | 10705 | 10710 | 10706 | 10706 | 10706 |
| RS | 102235 | 102235 | 102235 | 102235 | 102235 | 102235 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 289.18 | 315.49 | 322.98 | 257.91 | 305.6 | 306.12 |
| P95 | 423.46 | 575.05 | 579.73 | 372.3 | 554.68 | 559.85 |
| P99 | 435.4 | 598.12 | 602.55 | 382.47 | 576.82 | 582.4 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 64.31 | 147.03 | 251.59 | 989.0 | 1516.5 | 2144.49 |
| P95 | 72.15 | 148.06 | 278.81 | 1197.75 | 1851.5 | 2600.21 |
| P99 | 72.85 | 148.15 | 281.23 | 1216.31 | 1881.28 | 2640.72 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 964.55 | 1167.62 | 1819.29 | 3011.19 | 2715.4 | 3401.0 |
| P95 | 1654.88 | 1965.06 | 3101.61 | 4863.07 | 3842.46 | 4653.33 |
| P99 | 1716.24 | 2035.95 | 3215.59 | 5027.68 | 3942.64 | 4764.64 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 41.88 | 82.81 | 142.93 | 457.34 | 703.37 | 985.22 |
| P95 | 41.88 | 82.81 | 142.93 | 457.34 | 703.37 | 985.22 |
| P99 | 41.88 | 82.81 | 142.93 | 457.34 | 703.37 | 985.22 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 163.4 | 152.37 | 324.02 | 684.29 | 997.31 | 1427.14 |
| P95 | 237.0 | 194.12 | 403.05 | 747.34 | 1049.12 | 1519.2 |
| P99 | 243.54 | 197.83 | 410.08 | 752.94 | 1053.73 | 1527.38 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 77.25 | 111.24 | 216.36 | 628.91 | 959.58 | 1354.68 |
| P95 | 93.31 | 123.21 | 248.43 | 649.69 | 967.22 | 1371.83 |
| P99 | 94.74 | 124.27 | 251.28 | 651.54 | 967.9 | 1373.35 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 66.1 | 98.32 | 183.79 | 594.51 | 940.67 | 1333.51 |
| P95 | 69.58 | 104.49 | 191.03 | 599.25 | 950.44 | 1335.43 |
| P99 | 69.89 | 105.03 | 191.68 | 599.67 | 951.31 | 1335.6 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 61.74 | 101.58 | 227.52 | 596.47 | 936.56 | 1319.41 |
| P95 | 75.06 | 109.82 | 240.05 | 602.17 | 945.57 | 1324.44 |
| P99 | 76.25 | 110.56 | 241.17 | 602.68 | 946.37 | 1324.88 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 34.01 | 77.86 | 138.29 | 461.89 | 709.2 | 987.92 |
| P95 | 43.02 | 90.41 | 155.88 | 474.74 | 715.48 | 993.73 |
| P99 | 43.82 | 91.52 | 157.44 | 475.89 | 716.03 | 994.24 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 654.38 | 529.54 | 600.49 | 614.04 | 447.32 | 477.0 |
| P95 | 807.3 | 840.9 | 870.21 | 754.54 | 704.68 | 765.09 |
| P99 | 820.89 | 868.58 | 894.19 | 767.03 | 727.56 | 790.7 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 115.02 | 182.35 | 318.16 | 1100.2 | 1438.27 | 2052.97 |
| P95 | 149.3 | 271.25 | 475.18 | 1618.18 | 2179.31 | 3054.52 |
| P99 | 150.92 | 272.95 | 484.01 | 1635.48 | 2188.0 | 3065.9 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

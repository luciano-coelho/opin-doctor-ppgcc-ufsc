# Experiment 3 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py in hybrid mode (direct AS/RS traffic, no Conformance Suite -- CRYPTO_PROFILE=classic|pqc originally justified in thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8; the hybrid profile and everything specific to it -- Strong Nesting response signing, hybrid JWKS, hybrid mTLS certificates -- is documented in thesis/results/v4/DECISIONS.md, see in particular Decision 2 (Strong Nesting signing architecture) and Decision 6 (hybrid mTLS certificates, the dual nested combiner)).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 179486 | 28 | 26 | 5481.42 |
| 14ms | 179486 | 28 | 26 | 5481.42 |
| 30ms | 179486 | 28 | 26 | 5481.42 |
| 140ms | 179486 | 28 | 26 | 5481.42 |
| 225ms | 179486 | 28 | 26 | 5481.42 |
| 320ms | 179486 | 28 | 26 | 5481.42 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 38 | 48.0 | 162.58 | 397.85 |
| 14ms | 38 | 63.67 | 76.0 | 154.11 | 303.65 |
| 30ms | 38 | 88.17 | 104.25 | 159.32 | 405.3 |
| 140ms | 38 | 301.83 | 305.75 | 413 | 1292.2 |
| 225ms | 38 | 474.83 | 484.75 | 620.39 | 1938.7 |
| 320ms | 38 | 660.83 | 666.5 | 844.16 | 2653.8 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |
| 14ms | 6 | 25103.5 | 24991.0 | 25488.75 | 25568.95 |
| 30ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |
| 140ms | 6 | 25103.5 | 24991.0 | 25488.75 | 25568.95 |
| 225ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |
| 320ms | 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 66545 | 66545 | 66545 | 66545 | 66545 | 66545 |
| Client (opin_flow.py, total traffic) | 179486 | 179486 | 179486 | 179486 | 179486 | 179486 |
| PKI/CRL | 10706 | 10706 | 10706 | 10706 | 10706 | 10706 |
| RS | 102235 | 102235 | 102235 | 102235 | 102235 | 102235 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 305.65 | 300.59 | 303.79 | 303.88 | 308.79 | 311.2 |
| P95 | 558.05 | 551.45 | 553.49 | 555.94 | 563.45 | 564.85 |
| P99 | 580.48 | 573.75 | 575.69 | 578.34 | 586.09 | 587.39 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 86.3 | 154.53 | 230.15 | 946.2 | 1503.44 | 2118.5 |
| P95 | 92.03 | 168.5 | 273.19 | 1134.0 | 1810.44 | 2550.88 |
| P99 | 92.53 | 169.74 | 277.01 | 1150.7 | 1837.73 | 2589.31 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 1413.68 | 1503.56 | 1131.54 | 1711.59 | 2383.14 | 2909.04 |
| P95 | 2477.37 | 2620.44 | 1869.42 | 2431.34 | 3247.41 | 3741.78 |
| P99 | 2571.93 | 2719.71 | 1935.01 | 2495.32 | 3324.23 | 3815.8 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 71.62 | 86.48 | 122.23 | 439.86 | 698.25 | 989.75 |
| P95 | 71.62 | 86.48 | 122.23 | 439.86 | 698.25 | 989.75 |
| P99 | 71.62 | 86.48 | 122.23 | 439.86 | 698.25 | 989.75 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 270.04 | 153.46 | 199.1 | 631.41 | 958.71 | 1372.26 |
| P95 | 406.83 | 188.71 | 232.59 | 643.59 | 985.8 | 1423.69 |
| P99 | 418.99 | 191.85 | 235.56 | 644.68 | 988.2 | 1428.26 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 109.61 | 137.45 | 165.49 | 608.48 | 942.45 | 1325.56 |
| P95 | 119.3 | 143.55 | 177.51 | 619.78 | 947.85 | 1326.59 |
| P99 | 120.16 | 144.09 | 178.58 | 620.79 | 948.33 | 1326.68 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 90.55 | 118.7 | 161.24 | 594.14 | 937.51 | 1331.44 |
| P95 | 111.28 | 123.49 | 167.14 | 601.12 | 945.45 | 1334.18 |
| P99 | 113.12 | 123.91 | 167.66 | 601.74 | 946.15 | 1334.42 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 89.9 | 133.36 | 162.08 | 598.8 | 934.3 | 1335.93 |
| P95 | 111.31 | 140.64 | 167.81 | 605.22 | 939.27 | 1356.45 |
| P99 | 113.21 | 141.29 | 168.32 | 605.79 | 939.71 | 1358.27 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 49.87 | 77.18 | 126.74 | 445.92 | 720.07 | 979.74 |
| P95 | 65.88 | 86.44 | 131.37 | 452.59 | 736.52 | 984.44 |
| P99 | 67.3 | 87.27 | 131.78 | 453.19 | 737.98 | 984.86 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 2840.51 | 547.35 | 1000.66 | 2824.61 | 433.4 | 439.54 |
| P95 | 5245.15 | 919.05 | 1267.05 | 5210.58 | 698.91 | 698.21 |
| P99 | 5458.9 | 952.09 | 1290.73 | 5422.67 | 722.51 | 721.2 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 153.73 | 197.63 | 281.79 | 971.58 | 1425.5 | 1992.08 |
| P95 | 273.55 | 301.11 | 380.83 | 1351.86 | 2113.68 | 2985.94 |
| P99 | 283.08 | 308.85 | 383.63 | 1353.49 | 2114.41 | 2987.97 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

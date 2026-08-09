# Experiment 1 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 67584 | 28 | 26 | 1385.42 |
| 14ms | 67584 | 28 | 26 | 1385.42 |
| 30ms | 67590 | 28 | 26 | 1385.42 |
| 140ms | 67586 | 28 | 26 | 1385.42 |
| 225ms | 67586 | 28 | 26 | 1385.42 |
| 320ms | 67586 | 28 | 26 | 1385.42 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 54 | 33.25 | 47.65 | 23.78 | 88.4 |
| 14ms | 56 | 51.57 | 69.2 | 63.59 | 226.5 |
| 30ms | 58 | 93 | 127.0 | 100.24 | 302.6 |
| 140ms | 58 | 242.33 | 333.6 | 386.03 | 1101.15 |
| 225ms | 58 | 358.11 | 500.2 | 631.71 | 1910.55 |
| 320ms | 58 | 487.44 | 707.2 | 855.26 | 2382.55 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 10 | 10264.7 | 10398.5 | 10818.5 | 10894.1 |
| 14ms | 10 | 10256.2 | 10398.5 | 10751.75 | 10825.55 |
| 30ms | 11 | 10330.09 | 10416.0 | 10921.5 | 11096.3 |
| 140ms | 10 | 10236.3 | 10398.5 | 10671.45 | 10692.69 |
| 225ms | 10 | 10236.3 | 10398.5 | 10671.45 | 10692.69 |
| 320ms | 10 | 10236.3 | 10398.5 | 10671.45 | 10692.69 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 26063 | 26063 | 26063 | 26063 | 26063 | 26063 |
| Client (opin_flow.py, total traffic) | 67584 | 67584 | 67590 | 67586 | 67586 | 67586 |
| PKI/CRL | 10664 | 10664 | 10670 | 10666 | 10666 | 10666 |
| RS | 30857 | 30857 | 30857 | 30857 | 30857 | 30857 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 308.13 | 301.93 | 30.16 | 303.78 | 304.73 | 308.25 |
| P95 | 554.54 | 551.26 | 37.27 | 555.04 | 554.12 | 561.2 |
| P99 | 576.44 | 573.42 | 37.9 | 577.38 | 576.29 | 583.68 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 107.42 | 122.92 | 209.01 | 754.81 | 1288.96 | 1833.19 |
| P95 | 173.05 | 133.92 | 233.44 | 768.32 | 1398.13 | 2001.94 |
| P99 | 178.88 | 134.9 | 235.61 | 769.53 | 1407.83 | 2016.94 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 92.3 | 182.56 | 270.99 | 950.59 | 1483.13 | 2017.55 |
| P95 | 99.96 | 199.98 | 280.65 | 958.12 | 1484.89 | 2019.95 |
| P99 | 100.64 | 201.52 | 281.51 | 958.79 | 1485.05 | 2020.16 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 24.66 | 86.84 | 134.06 | 452.14 | 701.51 | 990.82 |
| P95 | 24.66 | 86.84 | 134.06 | 452.14 | 701.51 | 990.82 |
| P99 | 24.66 | 86.84 | 134.06 | 452.14 | 701.51 | 990.82 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 22.19 | 109.39 | 158.89 | 608.76 | 952.63 | 1360.76 |
| P95 | 23.73 | 109.75 | 166.33 | 615.36 | 958.8 | 1383.63 |
| P99 | 23.87 | 109.78 | 166.99 | 615.94 | 959.35 | 1385.66 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 23.85 | 101.18 | 160.82 | 617.43 | 971.26 | 1341.19 |
| P95 | 24.43 | 105.14 | 163.43 | 618.77 | 981.2 | 1353.36 |
| P99 | 24.48 | 105.49 | 163.67 | 618.89 | 982.08 | 1354.45 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 24.1 | 118.86 | 158.31 | 607.68 | 932.57 | 1318.4 |
| P95 | 24.64 | 134.45 | 160.86 | 617.71 | 933.03 | 1323.64 |
| P99 | 24.68 | 135.84 | 161.09 | 618.6 | 933.07 | 1324.1 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 24.12 | 96.97 | 166.15 | 617.73 | 962.94 | 1317.81 |
| P95 | 26.96 | 103.07 | 167.06 | 621.33 | 967.4 | 1324.58 |
| P99 | 27.21 | 103.61 | 167.14 | 621.65 | 967.8 | 1325.18 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 15.56 | 49.15 | 78.13 | 305.25 | 471.98 | 662.09 |
| P95 | 17.44 | 56.84 | 81.83 | 307.57 | 474.16 | 664.97 |
| P99 | 17.61 | 57.53 | 82.16 | 307.78 | 474.35 | 665.23 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 380.25 | 449.51 | 2412.5 | 1533.25 | 432.34 | 517.73 |
| P95 | 644.15 | 749.82 | 4466.0 | 2285.89 | 644.46 | 652.05 |
| P99 | 667.6 | 776.51 | 4648.53 | 2352.79 | 663.32 | 663.99 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 70.71 | 115.4 | 192.14 | 750.11 | 1179.5 | 1653.64 |
| P95 | 134.43 | 203.94 | 315.53 | 1211.7 | 2102.22 | 2671.52 |
| P99 | 141.77 | 206.28 | 317.24 | 1212.88 | 2132.87 | 2674.71 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

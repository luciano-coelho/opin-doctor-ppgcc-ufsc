# Experiment 2 Report -- opin_flow.py vs. Latency

Comparative report across the six WAN-latency scenarios (0/14/30/140/225/320ms, see thesis/scripts/set_latency.sh) run with thesis/scripts/opin_flow.py (direct AS/RS traffic, no Conformance Suite -- see thesis/results/experiment2 - PQC/DECISIONS.md, Decisions 6-8, for why).

## Total OPINsize and request count

| Latency | Total bytes exchanged | Total requests | JWTs found | Avg JWT size (bytes) |
|---|---|---|---|---|
| 0ms | 112791 | 28 | 26 | 2950.5 |
| 14ms | 178009 | 28 | 26 | 5458.81 |
| 30ms | 112797 | 28 | 26 | 2950.5 |
| 140ms | 112793 | 28 | 26 | 2950.5 |
| 225ms | 112793 | 28 | 26 | 2950.5 |
| 320ms | 112793 | 28 | 26 | 2950.5 |

## mTLS handshake vs. OPIN processing time (gateway-side)

| Latency | Requests logged | Handshake mean (ms) | Handshake P95 (ms) | OPIN proc. mean (ms) | OPIN proc. P95 (ms) |
|---|---|---|---|---|---|
| 0ms | 38 | 25.5 | 39.0 | 35.42 | 115.05 |
| 14ms | 38 | 46 | 55.0 | 53.66 | 169.15 |
| 30ms | 38 | 76.67 | 82.25 | 95.05 | 315.75 |
| 140ms | 38 | 313.5 | 336.5 | 346.71 | 1086.6 |
| 225ms | 38 | 501.33 | 568.0 | 534.08 | 1839.15 |
| 320ms | 38 | 682.5 | 724.75 | 770.97 | 2368.7 |

## mTLS handshake size (wire bytes, gateway-side)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished) -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to move most under PQC (larger KEM public keys/ciphertexts and signatures); it should be flat across latency scenarios here since this baseline doesn't change algorithms between them. Samples are deduplicated per physical TCP connection before P50/P95/P99 are computed (baseline_automation.py's dedupe_handshake_samples_by_connection) -- opin_flow.py reuses connections within a flow, so a naive one-sample-per-request count would over-weight whichever connection happened to carry the most requests.

| Latency | Connections (samples) | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|---|
| 0ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |
| 14ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |
| 30ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |
| 140ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |
| 225ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |
| 320ms | 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |

## Bytes by participant

**Client** is opin_flow.py itself -- it is one of the two parties on every logged call, so its row always equals that scenario's total bytes exchanged (see the first table) by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown of who the client was talking to on each call, and they sum to that same total.

| Participant | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| AS | 71270 | 71270 | 71270 | 71270 | 71270 | 71270 |
| Client (opin_flow.py, total traffic) | 112791 | 178009 | 112797 | 112793 | 112793 | 112793 |
| PKI/CRL | 10664 | 10664 | 10670 | 10666 | 10666 | 10666 |
| RS | 30857 | 96075 | 30857 | 30857 | 30857 | 30857 |

(Total bytes -- sent + received -- per participant, per scenario.)

## Latency per endpoint (client-side, P50/P95/P99 in ms)

Endpoint paths are normalized (consent URNs and UUIDs collapsed to `{id}`) so the same logical endpoint can be compared across scenarios.

### `/issuer-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 308.32 | 317.37 | 23.21 | 305.31 | 301.65 | 314.86 |
| P95 | 563.98 | 581.27 | 23.85 | 556.1 | 551.34 | 574.43 |
| P99 | 586.7 | 604.73 | 23.91 | 578.39 | 573.53 | 597.5 |

### `/jwks`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 88.62 | 107.7 | 194.07 | 844.98 | 1303.69 | 1843.21 |
| P95 | 113.21 | 115.47 | 215.17 | 923.78 | 1428.28 | 2016.28 |
| P99 | 115.4 | 116.17 | 217.04 | 930.78 | 1439.36 | 2031.66 |

### `/open-insurance/consents/v3/consents`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 153.31 | 156.98 | 244.96 | 925.73 | 1490.47 | 2186.23 |
| P95 | 188.09 | 160.58 | 247.12 | 935.69 | 1528.3 | 2330.63 |
| P99 | 191.18 | 160.9 | 247.32 | 936.57 | 1531.67 | 2343.47 |

### `/open-insurance/consents/v3/consents/{id}`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 45.36 | 65.2 | 116.25 | 454.99 | 700.13 | 995.91 |
| P95 | 45.36 | 65.2 | 116.25 | 454.99 | 700.13 | 995.91 |
| P99 | 45.36 | 65.2 | 116.25 | 454.99 | 700.13 | 995.91 |

### `/open-insurance/insurance-person/v2/insurance-person`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 44.48 | 85.63 | 158.84 | 652.84 | 949.36 | 1317.16 |
| P95 | 47.3 | 90.14 | 159.61 | 668.51 | 957.85 | 1319.19 |
| P99 | 47.55 | 90.54 | 159.68 | 669.9 | 958.6 | 1319.37 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/claim`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 31.94 | 84.44 | 155.87 | 644.45 | 953.48 | 1335.77 |
| P95 | 36.02 | 85.71 | 158.35 | 653.81 | 965.45 | 1337.86 |
| P99 | 36.38 | 85.83 | 158.58 | 654.64 | 966.52 | 1338.04 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/policy-info`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 30.66 | 81.48 | 163.73 | 605.58 | 942.02 | 1322.02 |
| P95 | 31.28 | 82.16 | 173.49 | 608.16 | 944.99 | 1324.26 |
| P99 | 31.34 | 82.22 | 174.35 | 608.39 | 945.25 | 1324.46 |

### `/open-insurance/insurance-person/v2/insurance-person/{id}/premium`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 34.02 | 77.73 | 151.85 | 598.29 | 936.99 | 1320.4 |
| P95 | 35.65 | 78.95 | 151.93 | 599.82 | 937.47 | 1321.03 |
| P99 | 35.8 | 79.06 | 151.93 | 599.96 | 937.51 | 1321.08 |

### `/request`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 34.93 | 64.04 | 118.81 | 448.44 | 709.6 | 982.16 |
| P95 | 39.28 | 66.93 | 118.96 | 451.97 | 718.5 | 985.94 |
| P99 | 39.67 | 67.18 | 118.98 | 452.28 | 719.29 | 986.27 |

### `/root-ca.pem`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 538.0 | 475.07 | 121.67 | 631.39 | 441.84 | 398.81 |
| P95 | 907.27 | 811.0 | 137.1 | 868.6 | 695.59 | 666.73 |
| P99 | 940.1 | 840.86 | 138.47 | 889.69 | 718.15 | 690.54 |

### `/token`

| Metric | 0ms | 14ms | 30ms | 140ms | 225ms | 320ms |
|---|---|---|---|---|---|---|
| P50 | 122.1 | 115.99 | 218.19 | 753.95 | 1182.44 | 1663.39 |
| P95 | 166.66 | 203.9 | 423.32 | 1212.0 | 1882.97 | 2648.02 |
| P99 | 172.45 | 206.41 | 433.93 | 1215.21 | 1883.96 | 2649.35 |

## Methodological notes

- **Connection reuse by design**: opin_flow.py's do_call() shares one requests.Session per flow (see its docstring), so unlike Experiment 1's Conformance Suite runs, most requests within a flow reuse the same TCP+TLS connection deliberately, not incidentally. The mTLS handshake cost is still counted once per physical connection (mock-service-os/mock_mtls/main.go), and compute_metrics() deduplicates by connection before computing handshake percentiles (see the note on the handshake-size table above) -- without that dedup, connection reuse would silently skew the percentiles toward whichever connection carried the most requests.
- **Outliers filtered**: mTLS handshake samples were dropped when more than 3x the scenario's median handshake time (`filter_handshake_outliers` in baseline_automation.py), applied iteratively, after the per-connection dedup above. Per-scenario counts of dropped samples are in `gateway_metrics.handshake_outliers_dropped` in each scenario's baseline_metrics.json.
- **PAR request_uri TTL at high injected latency**: oidc-provider's default 60s TTL for pushed authorization request_uris (not overridden in mock_as/utils/opin/configuration.js) is tight relative to the 225ms/320ms scenarios once round-trip cost compounds across the calls between PAR and login completion -- those two scenarios occasionally needed a retry (invalid_request_uri: expired) during data collection. This is an artifact of the measurement environment's security TTL, not a cryptography- or latency-*algorithm* finding; the data in this report is from the run that completed successfully for each scenario.

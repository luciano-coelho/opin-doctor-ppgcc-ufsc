# Baseline Report (Classical Cryptography)

Generated at: 2026-08-28T18:26:34.572507+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **254900 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **7324.81 bytes** (max: 9093 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 229.55 | 229.55 | 230.37 | 230.45 |
| `/jwks` | 2 | 1263.48 | 1263.48 | 1363.93 | 1372.86 |
| `/open-insurance/consents/v3/consents` | 2 | 1403.55 | 1403.55 | 1404.52 | 1404.61 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:34b2b9b8-3715-470c-92be-b683f907a9d6` | 5 | 695.83 | 697.55 | 699.62 | 699.93 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:5656f1fc-8a69-4354-b00e-b55a028d484e` | 1 | 697.94 | 697.94 | 697.94 | 697.94 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 927.71 | 927.71 | 931.24 | 931.55 |
| `/open-insurance/insurance-person/v2/insurance-person/651d3e5d-f698-4e75-b0b9-425fcdc454a3/claim` | 2 | 942.34 | 942.34 | 950.48 | 951.2 |
| `/open-insurance/insurance-person/v2/insurance-person/651d3e5d-f698-4e75-b0b9-425fcdc454a3/policy-info` | 2 | 923.15 | 923.15 | 926.41 | 926.7 |
| `/open-insurance/insurance-person/v2/insurance-person/651d3e5d-f698-4e75-b0b9-425fcdc454a3/premium` | 2 | 926.65 | 926.65 | 927.24 | 927.29 |
| `/request` | 2 | 696.66 | 696.66 | 703.22 | 703.8 |
| `/root-ca.pem` | 2 | 913.2 | 913.2 | 914.21 | 914.3 |
| `/token` | 4 | 1393.64 | 1392.51 | 2102.69 | 2103.39 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 467.67 | 468.0 | 471.75 | 471.95 |
| OPIN processing | 38 | 549.08 | 240.5 | 1868.6 | 2740.77 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 31058 | 59375 | 90433 |
| Client (test tool, total traffic) | 64878 | 190022 | 254900 |
| PKI/CRL | 37768 | 664 | 38432 |
| RS | 121196 | 4839 | 126035 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 6912 |
| 2 | 7156 |
| 3 | 7156 |
| 4 | 7156 |
| 5 | 7156 |
| 6 | 7492 |
| 7 | 6915 |
| 8 | 6912 |
| 9 | 7695 |
| 10 | 7140 |
| 11 | 7140 |
| 12 | 6912 |
| 13 | 7201 |
| 14 | 7201 |
| 15 | 7305 |
| 16 | 6915 |
| 17 | 6912 |
| 18 | 7695 |
| 19 | 6864 |
| 20 | 6864 |
| 21 | 7350 |
| 22 | 7350 |
| 23 | 9093 |
| 24 | 9093 |
| 25 | 7430 |
| 26 | 7430 |

# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T02:25:33.510941+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **184637 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5458.81 bytes** (max: 7246 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=pqc) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=pqc) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 231.59 | 231.59 | 232.0 | 232.04 |
| `/jwks` | 2 | 1268.01 | 1268.01 | 1368.95 | 1377.92 |
| `/open-insurance/consents/v3/consents` | 2 | 1447.97 | 1447.97 | 1450.39 | 1450.61 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:0d186631-1c9d-4fa8-8725-f51af71fb663` | 5 | 729.85 | 717.0 | 775.44 | 786.56 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f388ca62-bbbb-4a2e-ad99-5328a804fb78` | 1 | 704.63 | 704.63 | 704.63 | 704.63 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 971.0 | 971.0 | 972.13 | 972.23 |
| `/open-insurance/insurance-person/v2/insurance-person/10866a5e-74d9-4134-85d3-24b1ff63ea05/claim` | 2 | 955.99 | 955.99 | 963.08 | 963.71 |
| `/open-insurance/insurance-person/v2/insurance-person/10866a5e-74d9-4134-85d3-24b1ff63ea05/policy-info` | 2 | 967.68 | 967.68 | 971.72 | 972.07 |
| `/open-insurance/insurance-person/v2/insurance-person/10866a5e-74d9-4134-85d3-24b1ff63ea05/premium` | 2 | 957.8 | 957.8 | 964.62 | 965.23 |
| `/request` | 2 | 707.1 | 707.1 | 708.52 | 708.65 |
| `/root-ca.pem` | 2 | 967.58 | 967.58 | 983.52 | 984.94 |
| `/token` | 4 | 1198.19 | 1198.7 | 1923.42 | 1923.55 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 488 | 468.0 | 553.25 | 566.65 |
| OPIN processing | 38 | 541.03 | 253.5 | 1739.65 | 2755.65 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 137434 | 184637 |
| PKI/CRL | 16612 | 664 | 17276 |
| RS | 91252 | 4839 | 96091 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 4703 |
| 2 | 5284 |
| 3 | 5284 |
| 4 | 5284 |
| 5 | 5284 |
| 6 | 5283 |
| 7 | 4705 |
| 8 | 4703 |
| 9 | 7246 |
| 10 | 5268 |
| 11 | 5268 |
| 12 | 4703 |
| 13 | 5330 |
| 14 | 5330 |
| 15 | 5096 |
| 16 | 4705 |
| 17 | 4703 |
| 18 | 7246 |
| 19 | 4992 |
| 20 | 4992 |
| 21 | 5479 |
| 22 | 5479 |
| 23 | 7222 |
| 24 | 7222 |
| 25 | 5559 |
| 26 | 5559 |

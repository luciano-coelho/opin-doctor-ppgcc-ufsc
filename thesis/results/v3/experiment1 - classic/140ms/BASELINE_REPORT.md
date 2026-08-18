# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T03:30:47.121008+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67602 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **1385.42 bytes** (max: 3146 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=classic) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=classic) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 305.9 | 305.9 | 560.94 | 583.61 |
| `/jwks` | 2 | 839.58 | 839.58 | 888.83 | 893.21 |
| `/open-insurance/consents/v3/consents` | 2 | 975.69 | 975.69 | 980.36 | 980.78 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:4b60707d-a83b-464d-a963-df2fabaeb083` | 5 | 478.67 | 476.89 | 501.24 | 504.34 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e842edca-d631-4cf5-84c5-68f9afdf4a6a` | 1 | 452.2 | 452.2 | 452.2 | 452.2 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 629.27 | 629.27 | 640.03 | 640.99 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/claim` | 2 | 677.18 | 677.18 | 728.0 | 732.51 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/policy-info` | 2 | 637.94 | 637.94 | 641.09 | 641.37 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/premium` | 2 | 623.71 | 623.71 | 625.98 | 626.18 |
| `/request` | 2 | 347.88 | 347.88 | 371.88 | 374.01 |
| `/root-ca.pem` | 2 | 390.96 | 390.96 | 645.13 | 667.72 |
| `/token` | 4 | 772.57 | 773.56 | 1241.02 | 1242.36 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 328 | 323.0 | 349.25 | 350.65 |
| OPIN processing | 38 | 341.18 | 168.0 | 1105.85 | 1757.0 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 9969.5 | 9785.0 | 10407.25 | 10414.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11875 | 26063 |
| Client (test tool, total traffic) | 17378 | 50224 | 67602 |
| PKI/CRL | 10002 | 664 | 10666 |
| RS | 26034 | 4839 | 30873 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM | RSA | sig | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 3 | xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM | RSA | sig | 256 |
| 4 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 975 |
| 2 | 1208 |
| 3 | 1208 |
| 4 | 1208 |
| 5 | 1208 |
| 6 | 1555 |
| 7 | 977 |
| 8 | 975 |
| 9 | 1812 |
| 10 | 1192 |
| 11 | 1192 |
| 12 | 975 |
| 13 | 1254 |
| 14 | 1254 |
| 15 | 1368 |
| 16 | 977 |
| 17 | 975 |
| 18 | 1812 |
| 19 | 916 |
| 20 | 916 |
| 21 | 1403 |
| 22 | 1403 |
| 23 | 3146 |
| 24 | 3146 |
| 25 | 1483 |
| 26 | 1483 |

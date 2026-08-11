# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T02:07:36.153134+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67606 bytes**
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
| `/issuer-ca.pem` | 2 | 26.77 | 26.77 | 26.93 | 26.94 |
| `/jwks` | 2 | 39.64 | 39.64 | 44.75 | 45.2 |
| `/open-insurance/consents/v3/consents` | 2 | 54.47 | 54.47 | 55.47 | 55.56 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:2d14b555-f40d-42a8-bc76-e60425afdbb6` | 5 | 15.74 | 15.53 | 17.21 | 17.28 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:b98921ba-d0eb-4e56-949a-3512d4d59032` | 1 | 17.69 | 17.69 | 17.69 | 17.69 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 22.31 | 22.31 | 23.55 | 23.67 |
| `/open-insurance/insurance-person/v2/insurance-person/c742e705-57c4-4bdb-8c88-4afb2142cd5d/claim` | 2 | 28.88 | 28.88 | 33.62 | 34.04 |
| `/open-insurance/insurance-person/v2/insurance-person/c742e705-57c4-4bdb-8c88-4afb2142cd5d/policy-info` | 2 | 27.52 | 27.52 | 30.15 | 30.39 |
| `/open-insurance/insurance-person/v2/insurance-person/c742e705-57c4-4bdb-8c88-4afb2142cd5d/premium` | 2 | 30.87 | 30.87 | 33.98 | 34.25 |
| `/request` | 2 | 10.26 | 10.26 | 10.6 | 10.63 |
| `/root-ca.pem` | 2 | 169.24 | 169.24 | 217.97 | 222.3 |
| `/token` | 4 | 22.13 | 21.25 | 37.55 | 38.17 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 8 | 17 | 15.0 | 26.3 | 26.86 |
| OPIN processing | 58 | 15.26 | 9.0 | 48.0 | 62.01 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
2 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 10211.8 | 10198.0 | 10748.1 | 10777.62 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11875 | 26063 |
| Client (test tool, total traffic) | 17378 | 50228 | 67606 |
| PKI/CRL | 10006 | 664 | 10670 |
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

# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T14:55:47.397118+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67584 bytes**
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
| `/issuer-ca.pem` | 2 | 308.13 | 308.13 | 554.54 | 576.44 |
| `/jwks` | 2 | 107.42 | 107.42 | 173.05 | 178.88 |
| `/open-insurance/consents/v3/consents` | 2 | 92.3 | 92.3 | 99.96 | 100.64 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:d3ebd111-b467-40e0-acb3-3f13ae2d0d17` | 5 | 19.04 | 17.23 | 23.6 | 24.12 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f525a2d6-aa79-429f-8ade-0a544bfb2745` | 1 | 24.66 | 24.66 | 24.66 | 24.66 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 22.19 | 22.19 | 23.73 | 23.87 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/claim` | 2 | 23.85 | 23.85 | 24.43 | 24.48 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/policy-info` | 2 | 24.1 | 24.1 | 24.64 | 24.68 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/premium` | 2 | 24.12 | 24.12 | 26.96 | 27.21 |
| `/request` | 2 | 15.56 | 15.56 | 17.44 | 17.61 |
| `/root-ca.pem` | 2 | 380.25 | 380.25 | 644.15 | 667.6 |
| `/token` | 4 | 76.7 | 70.71 | 134.43 | 141.77 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **54**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 8 | 33.25 | 33.0 | 47.65 | 47.93 |
| OPIN processing | 54 | 23.78 | 11.5 | 88.4 | 115.15 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
2 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 10264.7 | 10398.5 | 10818.5 | 10894.1 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11875 | 26063 |
| Client (test tool, total traffic) | 17378 | 50206 | 67584 |
| PKI/CRL | 10000 | 664 | 10664 |
| RS | 26018 | 4839 | 30857 |

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

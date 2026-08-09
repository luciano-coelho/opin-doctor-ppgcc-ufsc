# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:36:57.600787+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67590 bytes**
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
| `/issuer-ca.pem` | 2 | 59.79 | 59.79 | 90.26 | 92.97 |
| `/jwks` | 2 | 199.45 | 199.45 | 213.53 | 214.78 |
| `/open-insurance/consents/v3/consents` | 2 | 241.45 | 241.45 | 246.56 | 247.01 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e2346d01-988a-428a-8261-3205d5b58d1b` | 1 | 109.23 | 109.23 | 109.23 | 109.23 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f8858284-9e55-440d-aa55-bf3f2c763498` | 5 | 109.72 | 108.06 | 112.68 | 112.7 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 146.26 | 146.26 | 148.5 | 148.7 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/claim` | 2 | 163.81 | 163.81 | 166.32 | 166.55 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/policy-info` | 2 | 149.29 | 149.29 | 150.1 | 150.17 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/premium` | 2 | 146.69 | 146.69 | 149.0 | 149.2 |
| `/request` | 2 | 74.05 | 74.05 | 75.55 | 75.68 |
| `/root-ca.pem` | 2 | 230.31 | 230.31 | 237.76 | 238.42 |
| `/token` | 4 | 188.55 | 179.69 | 318.39 | 322.79 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 9 | 75.89 | 78.0 | 100.4 | 101.68 |
| OPIN processing | 58 | 94.93 | 44.0 | 291.25 | 452.73 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 10225.8 | 10398.5 | 10723.45 | 10823.89 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11875 | 26063 |
| Client (test tool, total traffic) | 17378 | 50212 | 67590 |
| PKI/CRL | 10006 | 664 | 10670 |
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

# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T14:30:33.615031+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 301.93 | 301.93 | 551.26 | 573.42 |
| `/jwks` | 2 | 122.92 | 122.92 | 133.92 | 134.9 |
| `/open-insurance/consents/v3/consents` | 2 | 182.56 | 182.56 | 199.98 | 201.52 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:005ffce0-e629-460b-899c-c31439fabc73` | 5 | 93.05 | 84.06 | 113.43 | 115.67 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:eea3d5dd-ecaa-4945-bcc5-4c1b7b96d0fb` | 1 | 86.84 | 86.84 | 86.84 | 86.84 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 109.39 | 109.39 | 109.75 | 109.78 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/claim` | 2 | 101.18 | 101.18 | 105.14 | 105.49 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/policy-info` | 2 | 118.86 | 118.86 | 134.45 | 135.84 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/premium` | 2 | 96.97 | 96.97 | 103.07 | 103.61 |
| `/request` | 2 | 49.15 | 49.15 | 56.84 | 57.53 |
| `/root-ca.pem` | 2 | 449.51 | 449.51 | 749.82 | 776.51 |
| `/token` | 4 | 120.05 | 115.4 | 203.94 | 206.28 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **56**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 7 | 51.57 | 54.0 | 69.2 | 73.04 |
| OPIN processing | 56 | 63.59 | 37.0 | 226.5 | 279.95 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
3 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 10256.2 | 10398.5 | 10751.75 | 10825.55 |

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

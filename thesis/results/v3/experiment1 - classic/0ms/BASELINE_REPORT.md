# Baseline Report (Classical Cryptography)

Generated at: 2026-08-08T22:52:31.617617+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **55470 bytes**
- Total HTTP requests: **28**
- JWTs found: **18**
- Average JWT size: **1198.5 bytes** (max: 1812 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=classic) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | FAILED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=classic) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | FAILED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 426.26 | 426.26 | 708.8 | 733.92 |
| `/jwks` | 2 | 73.0 | 73.0 | 89.72 | 91.21 |
| `/open-insurance/consents/v3/consents` | 2 | 104.39 | 104.39 | 108.95 | 109.36 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:6d0f8533-296c-4286-b264-44068d2b3495` | 1 | 121.41 | 121.41 | 121.41 | 121.41 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:c6251c38-f983-4514-9a3b-d993ad09943d` | 5 | 79.67 | 73.72 | 110.9 | 111.26 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 108.31 | 108.31 | 114.82 | 115.39 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/claim` | 2 | 99.28 | 99.28 | 101.6 | 101.81 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/policy-info` | 2 | 99.62 | 99.62 | 100.65 | 100.74 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/premium` | 2 | 89.71 | 89.71 | 93.56 | 93.91 |
| `/request` | 2 | 84.64 | 84.64 | 107.64 | 109.68 |
| `/root-ca.pem` | 2 | 544.62 | 544.62 | 911.97 | 944.62 |
| `/token` | 4 | 93.26 | 100.04 | 130.9 | 132.55 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **64**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 61 | 17.3 | 18.0 | 30.0 | 34.4 |
| OPIN processing | 64 | 16.56 | 12.0 | 45.0 | 65.44 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
3 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 64 | 9889.89 | 9246.0 | 11495.0 | 12053.0 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11955 | 26143 |
| Client (test tool, total traffic) | 17658 | 37812 | 55470 |
| PKI/CRL | 10000 | 704 | 10704 |
| RS | 13624 | 4999 | 18623 |

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
| 10 | 975 |
| 11 | 1254 |
| 12 | 1254 |
| 13 | 1368 |
| 14 | 977 |
| 15 | 975 |
| 16 | 1812 |
| 17 | 916 |
| 18 | 916 |

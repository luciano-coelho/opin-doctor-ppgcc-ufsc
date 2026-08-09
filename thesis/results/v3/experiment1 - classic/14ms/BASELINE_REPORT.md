# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T00:23:04.242113+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67870 bytes**
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
| `/issuer-ca.pem` | 2 | 49.14 | 49.14 | 72.19 | 74.24 |
| `/jwks` | 2 | 132.21 | 132.21 | 142.81 | 143.75 |
| `/open-insurance/consents/v3/consents` | 2 | 182.18 | 182.18 | 229.62 | 233.84 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:59538861-3ce3-4415-9355-be7559c213e8` | 1 | 71.34 | 71.34 | 71.34 | 71.34 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f3e7d051-f187-474e-8e4b-04e33bc66fdc` | 5 | 59.51 | 59.16 | 65.51 | 66.25 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 76.22 | 76.22 | 76.9 | 76.96 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/claim` | 2 | 80.41 | 80.41 | 80.6 | 80.62 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/policy-info` | 2 | 79.86 | 79.86 | 81.15 | 81.26 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/premium` | 2 | 79.47 | 79.47 | 81.26 | 81.41 |
| `/request` | 2 | 43.39 | 43.39 | 49.48 | 50.02 |
| `/root-ca.pem` | 2 | 458.57 | 458.57 | 717.47 | 740.48 |
| `/token` | 4 | 102.48 | 102.91 | 166.2 | 167.39 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **67**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 19 | 37.21 | 30.0 | 64.4 | 67.28 |
| OPIN processing | 67 | 49.46 | 28.0 | 151.8 | 275.38 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
2 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 21 | 10736.1 | 11455.0 | 12053.0 | 12083.4 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11955 | 26143 |
| Client (test tool, total traffic) | 17658 | 50212 | 67870 |
| PKI/CRL | 10006 | 704 | 10710 |
| RS | 26018 | 4999 | 31017 |

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

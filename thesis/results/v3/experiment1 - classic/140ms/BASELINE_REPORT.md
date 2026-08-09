# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:37:36.323554+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 23.91 | 23.91 | 25.19 | 25.31 |
| `/jwks` | 2 | 804.8 | 804.8 | 871.36 | 877.27 |
| `/open-insurance/consents/v3/consents` | 2 | 899.68 | 899.68 | 899.73 | 899.74 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:29e09855-93a1-459e-a106-0291586c8ada` | 1 | 438.72 | 438.72 | 438.72 | 438.72 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:9bcb2d82-68d3-4735-bfe2-d1c211462d87` | 5 | 439.56 | 439.88 | 441.8 | 442.0 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 585.93 | 585.93 | 590.4 | 590.8 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/claim` | 2 | 590.33 | 590.33 | 591.02 | 591.08 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/policy-info` | 2 | 592.16 | 592.16 | 594.59 | 594.8 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/premium` | 2 | 587.94 | 587.94 | 589.4 | 589.53 |
| `/request` | 2 | 291.22 | 291.22 | 293.48 | 293.69 |
| `/root-ca.pem` | 2 | 908.42 | 908.42 | 1438.85 | 1486.0 |
| `/token` | 4 | 729.41 | 727.43 | 1172.12 | 1173.21 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 9 | 218.22 | 295.0 | 304.6 | 304.92 |
| OPIN processing | 58 | 386.43 | 154.5 | 1166.8 | 1995.07 |

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

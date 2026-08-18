# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T03:29:56.309231+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 24.38 | 24.38 | 25.09 | 25.15 |
| `/jwks` | 2 | 125.25 | 125.25 | 134.58 | 135.41 |
| `/open-insurance/consents/v3/consents` | 2 | 314.41 | 314.41 | 411.18 | 419.78 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:3691ba30-0c8a-4769-a7de-77b31acc0c89` | 5 | 92.34 | 96.32 | 102.16 | 103.22 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:623c4513-33fe-4ad0-9802-444783b14711` | 1 | 81.46 | 81.46 | 81.46 | 81.46 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 112.9 | 112.9 | 114.09 | 114.2 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/claim` | 2 | 123.24 | 123.24 | 124.46 | 124.57 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/policy-info` | 2 | 105.97 | 105.97 | 113.86 | 114.56 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/premium` | 2 | 167.59 | 167.59 | 200.63 | 203.57 |
| `/request` | 2 | 53.27 | 53.27 | 63.04 | 63.91 |
| `/root-ca.pem` | 2 | 93.17 | 93.17 | 106.78 | 107.99 |
| `/token` | 4 | 141.13 | 153.12 | 208.42 | 209.58 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 5 | 61 | 62.0 | 63.8 | 63.96 |
| OPIN processing | 38 | 64.18 | 39.0 | 191.05 | 246.14 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

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

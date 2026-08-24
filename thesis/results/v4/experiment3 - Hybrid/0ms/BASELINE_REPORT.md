# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T20:44:30.048978+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **179486 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5481.42 bytes** (max: 7596 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 305.65 | 305.65 | 558.05 | 580.48 |
| `/jwks` | 2 | 86.3 | 86.3 | 92.03 | 92.53 |
| `/open-insurance/consents/v3/consents` | 2 | 1413.68 | 1413.68 | 2477.37 | 2571.93 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:4ba22eed-da6e-4f41-816c-48f05fc7ab1d` | 1 | 71.62 | 71.62 | 71.62 | 71.62 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:52a61f97-cea4-420d-b497-92ad02e3f4c7` | 5 | 87.64 | 87.92 | 118.47 | 124.4 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 270.04 | 270.04 | 406.83 | 418.99 |
| `/open-insurance/insurance-person/v2/insurance-person/c5de8fb2-29e0-4b29-9cc5-0c4e8765c57e/claim` | 2 | 109.61 | 109.61 | 119.3 | 120.16 |
| `/open-insurance/insurance-person/v2/insurance-person/c5de8fb2-29e0-4b29-9cc5-0c4e8765c57e/policy-info` | 2 | 90.55 | 90.55 | 111.28 | 113.12 |
| `/open-insurance/insurance-person/v2/insurance-person/c5de8fb2-29e0-4b29-9cc5-0c4e8765c57e/premium` | 2 | 89.9 | 89.9 | 111.31 | 113.21 |
| `/request` | 2 | 49.87 | 49.87 | 65.88 | 67.3 |
| `/root-ca.pem` | 2 | 2840.51 | 2840.51 | 5245.15 | 5458.9 |
| `/token` | 4 | 155.65 | 153.73 | 273.55 | 283.08 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 38 | 41.0 | 48.0 | 48.8 |
| OPIN processing | 38 | 162.58 | 65.5 | 397.85 | 1706.74 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 19292 | 47253 | 66545 |
| Client (test tool, total traffic) | 52956 | 126530 | 179486 |
| PKI/CRL | 10002 | 704 | 10706 |
| RS | 97236 | 4999 | 102235 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 5387 |
| 2 | 5658 |
| 3 | 5658 |
| 4 | 5658 |
| 5 | 5658 |
| 6 | 5967 |
| 7 | 5389 |
| 8 | 5387 |
| 9 | 1812 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 5387 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 5780 |
| 16 | 5389 |
| 17 | 5387 |
| 18 | 1812 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

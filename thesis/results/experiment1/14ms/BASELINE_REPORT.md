# Baseline Report (Classical Cryptography)

Generated at: 2026-08-03T19:30:19.185371+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **71750 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\14ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260803T192912Z.json` |
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\14ms\consents_v3__opin-consent-api-status-test-v3_20260803T192948Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\14ms\person_v2__opin-consents_api_preflight_test-module_v3_20260803T192953Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\14ms\person_v2__person_api_core_test-module_v2.0.0_20260803T193018Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 263.75 | 124.0 | 617.9 | 686.78 |
| `/jwks` | 2 | 92 | 92.0 | 93.8 | 93.96 |
| `/open-insurance/consents/v3/consents` | 2 | 163 | 163.0 | 175.6 | 176.72 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:3cbbabac-323a-4b7b-80ae-20b7a97fd336` | 5 | 138.2 | 130.0 | 163.0 | 167.8 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:4f954217-63b3-483c-93a4-a0adcc3c0a9d` | 1 | 155 | 155 | 155 | 155 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 170.5 | 170.5 | 173.65 | 173.93 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/claim` | 2 | 186.5 | 186.5 | 186.95 | 186.99 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/policy-info` | 2 | 167 | 167.0 | 171.5 | 171.9 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/premium` | 2 | 178.5 | 178.5 | 185.25 | 185.85 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 89 | 89 | 89 | 89 |
| `/request` | 2 | 109.5 | 109.5 | 116.25 | 116.85 |
| `/root-ca.pem` | 4 | 295.25 | 143.0 | 707.85 | 782.37 |
| `/token` | 8 | 152.12 | 105.5 | 316.55 | 318.51 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **56**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 55 | 45.27 | 50.0 | 64.0 | 65.46 |
| OPIN processing | 56 | 52.45 | 35.0 | 180.25 | 261.4 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 56 | 11502.16 | 11234.5 | 13976.0 | 14768.7 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13348 | 29698 |
| Client (test tool, total traffic) | 19485 | 52265 | 71750 |
| Directory | 1311 | 465 | 1776 |
| PKI/CRL | 19814 | 800 | 20614 |
| RS | 14790 | 4872 | 19662 |

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
| 1 | 953 |
| 2 | 950 |
| 3 | 953 |
| 4 | 1549 |
| 5 | 937 |
| 6 | 953 |
| 7 | 1810 |
| 8 | 953 |
| 9 | 953 |
| 10 | 1363 |
| 11 | 937 |
| 12 | 953 |
| 13 | 1810 |

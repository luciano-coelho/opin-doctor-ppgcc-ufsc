# Baseline Report (Classical Cryptography)

Generated at: 2026-08-03T19:28:32.002649+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **71744 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260803T192633Z.json` |
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\consents_v3__opin-consent-api-status-test-v3_20260803T192725Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\person_v2__opin-consents_api_preflight_test-module_v3_20260803T192730Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\person_v2__person_api_core_test-module_v2.0.0_20260803T192831Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 622.5 | 388.0 | 1485.0 | 1600.2 |
| `/jwks` | 2 | 31.5 | 31.5 | 39.15 | 39.83 |
| `/open-insurance/consents/v3/consents` | 2 | 1180 | 1180.0 | 2167.3 | 2255.06 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:80f4e625-9aff-4220-b116-bab8a34a8b20` | 5 | 110.6 | 102.0 | 172.4 | 181.68 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:88d82fef-435c-4e0b-bac8-3fd07efd5590` | 1 | 43 | 43 | 43 | 43 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 188 | 188.0 | 250.1 | 255.62 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/claim` | 2 | 124 | 124.0 | 151.9 | 154.38 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/policy-info` | 2 | 114.5 | 114.5 | 123.95 | 124.79 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/premium` | 2 | 132.5 | 132.5 | 137.45 | 137.89 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 44 | 44 | 44 | 44 |
| `/request` | 2 | 57.5 | 57.5 | 64.25 | 64.85 |
| `/root-ca.pem` | 4 | 1329 | 1053.0 | 2320.3 | 2459.26 |
| `/token` | 8 | 89.62 | 43.0 | 217.75 | 233.15 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **60**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 57 | 24.16 | 22.0 | 50.2 | 54.88 |
| OPIN processing | 60 | 82.68 | 31.0 | 190.1 | 1071.65 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
2 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 59 | 11326.69 | 11263.0 | 13976.0 | 14740.32 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13346 | 29696 |
| Client (test tool, total traffic) | 19483 | 52261 | 71744 |
| Directory | 1311 | 465 | 1776 |
| PKI/CRL | 19810 | 800 | 20610 |
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

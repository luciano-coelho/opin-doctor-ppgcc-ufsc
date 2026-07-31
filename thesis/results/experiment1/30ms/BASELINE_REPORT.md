# Baseline Report (Classical Cryptography)

Generated at: 2026-07-31T14:23:45.630562+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **70638 bytes**
- Total HTTP requests: **36**
- JWTs found: **12**
- Average JWT size: **1177 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\30ms\consents_v3__opin-consent-api-status-test-v3_20260730T214730Z.json` |
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\30ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260730T214705Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\30ms\person_v2__opin-consents_api_preflight_test-module_v3_20260730T214736Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\30ms\person_v2__person_api_core_test-module_v2.0.0_20260730T214801Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 363.25 | 187.0 | 849.65 | 937.13 |
| `/jwks` | 2 | 164 | 164.0 | 164.9 | 164.98 |
| `/open-insurance/consents/v3/consents` | 2 | 248.5 | 248.5 | 258.85 | 259.77 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:74466d89-9fa6-4029-9d53-66da309effa0` | 1 | 221 | 221 | 221 | 221 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:d6228072-15a4-430d-a82f-5a3137e52158` | 5 | 227.2 | 219.0 | 251.0 | 256.6 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 271 | 271.0 | 275.5 | 275.9 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/claim` | 2 | 260.5 | 260.5 | 261.85 | 261.97 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/policy-info` | 2 | 257 | 257.0 | 265.1 | 265.82 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/premium` | 2 | 256.5 | 256.5 | 259.65 | 259.93 |
| `/request` | 2 | 182 | 182.0 | 182.9 | 182.98 |
| `/root-ca.pem` | 4 | 514.75 | 352.0 | 1080.1 | 1164.82 |
| `/token` | 8 | 238.25 | 182.5 | 440.95 | 441.79 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **56**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 49 | 59.61 | 73.0 | 85.2 | 90.08 |
| OPIN processing | 56 | 77.3 | 45.0 | 282.25 | 381.85 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
6 handshake sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13346 | 29696 |
| Client (test tool, total traffic) | 19396 | 51242 | 70638 |
| Directory | 272 | 378 | 650 |
| PKI/CRL | 19814 | 800 | 20614 |
| RS | 14806 | 4872 | 19678 |

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
| 2 | 1549 |
| 3 | 937 |
| 4 | 953 |
| 5 | 1810 |
| 6 | 953 |
| 7 | 953 |
| 8 | 953 |
| 9 | 1363 |
| 10 | 937 |
| 11 | 953 |
| 12 | 1810 |

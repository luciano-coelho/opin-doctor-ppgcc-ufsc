# Baseline Report (Classical Cryptography)

Generated at: 2026-07-31T14:23:45.184420+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **71628 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\consents_v3__opin-consent-api-status-test-v3_20260730T214441Z.json` |
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260730T214415Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\person_v2__opin-consents_api_preflight_test-module_v3_20260730T214446Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\person_v2__person_api_core_test-module_v2.0.0_20260730T214512Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 245.5 | 97.5 | 604.9 | 676.18 |
| `/jwks` | 2 | 12.5 | 12.5 | 12.95 | 12.99 |
| `/open-insurance/consents/v3/consents` | 2 | 49.5 | 49.5 | 58.05 | 58.81 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:45a08674-3591-4480-be7a-4a0591b1841c` | 5 | 40.8 | 41.0 | 53.4 | 55.48 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:6b2c6799-5c4d-4758-9748-67c8c2b747c7` | 1 | 27 | 27 | 27 | 27 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 91.5 | 91.5 | 109.95 | 111.59 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/claim` | 2 | 93.5 | 93.5 | 95.75 | 95.95 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/policy-info` | 2 | 96 | 96.0 | 104.1 | 104.82 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/premium` | 2 | 91.5 | 91.5 | 102.75 | 103.75 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 17 | 17 | 17 | 17 |
| `/request` | 2 | 28 | 28.0 | 32.5 | 32.9 |
| `/root-ca.pem` | 4 | 422.5 | 261.0 | 970.85 | 1050.17 |
| `/token` | 7 | 41.57 | 23.0 | 96.2 | 100.04 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **56**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 51 | 15.41 | 12.0 | 29.0 | 34.0 |
| OPIN processing | 56 | 18.84 | 11.5 | 56.5 | 69.2 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
5 handshake sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13346 | 29696 |
| Client (test tool, total traffic) | 19483 | 52145 | 71628 |
| Directory | 1175 | 465 | 1640 |
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
| 7 | 950 |
| 8 | 953 |
| 9 | 953 |
| 10 | 1363 |
| 11 | 937 |
| 12 | 953 |
| 13 | 1810 |

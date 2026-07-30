# Baseline Report (Classical Cryptography)

Generated at: 2026-07-30T21:37:42.520682+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **71766 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260730T213630Z.json` |
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\consents_v3__opin-consent-api-status-test-v3_20260730T213706Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\person_v2__opin-consents_api_preflight_test-module_v3_20260730T213711Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\0ms\person_v2__person_api_core_test-module_v2.0.0_20260730T213742Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 667.75 | 659.5 | 1250.55 | 1255.71 |
| `/jwks` | 2 | 13 | 13.0 | 13.9 | 13.98 |
| `/open-insurance/consents/v3/consents` | 2 | 55 | 55.0 | 57.7 | 57.94 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:b7ada28b-c127-4fa1-a681-54c8bb746c51` | 1 | 43 | 43 | 43 | 43 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:efcbdd95-17fb-4be8-b7be-347cbfa524b9` | 5 | 38.2 | 38.0 | 44.0 | 44.0 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 65.5 | 65.5 | 72.25 | 72.85 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/claim` | 2 | 74 | 74.0 | 75.8 | 75.96 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/policy-info` | 2 | 74 | 74.0 | 81.2 | 81.84 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/premium` | 2 | 73 | 73.0 | 76.6 | 76.92 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 31 | 31 | 31 | 31 |
| `/request` | 2 | 32 | 32.0 | 32.9 | 32.98 |
| `/root-ca.pem` | 4 | 322.5 | 156.0 | 758.1 | 840.42 |
| `/token` | 8 | 44.62 | 25.0 | 108.55 | 110.51 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **59**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 58 | 19.22 | 17.5 | 32.6 | 37.43 |
| OPIN processing | 59 | 19.98 | 13.0 | 59.7 | 105.84 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.

## Bytes by participant

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13348 | 29698 |
| Client | 19485 | 52281 | 71766 |
| Directory | 1311 | 465 | 1776 |
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

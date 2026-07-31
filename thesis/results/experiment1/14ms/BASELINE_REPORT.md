# Baseline Report (Classical Cryptography)

Generated at: 2026-07-31T14:23:45.399297+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **71764 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\14ms\consents_v3__opin-consent-api-status-test-v3_20260730T214609Z.json` |
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\14ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260730T214543Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\14ms\person_v2__opin-consents_api_preflight_test-module_v3_20260730T214614Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\14ms\person_v2__person_api_core_test-module_v2.0.0_20260730T214640Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 463.5 | 530.5 | 676.5 | 677.7 |
| `/jwks` | 2 | 83 | 83.0 | 83.9 | 83.98 |
| `/open-insurance/consents/v3/consents` | 2 | 135 | 135.0 | 139.5 | 139.9 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:020b3a8b-4049-4843-aabd-e7ef6617337b` | 5 | 125.6 | 117.0 | 143.0 | 143.8 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:2bb528fd-618f-4744-aa04-332cc0f4ebe8` | 1 | 115 | 115 | 115 | 115 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 138 | 138.0 | 138.0 | 138.0 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/claim` | 2 | 145 | 145.0 | 153.1 | 153.82 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/policy-info` | 2 | 162 | 162.0 | 162.9 | 162.98 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/premium` | 2 | 134.5 | 134.5 | 136.75 | 136.95 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 74 | 74 | 74 | 74 |
| `/request` | 2 | 92.5 | 92.5 | 92.95 | 92.99 |
| `/root-ca.pem` | 4 | 930 | 147.0 | 2853.35 | 3231.47 |
| `/token` | 8 | 123.75 | 92.0 | 239.9 | 247.18 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **56**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 52 | 33.96 | 38.0 | 48.35 | 52.49 |
| OPIN processing | 56 | 43.54 | 29.0 | 150.0 | 207.8 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
4 handshake sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13346 | 29696 |
| Client (test tool, total traffic) | 19483 | 52281 | 71764 |
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

# Baseline Report (Classical Cryptography)

Generated at: 2026-07-31T14:23:46.285285+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **72890 bytes**
- Total HTTP requests: **38**
- JWTs found: **14**
- Average JWT size: **1144.57 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\320ms\consents_v3__opin-consent-api-status-test-v3_20260731T000533Z.json` |
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\320ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260731T000427Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\320ms\person_v2__opin-consents_api_preflight_test-module_v3_20260731T132619Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\320ms\person_v2__person_api_core_test-module_v2.0.0_20260731T132802Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 652 | 625.5 | 965.85 | 992.37 |
| `/jwks` | 2 | 1945 | 1945.0 | 1945.9 | 1945.98 |
| `/open-insurance/consents/v3/consents` | 2 | 2285.5 | 2285.5 | 2517.25 | 2537.85 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:8b60a095-a283-456c-bfdc-a5df2d6de4ff` | 5 | 2002.8 | 1999.0 | 2019.8 | 2020.76 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:9bfcb09a-c898-4b89-bb52-ff815c9df882` | 1 | 2022 | 2022 | 2022 | 2022 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 2322 | 2322.0 | 2330.1 | 2330.82 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/claim` | 2 | 2349 | 2349.0 | 2360.7 | 2361.74 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/policy-info` | 2 | 2319 | 2319.0 | 2337.0 | 2338.6 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/premium` | 2 | 2352 | 2352.0 | 2379.9 | 2382.38 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 2 | 1321 | 1321.0 | 1321.0 | 1321.0 |
| `/request` | 2 | 1650.5 | 1650.5 | 1653.65 | 1653.93 |
| `/root-ca.pem` | 4 | 718.5 | 541.0 | 1517.85 | 1611.57 |
| `/token` | 8 | 2121.5 | 1667.5 | 3668.25 | 3669.65 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **136**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 130 | 694.88 | 672.0 | 1281.0 | 1281.0 |
| OPIN processing | 136 | 610.63 | 345.0 | 2340.5 | 4344.1 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
2 handshake sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13348 | 29698 |
| Client (test tool, total traffic) | 19572 | 53318 | 72890 |
| Directory | 2350 | 552 | 2902 |
| PKI/CRL | 19812 | 800 | 20612 |
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
| 9 | 950 |
| 10 | 953 |
| 11 | 1363 |
| 12 | 937 |
| 13 | 953 |
| 14 | 1810 |

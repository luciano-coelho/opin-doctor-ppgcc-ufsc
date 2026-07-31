# Baseline Report (Classical Cryptography)

Generated at: 2026-07-31T13:49:42.206528+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **71037 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\140ms\consents_v3__opin-consent-api-status-test-v3_20260730T214911Z.json` |
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\140ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260730T214835Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\140ms\person_v2__opin-consents_api_preflight_test-module_v3_20260730T214916Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\140ms\person_v2__person_api_core_test-module_v2.0.0_20260730T235749Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 462 | 463.5 | 804.65 | 810.53 |
| `/jwks` | 2 | 790 | 790.0 | 856.6 | 862.52 |
| `/open-insurance/consents/v3/consents` | 1 | 1082 | 1082 | 1082 | 1082 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:19492138-05f2-4429-86a5-247eac5e012a` | 1 | 909 | 909 | 909 | 909 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:c45021ac-e015-4a2c-a840-88b19c5775a0` | 5 | 874.4 | 874.0 | 881.8 | 882.76 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1058.5 | 1058.5 | 1066.15 | 1066.83 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/claim` | 2 | 1053.5 | 1053.5 | 1058.45 | 1058.89 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/policy-info` | 2 | 1073 | 1073.0 | 1094.6 | 1096.52 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/premium` | 2 | 1062.5 | 1062.5 | 1072.85 | 1073.77 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 580 | 580 | 580 | 580 |
| `/request` | 2 | 762 | 762.0 | 775.5 | 776.7 |
| `/root-ca.pem` | 4 | 930 | 660.5 | 2075.4 | 2217.48 |
| `/token` | 8 | 947.12 | 745.5 | 1678.95 | 1702.19 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **93**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 91 | 326.95 | 306.0 | 559.0 | 559.0 |
| OPIN processing | 93 | 292.58 | 158.0 | 1062.0 | 2074.24 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
2 handshake sample(s) discarded as outliers (> 3x this scenario's P99; see filter_handshake_outliers).

## Bytes by participant

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13350 | 29700 |
| Client | 19487 | 51550 | 71037 |
| Directory | 1311 | 465 | 1776 |
| PKI/CRL | 19810 | 800 | 20610 |
| RS | 14079 | 4872 | 18951 |

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

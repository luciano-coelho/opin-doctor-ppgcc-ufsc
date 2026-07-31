# Baseline Report (Classical Cryptography)

Generated at: 2026-07-31T13:49:42.329833+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **72886 bytes**
- Total HTTP requests: **38**
- JWTs found: **14**
- Average JWT size: **1144.57 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\225ms\consents_v3__opin-consent-api-status-test-v3_20260730T235938Z.json` |
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\225ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260730T235837Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\225ms\person_v2__opin-consents_api_preflight_test-module_v3_20260730T235949Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\225ms\person_v2__person_api_core_test-module_v2.0.0_20260731T000348Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 2504.5 | 1740.0 | 4953.75 | 5406.75 |
| `/jwks` | 2 | 1384 | 1384.0 | 1387.6 | 1387.92 |
| `/open-insurance/consents/v3/consents` | 2 | 1590.5 | 1590.5 | 1703.45 | 1713.49 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:14aa7129-0c3a-4dcd-831a-1fe074a5e855` | 1 | 1424 | 1424 | 1424 | 1424 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:376bf9eb-7539-4694-8b4c-643dd5933bf2` | 5 | 1422.4 | 1419.0 | 1449.2 | 1453.84 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1650.5 | 1650.5 | 1651.85 | 1651.97 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/claim` | 2 | 1674.5 | 1674.5 | 1694.75 | 1696.55 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/policy-info` | 2 | 1685 | 1685.0 | 1695.8 | 1696.76 |
| `/open-insurance/insurance-person/v2/insurance-person/03e0a33f-c731-48d5-b284-a0c4478ea411/premium` | 2 | 1658.5 | 1658.5 | 1664.35 | 1664.87 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 2 | 958 | 958.0 | 961.6 | 961.92 |
| `/request` | 2 | 1177 | 1177.0 | 1181.5 | 1181.9 |
| `/root-ca.pem` | 4 | 1774.5 | 1776.0 | 2235.9 | 2266.38 |
| `/token` | 8 | 1596.75 | 1313.5 | 2891.75 | 3024.75 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **60**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 59 | 446.83 | 473.0 | 515.0 | 515.84 |
| OPIN processing | 60 | 461.68 | 254.5 | 1699.75 | 2594.01 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake sample(s) discarded as outliers (> 3x this scenario's P99; see filter_handshake_outliers).

## Bytes by participant

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13348 | 29698 |
| Client | 19572 | 53314 | 72886 |
| Directory | 2350 | 552 | 2902 |
| PKI/CRL | 19808 | 800 | 20608 |
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

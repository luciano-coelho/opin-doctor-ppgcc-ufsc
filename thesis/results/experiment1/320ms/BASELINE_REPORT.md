# Baseline Report (Classical Cryptography)

Generated at: 2026-08-03T19:39:24.915270+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **70816 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\320ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260803T193632Z.json` |
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\320ms\consents_v3__opin-consent-api-status-test-v3_20260803T193808Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\320ms\person_v2__opin-consents_api_preflight_test-module_v3_20260803T193819Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\320ms\person_v2__person_api_core_test-module_v2.0.0_20260803T193924Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 413.75 | 384.5 | 769.1 | 784.22 |
| `/jwks` | 2 | 1936.5 | 1936.5 | 1936.95 | 1936.99 |
| `/open-insurance/consents/v3/consents` | 2 | 1970.5 | 1970.5 | 1970.95 | 1970.99 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f140b4e8-5455-4187-ae43-88f60779b09b` | 5 | 1951.6 | 1952.0 | 1954.6 | 1954.92 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f1d09501-e5ef-4da6-95d2-3a4e1f43e69a` | 1 | 1952 | 1952 | 1952 | 1952 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 2283 | 2283.0 | 2288.4 | 2288.88 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/claim` | 2 | 2281 | 2281.0 | 2282.8 | 2282.96 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/policy-info` | 2 | 2279 | 2279.0 | 2279.9 | 2279.98 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/premium` | 1 | 2287 | 2287 | 2287 | 2287 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 1298 | 1298 | 1298 | 1298 |
| `/request` | 2 | 1627 | 1627.0 | 1630.6 | 1630.92 |
| `/root-ca.pem` | 4 | 1122 | 977.5 | 2234.9 | 2397.38 |
| `/token` | 8 | 2113.88 | 1785.5 | 3584.65 | 3584.93 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **57**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 56 | 453.89 | 650.0 | 656.0 | 657.45 |
| OPIN processing | 57 | 655.86 | 334.0 | 2301.0 | 3466.88 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 56 | 11524.43 | 11234.5 | 13976.0 | 14768.7 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13348 | 29698 |
| Client (test tool, total traffic) | 19485 | 51331 | 70816 |
| Directory | 1311 | 465 | 1776 |
| PKI/CRL | 19812 | 800 | 20612 |
| RS | 13858 | 4872 | 18730 |

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
| 2 | 953 |
| 3 | 1549 |
| 4 | 937 |
| 5 | 953 |
| 6 | 1810 |
| 7 | 953 |
| 8 | 950 |
| 9 | 953 |
| 10 | 1363 |
| 11 | 937 |
| 12 | 953 |
| 13 | 1810 |

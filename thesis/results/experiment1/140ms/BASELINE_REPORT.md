# Baseline Report (Classical Cryptography)

Generated at: 2026-08-03T19:33:42.627954+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **71756 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\140ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260803T193211Z.json` |
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\140ms\consents_v3__opin-consent-api-status-test-v3_20260803T193251Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\140ms\person_v2__opin-consents_api_preflight_test-module_v3_20260803T193256Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\140ms\person_v2__person_api_core_test-module_v2.0.0_20260803T193342Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 364.25 | 218.0 | 813.15 | 894.63 |
| `/jwks` | 2 | 713.5 | 713.5 | 714.85 | 714.97 |
| `/open-insurance/consents/v3/consents` | 2 | 894 | 894.0 | 898.5 | 898.9 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:3ff04068-4ba4-4aff-a6f0-1dac9a346548` | 5 | 874.4 | 874.0 | 879.4 | 879.88 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:b5e6821a-2aff-4171-83be-b31aa45ac218` | 1 | 877 | 877 | 877 | 877 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1020.5 | 1020.5 | 1022.75 | 1022.95 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/claim` | 2 | 1018.5 | 1018.5 | 1019.85 | 1019.97 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/policy-info` | 2 | 1019 | 1019.0 | 1021.7 | 1021.94 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/premium` | 2 | 1016.5 | 1016.5 | 1018.75 | 1018.95 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 587 | 587 | 587 | 587 |
| `/request` | 2 | 728.5 | 728.5 | 730.75 | 730.95 |
| `/root-ca.pem` | 4 | 447.75 | 356.5 | 916.65 | 980.13 |
| `/token` | 8 | 926.88 | 726.0 | 1609.9 | 1611.58 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **56**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 56 | 221.29 | 288.5 | 297.25 | 299.35 |
| OPIN processing | 56 | 291.96 | 153.0 | 1035.5 | 1552.65 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 56 | 11541.5 | 11234.5 | 13976.0 | 14770.9 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13354 | 29704 |
| Client (test tool, total traffic) | 19491 | 52265 | 71756 |
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

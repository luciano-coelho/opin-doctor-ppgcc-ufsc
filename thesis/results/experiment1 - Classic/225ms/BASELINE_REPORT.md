# Baseline Report (Classical Cryptography)

Generated at: 2026-08-03T19:36:02.602864+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **71475 bytes**
- Total HTTP requests: **37**
- JWTs found: **13**
- Average JWT size: **1159.54 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\225ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260803T193415Z.json` |
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\225ms\consents_v3__opin-consent-api-status-test-v3_20260803T193501Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\225ms\person_v2__opin-consents_api_preflight_test-module_v3_20260803T193506Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\225ms\person_v2__person_api_core_test-module_v2.0.0_20260803T193602Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 1331.25 | 302.0 | 4007.0 | 4506.2 |
| `/jwks` | 2 | 1139 | 1139.0 | 1139.9 | 1139.98 |
| `/open-insurance/consents/v3/consents` | 2 | 1392 | 1392.0 | 1392.9 | 1392.98 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:d3d5d1c1-469e-4463-b589-d76c85c775ab` | 5 | 1382.8 | 1382.0 | 1387.2 | 1387.84 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f01748e3-1e0e-46da-a54b-43328f4ee66c` | 1 | 1383 | 1383 | 1383 | 1383 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1632.5 | 1632.5 | 1642.85 | 1643.77 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/claim` | 2 | 1628 | 1628.0 | 1636.1 | 1636.82 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/policy-info` | 2 | 1617 | 1617.0 | 1619.7 | 1619.94 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/premium` | 2 | 1608.5 | 1608.5 | 1611.65 | 1611.93 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 1 | 927 | 927 | 927 | 927 |
| `/request` | 2 | 1152 | 1152.0 | 1152.0 | 1152.0 |
| `/root-ca.pem` | 4 | 469.75 | 497.0 | 778.95 | 784.59 |
| `/token` | 6 | 1694.5 | 1381.5 | 2554.0 | 2554.0 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **63**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 63 | 304.14 | 456.0 | 469.8 | 475.9 |
| OPIN processing | 63 | 470.25 | 239.0 | 1629.0 | 2355.88 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 63 | 11464.27 | 11003.0 | 13976.0 | 14702.48 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13346 | 29696 |
| Client (test tool, total traffic) | 19483 | 51992 | 71475 |
| Directory | 1039 | 465 | 1504 |
| PKI/CRL | 19813 | 800 | 20613 |
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

# Baseline Report (Classical Cryptography)

Generated at: 2026-08-03T19:31:46.360648+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **70622 bytes**
- Total HTTP requests: **36**
- JWTs found: **12**
- Average JWT size: **1177 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\30ms\consents_v3__opin-consents_api_preflight_test-module_v3_20260803T193049Z.json` |
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\30ms\consents_v3__opin-consent-api-status-test-v3_20260803T193115Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\30ms\person_v2__opin-consents_api_preflight_test-module_v3_20260803T193120Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `C:\Users\lucia_csx8nlz\MockOPIN\thesis\results\experiment1\30ms\person_v2__person_api_core_test-module_v2.0.0_20260803T193146Z.json` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 377.75 | 314.5 | 627.3 | 667.86 |
| `/jwks` | 2 | 171 | 171.0 | 176.4 | 176.88 |
| `/open-insurance/consents/v3/consents` | 2 | 245 | 245.0 | 245.0 | 245.0 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:9b65eb02-7e22-4736-8674-f74f86c0c102` | 1 | 219 | 219 | 219 | 219 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:ed947026-28f9-4251-b596-804a4a45e3ac` | 5 | 239.4 | 230.0 | 263.6 | 263.92 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 266.5 | 266.5 | 269.65 | 269.93 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/claim` | 2 | 270.5 | 270.5 | 274.55 | 274.91 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/policy-info` | 2 | 268 | 268.0 | 269.8 | 269.96 |
| `/open-insurance/insurance-person/v2/insurance-person/3b723160-654c-4554-9342-30c6c40f1d4c/premium` | 2 | 253.5 | 253.5 | 256.65 | 256.93 |
| `/request` | 2 | 183.5 | 183.5 | 185.75 | 185.95 |
| `/root-ca.pem` | 4 | 403.75 | 323.5 | 809.3 | 864.26 |
| `/token` | 8 | 245.25 | 186.5 | 447.1 | 451.02 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **55**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 54 | 74.24 | 75.5 | 107.1 | 111.0 |
| OPIN processing | 55 | 81.67 | 49.0 | 299.4 | 407.82 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 55 | 11495.45 | 11003.0 | 13976.0 | 14777.08 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 16350 | 13346 | 29696 |
| Client (test tool, total traffic) | 19396 | 51226 | 70622 |
| Directory | 272 | 378 | 650 |
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
| 2 | 953 |
| 3 | 1549 |
| 4 | 937 |
| 5 | 953 |
| 6 | 1810 |
| 7 | 953 |
| 8 | 953 |
| 9 | 1363 |
| 10 | 937 |
| 11 | 953 |
| 12 | 1810 |

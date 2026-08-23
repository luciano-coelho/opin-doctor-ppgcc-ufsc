# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T04:35:28.367318+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **144192 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **4123.88 bytes** (max: 7596 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 315.59 | 315.59 | 569.14 | 591.68 |
| `/jwks` | 2 | 2113.93 | 2113.93 | 2550.85 | 2589.69 |
| `/open-insurance/consents/v3/consents` | 2 | 3336.27 | 3336.27 | 4556.53 | 4665.0 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:81b82aa6-970a-424e-9a9f-0fb4f8465a8d` | 5 | 1000.26 | 992.82 | 1017.11 | 1017.44 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:a7a85371-bff6-4ab5-96c8-3af6ca6417b5` | 1 | 996.77 | 996.77 | 996.77 | 996.77 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1342.74 | 1342.74 | 1371.76 | 1374.34 |
| `/open-insurance/insurance-person/v2/insurance-person/6bac650a-4ae7-4017-9c70-29e182b5128c/claim` | 2 | 1332.0 | 1332.0 | 1347.06 | 1348.4 |
| `/open-insurance/insurance-person/v2/insurance-person/6bac650a-4ae7-4017-9c70-29e182b5128c/policy-info` | 2 | 1322.33 | 1322.33 | 1328.99 | 1329.59 |
| `/open-insurance/insurance-person/v2/insurance-person/6bac650a-4ae7-4017-9c70-29e182b5128c/premium` | 2 | 1321.84 | 1321.84 | 1332.01 | 1332.92 |
| `/request` | 2 | 654.39 | 654.39 | 658.16 | 658.49 |
| `/root-ca.pem` | 2 | 467.97 | 467.97 | 707.38 | 728.66 |
| `/token` | 4 | 1661.72 | 1661.41 | 2665.24 | 2670.25 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 658.5 | 658.0 | 661.5 | 661.9 |
| OPIN processing | 38 | 814.82 | 345.0 | 2709.75 | 4075.24 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25109.33 | 24991.0 | 25515.0 | 25602.2 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 19292 | 11955 | 31247 |
| Client (test tool, total traffic) | 17658 | 126534 | 144192 |
| PKI/CRL | 10006 | 704 | 10710 |
| RS | 97236 | 4999 | 102235 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 975 |
| 2 | 5658 |
| 3 | 5658 |
| 4 | 5658 |
| 5 | 5658 |
| 6 | 1555 |
| 7 | 977 |
| 8 | 975 |
| 9 | 1812 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 975 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 1368 |
| 16 | 977 |
| 17 | 975 |
| 18 | 1812 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

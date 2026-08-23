# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T04:28:22.543033+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **144186 bytes**
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
| `/issuer-ca.pem` | 2 | 304.13 | 304.13 | 552.35 | 574.41 |
| `/jwks` | 2 | 125.12 | 125.12 | 149.07 | 151.19 |
| `/open-insurance/consents/v3/consents` | 2 | 1073.24 | 1073.24 | 1880.87 | 1952.66 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:77ca5b41-eaea-4915-9734-2a21918640d9` | 1 | 70.41 | 70.41 | 70.41 | 70.41 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:c092a8a6-a882-4c07-8723-809606d7ac63` | 5 | 105.37 | 87.38 | 150.11 | 158.72 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 134.45 | 134.45 | 173.58 | 177.06 |
| `/open-insurance/insurance-person/v2/insurance-person/06bdae30-b79f-43f6-879d-07bc59858448/claim` | 2 | 106.29 | 106.29 | 114.63 | 115.37 |
| `/open-insurance/insurance-person/v2/insurance-person/06bdae30-b79f-43f6-879d-07bc59858448/policy-info` | 2 | 101.49 | 101.49 | 104.92 | 105.23 |
| `/open-insurance/insurance-person/v2/insurance-person/06bdae30-b79f-43f6-879d-07bc59858448/premium` | 2 | 105.14 | 105.14 | 113.75 | 114.52 |
| `/request` | 2 | 46.25 | 46.25 | 51.11 | 51.54 |
| `/root-ca.pem` | 2 | 417.98 | 417.98 | 666.14 | 688.2 |
| `/token` | 4 | 142.02 | 147.55 | 231.64 | 232.04 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 43.5 | 42.5 | 48.5 | 48.9 |
| OPIN processing | 38 | 120.05 | 44.0 | 235.15 | 1291.18 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25036.67 | 24991.0 | 25188.0 | 25188.0 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 19292 | 11955 | 31247 |
| Client (test tool, total traffic) | 17658 | 126528 | 144186 |
| PKI/CRL | 10000 | 704 | 10704 |
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

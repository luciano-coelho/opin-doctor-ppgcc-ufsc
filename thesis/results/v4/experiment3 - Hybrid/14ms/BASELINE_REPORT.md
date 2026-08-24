# Baseline Report (Classical Cryptography)

Generated at: 2026-08-24T13:05:48.840667+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **191251 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5933.96 bytes** (max: 7695 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 315.49 | 315.49 | 575.05 | 598.12 |
| `/jwks` | 2 | 147.03 | 147.03 | 148.06 | 148.15 |
| `/open-insurance/consents/v3/consents` | 2 | 1167.62 | 1167.62 | 1965.06 | 2035.95 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:033f91ef-36ba-44e5-92c2-50b25f9711c2` | 1 | 82.81 | 82.81 | 82.81 | 82.81 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:3caa1486-cdbc-40b1-be2e-cc2979612b1f` | 5 | 102.11 | 98.59 | 133.29 | 138.96 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 152.37 | 152.37 | 194.12 | 197.83 |
| `/open-insurance/insurance-person/v2/insurance-person/cac23891-c9f5-4fdc-b7bd-14c1e4888c87/claim` | 2 | 111.24 | 111.24 | 123.21 | 124.27 |
| `/open-insurance/insurance-person/v2/insurance-person/cac23891-c9f5-4fdc-b7bd-14c1e4888c87/policy-info` | 2 | 98.32 | 98.32 | 104.49 | 105.03 |
| `/open-insurance/insurance-person/v2/insurance-person/cac23891-c9f5-4fdc-b7bd-14c1e4888c87/premium` | 2 | 101.58 | 101.58 | 109.82 | 110.56 |
| `/request` | 2 | 77.86 | 77.86 | 90.41 | 91.52 |
| `/root-ca.pem` | 2 | 529.54 | 529.54 | 840.9 | 868.58 |
| `/token` | 4 | 175.58 | 182.35 | 271.25 | 272.95 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 58 | 58.5 | 67.25 | 67.85 |
| OPIN processing | 38 | 130.53 | 46.5 | 273.95 | 1343.97 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 31058 | 47253 | 78311 |
| Client (test tool, total traffic) | 52956 | 138295 | 191251 |
| PKI/CRL | 10001 | 704 | 10705 |
| RS | 97236 | 4999 | 102235 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 5387 |
| 2 | 5658 |
| 3 | 5658 |
| 4 | 5658 |
| 5 | 5658 |
| 6 | 5967 |
| 7 | 5389 |
| 8 | 5387 |
| 9 | 7695 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 5387 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 5780 |
| 16 | 5389 |
| 17 | 5387 |
| 18 | 7695 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

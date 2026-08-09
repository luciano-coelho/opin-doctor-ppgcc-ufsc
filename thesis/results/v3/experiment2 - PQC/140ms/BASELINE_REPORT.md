# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T14:38:40.718487+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **112793 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **2950.5 bytes** (max: 7246 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=pqc) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=pqc) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 305.31 | 305.31 | 556.1 | 578.39 |
| `/jwks` | 2 | 844.98 | 844.98 | 923.78 | 930.78 |
| `/open-insurance/consents/v3/consents` | 2 | 925.73 | 925.73 | 935.69 | 936.57 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:60f273a0-1487-4936-8257-aec36fec4280` | 1 | 454.99 | 454.99 | 454.99 | 454.99 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e8f7f229-7240-414b-a8d1-7ff3069d9662` | 5 | 457.36 | 458.89 | 465.17 | 465.43 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 652.84 | 652.84 | 668.51 | 669.9 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/claim` | 2 | 644.45 | 644.45 | 653.81 | 654.64 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/policy-info` | 2 | 605.58 | 605.58 | 608.16 | 608.39 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/premium` | 2 | 598.29 | 598.29 | 599.82 | 599.96 |
| `/request` | 2 | 448.44 | 448.44 | 451.97 | 452.28 |
| `/root-ca.pem` | 2 | 631.39 | 631.39 | 868.6 | 889.69 |
| `/token` | 4 | 756.24 | 753.95 | 1212.0 | 1215.21 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 313.5 | 311.0 | 336.5 | 340.1 |
| OPIN processing | 38 | 346.71 | 163.5 | 1086.6 | 1730.02 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 65590 | 112793 |
| PKI/CRL | 10002 | 664 | 10666 |
| RS | 26018 | 4839 | 30857 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 4703 |
| 2 | 1208 |
| 3 | 1208 |
| 4 | 1208 |
| 5 | 1208 |
| 6 | 5283 |
| 7 | 4705 |
| 8 | 4703 |
| 9 | 7246 |
| 10 | 1192 |
| 11 | 1192 |
| 12 | 4703 |
| 13 | 1254 |
| 14 | 1254 |
| 15 | 5096 |
| 16 | 4705 |
| 17 | 4703 |
| 18 | 7246 |
| 19 | 916 |
| 20 | 916 |
| 21 | 1403 |
| 22 | 1403 |
| 23 | 3146 |
| 24 | 3146 |
| 25 | 1483 |
| 26 | 1483 |

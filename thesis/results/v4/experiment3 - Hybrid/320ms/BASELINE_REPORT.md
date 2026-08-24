# Baseline Report (Classical Cryptography)

Generated at: 2026-08-24T13:15:47.996673+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **191252 bytes**
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
| `/issuer-ca.pem` | 2 | 306.12 | 306.12 | 559.85 | 582.4 |
| `/jwks` | 2 | 2144.49 | 2144.49 | 2600.21 | 2640.72 |
| `/open-insurance/consents/v3/consents` | 2 | 3401.0 | 3401.0 | 4653.33 | 4764.64 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:0d30f770-7a4a-4e00-bf25-c89c4cd16eff` | 1 | 985.22 | 985.22 | 985.22 | 985.22 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:18f0da4a-c6b5-48c6-9770-1d36398cb5f9` | 5 | 1004.51 | 1001.08 | 1026.11 | 1030.36 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1427.14 | 1427.14 | 1519.2 | 1527.38 |
| `/open-insurance/insurance-person/v2/insurance-person/77092715-4388-437b-9459-0088e177b511/claim` | 2 | 1354.68 | 1354.68 | 1371.83 | 1373.35 |
| `/open-insurance/insurance-person/v2/insurance-person/77092715-4388-437b-9459-0088e177b511/policy-info` | 2 | 1333.51 | 1333.51 | 1335.43 | 1335.6 |
| `/open-insurance/insurance-person/v2/insurance-person/77092715-4388-437b-9459-0088e177b511/premium` | 2 | 1319.41 | 1319.41 | 1324.44 | 1324.88 |
| `/request` | 2 | 987.92 | 987.92 | 993.73 | 994.24 |
| `/root-ca.pem` | 2 | 477.0 | 477.0 | 765.09 | 790.7 |
| `/token` | 4 | 2042.01 | 2052.97 | 3054.52 | 3065.9 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 675.67 | 676.0 | 686.25 | 686.85 |
| OPIN processing | 38 | 883.32 | 356.5 | 2796.0 | 4074.72 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25103.5 | 24991.0 | 25488.75 | 25568.95 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 31058 | 47253 | 78311 |
| Client (test tool, total traffic) | 52956 | 138296 | 191252 |
| PKI/CRL | 10002 | 704 | 10706 |
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

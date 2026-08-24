# Baseline Report (Classical Cryptography)

Generated at: 2026-08-24T13:09:21.475839+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **191256 bytes**
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
| `/issuer-ca.pem` | 2 | 322.98 | 322.98 | 579.73 | 602.55 |
| `/jwks` | 2 | 251.59 | 251.59 | 278.81 | 281.23 |
| `/open-insurance/consents/v3/consents` | 2 | 1819.29 | 1819.29 | 3101.61 | 3215.59 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:6b90e979-698a-43c1-8013-6a2c38f45fbb` | 5 | 167.41 | 178.89 | 204.36 | 209.24 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:97cd0437-58be-47a4-a638-9a721d91812d` | 1 | 142.93 | 142.93 | 142.93 | 142.93 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 324.02 | 324.02 | 403.05 | 410.08 |
| `/open-insurance/insurance-person/v2/insurance-person/e5447ee8-4624-49bd-b0e0-39e4492db7bf/claim` | 2 | 216.36 | 216.36 | 248.43 | 251.28 |
| `/open-insurance/insurance-person/v2/insurance-person/e5447ee8-4624-49bd-b0e0-39e4492db7bf/policy-info` | 2 | 183.79 | 183.79 | 191.03 | 191.68 |
| `/open-insurance/insurance-person/v2/insurance-person/e5447ee8-4624-49bd-b0e0-39e4492db7bf/premium` | 2 | 227.52 | 227.52 | 240.05 | 241.17 |
| `/request` | 2 | 138.29 | 138.29 | 155.88 | 157.44 |
| `/root-ca.pem` | 2 | 600.49 | 600.49 | 870.21 | 894.19 |
| `/token` | 4 | 310.31 | 318.16 | 475.18 | 484.01 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 98 | 96.5 | 112.5 | 112.9 |
| OPIN processing | 38 | 224.61 | 94.5 | 489.75 | 2137.54 |

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
| Client (test tool, total traffic) | 52956 | 138300 | 191256 |
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

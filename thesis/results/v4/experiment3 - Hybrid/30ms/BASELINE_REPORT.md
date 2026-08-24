# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T20:47:16.279056+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **179486 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5481.42 bytes** (max: 7596 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 303.79 | 303.79 | 553.49 | 575.69 |
| `/jwks` | 2 | 230.15 | 230.15 | 273.19 | 277.01 |
| `/open-insurance/consents/v3/consents` | 2 | 1131.54 | 1131.54 | 1869.42 | 1935.01 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:52b033d7-35c7-450b-94f0-36eb50ddc9d5` | 1 | 122.23 | 122.23 | 122.23 | 122.23 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:78e5dd31-9029-4a19-a7ad-125ee680a5ee` | 5 | 139.66 | 139.04 | 159.41 | 163.19 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 199.1 | 199.1 | 232.59 | 235.56 |
| `/open-insurance/insurance-person/v2/insurance-person/bfc73564-07a9-4081-a944-07d1e3985367/claim` | 2 | 165.49 | 165.49 | 177.51 | 178.58 |
| `/open-insurance/insurance-person/v2/insurance-person/bfc73564-07a9-4081-a944-07d1e3985367/policy-info` | 2 | 161.24 | 161.24 | 167.14 | 167.66 |
| `/open-insurance/insurance-person/v2/insurance-person/bfc73564-07a9-4081-a944-07d1e3985367/premium` | 2 | 162.08 | 162.08 | 167.81 | 168.32 |
| `/request` | 2 | 126.74 | 126.74 | 131.37 | 131.78 |
| `/root-ca.pem` | 2 | 1000.66 | 1000.66 | 1267.05 | 1290.73 |
| `/token` | 4 | 264.89 | 281.79 | 380.83 | 383.63 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 88.17 | 85.5 | 104.25 | 106.45 |
| OPIN processing | 38 | 159.32 | 66.5 | 405.3 | 1294.55 |

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
| AS | 19292 | 47253 | 66545 |
| Client (test tool, total traffic) | 52956 | 126530 | 179486 |
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
| 9 | 1812 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 5387 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 5780 |
| 16 | 5389 |
| 17 | 5387 |
| 18 | 1812 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

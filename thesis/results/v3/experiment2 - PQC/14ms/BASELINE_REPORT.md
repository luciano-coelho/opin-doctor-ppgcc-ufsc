# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T03:35:09.756491+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **184637 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5458.81 bytes** (max: 7246 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=pqc) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=pqc) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 19.59 | 19.59 | 19.71 | 19.72 |
| `/jwks` | 2 | 116.54 | 116.54 | 121.59 | 122.04 |
| `/open-insurance/consents/v3/consents` | 2 | 219.64 | 219.64 | 231.58 | 232.64 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:69a76f3d-82cc-487f-936d-d345d0ee6566` | 1 | 71.66 | 71.66 | 71.66 | 71.66 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:971ecacf-bd0e-4abb-8e6c-cf229af6d777` | 5 | 87.84 | 89.44 | 98.23 | 99.79 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 110.88 | 110.88 | 113.42 | 113.64 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/claim` | 2 | 132.41 | 132.41 | 135.07 | 135.3 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/policy-info` | 2 | 116.65 | 116.65 | 124.44 | 125.13 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/premium` | 2 | 110.7 | 110.7 | 118.25 | 118.92 |
| `/request` | 2 | 78.93 | 78.93 | 85.19 | 85.75 |
| `/root-ca.pem` | 2 | 78.45 | 78.45 | 82.86 | 83.25 |
| `/token` | 4 | 162.5 | 148.31 | 291.88 | 299.7 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 45.5 | 45.0 | 50.75 | 51.75 |
| OPIN processing | 38 | 76.42 | 46.0 | 227.0 | 299.42 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 137434 | 184637 |
| PKI/CRL | 16612 | 664 | 17276 |
| RS | 91252 | 4839 | 96091 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 4703 |
| 2 | 5284 |
| 3 | 5284 |
| 4 | 5284 |
| 5 | 5284 |
| 6 | 5283 |
| 7 | 4705 |
| 8 | 4703 |
| 9 | 7246 |
| 10 | 5268 |
| 11 | 5268 |
| 12 | 4703 |
| 13 | 5330 |
| 14 | 5330 |
| 15 | 5096 |
| 16 | 4705 |
| 17 | 4703 |
| 18 | 7246 |
| 19 | 4992 |
| 20 | 4992 |
| 21 | 5479 |
| 22 | 5479 |
| 23 | 7222 |
| 24 | 7222 |
| 25 | 5559 |
| 26 | 5559 |

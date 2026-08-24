# Baseline Report (Classical Cryptography)

Generated at: 2026-08-24T13:04:23.632422+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **191250 bytes**
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
| `/issuer-ca.pem` | 2 | 289.18 | 289.18 | 423.46 | 435.4 |
| `/jwks` | 2 | 64.31 | 64.31 | 72.15 | 72.85 |
| `/open-insurance/consents/v3/consents` | 2 | 964.55 | 964.55 | 1654.88 | 1716.24 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:5a036097-a422-437c-b704-21d7c57e2642` | 1 | 41.88 | 41.88 | 41.88 | 41.88 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:7be15281-9890-4b8b-92b0-842b1830c14a` | 5 | 96.44 | 71.74 | 192.01 | 208.57 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 163.4 | 163.4 | 237.0 | 243.54 |
| `/open-insurance/insurance-person/v2/insurance-person/3e465d15-d629-4605-99df-2aa41a6ce98b/claim` | 2 | 77.25 | 77.25 | 93.31 | 94.74 |
| `/open-insurance/insurance-person/v2/insurance-person/3e465d15-d629-4605-99df-2aa41a6ce98b/policy-info` | 2 | 66.1 | 66.1 | 69.58 | 69.89 |
| `/open-insurance/insurance-person/v2/insurance-person/3e465d15-d629-4605-99df-2aa41a6ce98b/premium` | 2 | 61.74 | 61.74 | 75.06 | 76.25 |
| `/request` | 2 | 34.01 | 34.01 | 43.02 | 43.82 |
| `/root-ca.pem` | 2 | 654.38 | 654.38 | 807.3 | 820.89 |
| `/token` | 4 | 100.14 | 115.02 | 149.3 | 150.92 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 27.17 | 29.0 | 39.5 | 40.7 |
| OPIN processing | 38 | 113.63 | 41.0 | 270.85 | 1204.2 |

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
| Client (test tool, total traffic) | 52956 | 138294 | 191250 |
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

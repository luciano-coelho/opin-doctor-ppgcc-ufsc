# Baseline Report (Classical Cryptography)

Generated at: 2026-08-24T23:23:59.282265+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **218738 bytes**
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
| `/issuer-ca.pem` | 2 | 35.3 | 35.3 | 35.73 | 35.76 |
| `/jwks` | 2 | 220.75 | 220.75 | 224.57 | 224.91 |
| `/open-insurance/consents/v3/consents` | 2 | 300.11 | 300.11 | 328.28 | 330.78 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:73a5e286-875a-4d6a-b143-0bde6f969441` | 5 | 124.46 | 129.76 | 130.93 | 131.1 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e5da34aa-2e95-4238-85c4-d34f0ee1ecca` | 1 | 122.77 | 122.77 | 122.77 | 122.77 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 154.43 | 154.43 | 154.91 | 154.96 |
| `/open-insurance/insurance-person/v2/insurance-person/619c39d4-b6bf-4a26-908d-6f77bb44b02f/claim` | 2 | 172.85 | 172.85 | 191.32 | 192.96 |
| `/open-insurance/insurance-person/v2/insurance-person/619c39d4-b6bf-4a26-908d-6f77bb44b02f/policy-info` | 2 | 152.85 | 152.85 | 156.22 | 156.52 |
| `/open-insurance/insurance-person/v2/insurance-person/619c39d4-b6bf-4a26-908d-6f77bb44b02f/premium` | 2 | 147.2 | 147.2 | 147.91 | 147.97 |
| `/request` | 2 | 115.03 | 115.03 | 118.6 | 118.92 |
| `/root-ca.pem` | 2 | 151.54 | 151.54 | 160.71 | 161.52 |
| `/token` | 4 | 267.78 | 256.43 | 436.48 | 442.32 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 98.17 | 93.5 | 118.25 | 122.85 |
| OPIN processing | 38 | 101.16 | 51.0 | 366.05 | 475.93 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 26064.5 | 25880.0 | 26502.25 | 26509.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 31058 | 47173 | 78231 |
| Client (test tool, total traffic) | 52676 | 166062 | 218738 |
| PKI/CRL | 37768 | 664 | 38432 |
| RS | 97236 | 4839 | 102075 |

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

# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:28:45.617676+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178009 bytes**
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
| `/issuer-ca.pem` | 2 | 301.71 | 301.71 | 550.49 | 572.61 |
| `/jwks` | 2 | 37.95 | 37.95 | 48.39 | 49.32 |
| `/open-insurance/consents/v3/consents` | 2 | 203.39 | 203.39 | 306.26 | 315.4 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:25848298-a8be-4316-89c3-21957ad6f251` | 5 | 39.74 | 40.03 | 48.73 | 49.34 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:b9e8a6fa-7da8-4e4f-ab37-13d96af98798` | 1 | 47.8 | 47.8 | 47.8 | 47.8 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 50.87 | 50.87 | 51.79 | 51.88 |
| `/open-insurance/insurance-person/v2/insurance-person/108c8c66-de08-46d5-a006-4ece682d5cb0/claim` | 2 | 51.56 | 51.56 | 63.96 | 65.06 |
| `/open-insurance/insurance-person/v2/insurance-person/108c8c66-de08-46d5-a006-4ece682d5cb0/policy-info` | 2 | 37.37 | 37.37 | 41.74 | 42.13 |
| `/open-insurance/insurance-person/v2/insurance-person/108c8c66-de08-46d5-a006-4ece682d5cb0/premium` | 2 | 28.29 | 28.29 | 29.5 | 29.61 |
| `/request` | 2 | 21.83 | 21.83 | 21.84 | 21.84 |
| `/root-ca.pem` | 2 | 586.1 | 586.1 | 1002.04 | 1039.02 |
| `/token` | 4 | 72.96 | 74.37 | 118.95 | 123.04 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **56**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 7 | 29.14 | 23.0 | 54.1 | 54.82 |
| OPIN processing | 56 | 31.46 | 17.0 | 116.25 | 162.6 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
3 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 13672.9 | 15440.0 | 16115.25 | 16127.85 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 130806 | 178009 |
| PKI/CRL | 10000 | 664 | 10664 |
| RS | 91236 | 4839 | 96075 |

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

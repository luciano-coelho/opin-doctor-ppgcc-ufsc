# Baseline Report (Classical Cryptography)

Generated at: 2026-08-14T21:55:01.870358+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178031 bytes**
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
| `/issuer-ca.pem` | 2 | 24.18 | 24.18 | 24.37 | 24.39 |
| `/jwks` | 2 | 30.78 | 30.78 | 31.28 | 31.33 |
| `/open-insurance/consents/v3/consents` | 2 | 65.86 | 65.86 | 66.31 | 66.35 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:46381f1d-01ea-4c82-aa10-b8145f564140` | 5 | 27.37 | 19.49 | 41.64 | 42.15 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:fca52398-1944-4150-8dfc-1db8b81ccdb5` | 1 | 16.24 | 16.24 | 16.24 | 16.24 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 60.19 | 60.19 | 67.21 | 67.84 |
| `/open-insurance/insurance-person/v2/insurance-person/a9496418-021d-4752-866b-bcb296f8af35/claim` | 2 | 54.62 | 54.62 | 57.62 | 57.89 |
| `/open-insurance/insurance-person/v2/insurance-person/a9496418-021d-4752-866b-bcb296f8af35/policy-info` | 2 | 39.4 | 39.4 | 41.37 | 41.54 |
| `/open-insurance/insurance-person/v2/insurance-person/a9496418-021d-4752-866b-bcb296f8af35/premium` | 2 | 35.89 | 35.89 | 36.82 | 36.91 |
| `/request` | 2 | 14.7 | 14.7 | 14.8 | 14.81 |
| `/root-ca.pem` | 2 | 2544.73 | 2544.73 | 4500.89 | 4674.77 |
| `/token` | 4 | 69.32 | 66.49 | 130.07 | 131.54 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 8 | 7.0 | 13.25 | 14.65 |
| OPIN processing | 38 | 22.21 | 11.0 | 57.75 | 119.93 |

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
| Client (test tool, total traffic) | 47203 | 130828 | 178031 |
| PKI/CRL | 10006 | 664 | 10670 |
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

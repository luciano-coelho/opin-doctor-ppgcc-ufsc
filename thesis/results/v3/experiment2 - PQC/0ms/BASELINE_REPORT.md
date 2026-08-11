# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T02:09:57.382241+00:00
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
| `/issuer-ca.pem` | 2 | 25.93 | 25.93 | 26.83 | 26.91 |
| `/jwks` | 2 | 49.99 | 49.99 | 54.32 | 54.7 |
| `/open-insurance/consents/v3/consents` | 2 | 126.75 | 126.75 | 155.54 | 158.1 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:930203bd-c743-4987-a05b-22d4eedb3b39` | 1 | 39.73 | 39.73 | 39.73 | 39.73 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:ed6578d4-17d2-4b2b-b4ed-9d642b20e3ac` | 5 | 37.29 | 38.75 | 40.96 | 41.0 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 56.18 | 56.18 | 59.28 | 59.55 |
| `/open-insurance/insurance-person/v2/insurance-person/f09d491f-9269-43fa-af4c-18600bfbca80/claim` | 2 | 51.88 | 51.88 | 60.12 | 60.86 |
| `/open-insurance/insurance-person/v2/insurance-person/f09d491f-9269-43fa-af4c-18600bfbca80/policy-info` | 2 | 35.32 | 35.32 | 35.37 | 35.38 |
| `/open-insurance/insurance-person/v2/insurance-person/f09d491f-9269-43fa-af4c-18600bfbca80/premium` | 2 | 43.64 | 43.64 | 45.08 | 45.21 |
| `/request` | 2 | 21.44 | 21.44 | 22.48 | 22.57 |
| `/root-ca.pem` | 2 | 257.45 | 257.45 | 385.77 | 397.17 |
| `/token` | 4 | 67.34 | 66.5 | 120.04 | 121.29 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 18.83 | 15.5 | 29.75 | 29.95 |
| OPIN processing | 38 | 32.87 | 23.5 | 108.05 | 124.08 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 15611.83 | 15500.0 | 15995.75 | 16075.95 |

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

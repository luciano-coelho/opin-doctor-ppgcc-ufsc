# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T02:00:11.784170+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 90.74 | 90.74 | 100.4 | 101.26 |
| `/jwks` | 2 | 1264.62 | 1264.62 | 1366.77 | 1375.85 |
| `/open-insurance/consents/v3/consents` | 2 | 1392.94 | 1392.94 | 1393.7 | 1393.77 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f6a57381-2910-449a-b9a2-d9ae6eaf522b` | 1 | 698.15 | 698.15 | 698.15 | 698.15 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f926640a-bccf-4d63-9de2-19a64dfad377` | 5 | 693.33 | 692.3 | 698.01 | 698.45 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 920.78 | 920.78 | 920.88 | 920.89 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/claim` | 2 | 931.19 | 931.19 | 933.01 | 933.17 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/policy-info` | 2 | 930.22 | 930.22 | 933.63 | 933.94 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/premium` | 2 | 928.86 | 928.86 | 933.84 | 934.28 |
| `/request` | 2 | 687.66 | 687.66 | 688.65 | 688.73 |
| `/root-ca.pem` | 2 | 1354.19 | 1354.19 | 1459.7 | 1469.08 |
| `/token` | 4 | 1151.32 | 1150.87 | 1843.83 | 1844.11 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 461.67 | 460.0 | 467.0 | 468.6 |
| OPIN processing | 38 | 513.11 | 238.0 | 1650.9 | 2561.2 |

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

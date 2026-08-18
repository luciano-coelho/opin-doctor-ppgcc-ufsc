# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T03:37:29.130361+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 231.45 | 231.45 | 232.03 | 232.08 |
| `/jwks` | 2 | 1283.36 | 1283.36 | 1380.93 | 1389.6 |
| `/open-insurance/consents/v3/consents` | 2 | 1482.6 | 1482.6 | 1483.86 | 1483.97 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:34c7f007-50e3-4e89-93f7-d82ba8f16b88` | 1 | 744.69 | 744.69 | 744.69 | 744.69 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:90186f01-5a15-4b25-a1cc-c2cb088f27ac` | 5 | 717.73 | 715.31 | 728.5 | 729.61 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 959.33 | 959.33 | 962.05 | 962.3 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/claim` | 2 | 1159.56 | 1159.56 | 1343.47 | 1359.81 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/policy-info` | 2 | 967.12 | 967.12 | 982.62 | 984.0 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/premium` | 2 | 1001.95 | 1001.95 | 1027.57 | 1029.85 |
| `/request` | 2 | 819.54 | 819.54 | 913.81 | 922.19 |
| `/root-ca.pem` | 2 | 931.91 | 931.91 | 935.17 | 935.46 |
| `/token` | 4 | 1188.2 | 1177.25 | 1925.64 | 1930.92 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 472.5 | 466.0 | 492.25 | 493.65 |
| OPIN processing | 38 | 545.05 | 251.0 | 1721.75 | 2765.41 |

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

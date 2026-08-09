# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T14:40:07.177093+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **112793 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **2950.5 bytes** (max: 7246 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=pqc) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=pqc) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 301.65 | 301.65 | 551.34 | 573.53 |
| `/jwks` | 2 | 1303.69 | 1303.69 | 1428.28 | 1439.36 |
| `/open-insurance/consents/v3/consents` | 2 | 1490.47 | 1490.47 | 1528.3 | 1531.67 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:b0cb10e5-8a71-451e-9082-88ce5bf6fa73` | 5 | 708.78 | 702.22 | 731.45 | 736.12 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:ef0d0a84-dd45-49f7-92ac-7ba446619975` | 1 | 700.13 | 700.13 | 700.13 | 700.13 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 949.36 | 949.36 | 957.85 | 958.6 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/claim` | 2 | 953.48 | 953.48 | 965.45 | 966.52 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/policy-info` | 2 | 942.02 | 942.02 | 944.99 | 945.25 |
| `/open-insurance/insurance-person/v2/insurance-person/b4a094be-878d-4e06-8074-d7a8152e2837/premium` | 2 | 936.99 | 936.99 | 937.47 | 937.51 |
| `/request` | 2 | 709.6 | 709.6 | 718.5 | 719.29 |
| `/root-ca.pem` | 2 | 441.84 | 441.84 | 695.59 | 718.15 |
| `/token` | 4 | 1178.77 | 1182.44 | 1882.97 | 1883.96 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 501.33 | 482.5 | 568.0 | 578.4 |
| OPIN processing | 38 | 534.08 | 247.0 | 1839.15 | 2596.6 |

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
| Client (test tool, total traffic) | 47203 | 65590 | 112793 |
| PKI/CRL | 10002 | 664 | 10666 |
| RS | 26018 | 4839 | 30857 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 4703 |
| 2 | 1208 |
| 3 | 1208 |
| 4 | 1208 |
| 5 | 1208 |
| 6 | 5283 |
| 7 | 4705 |
| 8 | 4703 |
| 9 | 7246 |
| 10 | 1192 |
| 11 | 1192 |
| 12 | 4703 |
| 13 | 1254 |
| 14 | 1254 |
| 15 | 5096 |
| 16 | 4705 |
| 17 | 4703 |
| 18 | 7246 |
| 19 | 916 |
| 20 | 916 |
| 21 | 1403 |
| 22 | 1403 |
| 23 | 3146 |
| 24 | 3146 |
| 25 | 1483 |
| 26 | 1483 |

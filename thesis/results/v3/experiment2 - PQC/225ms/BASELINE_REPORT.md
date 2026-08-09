# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:44:01.263511+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178011 bytes**
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
| `/issuer-ca.pem` | 2 | 320.08 | 320.08 | 584.34 | 607.83 |
| `/jwks` | 2 | 1265.25 | 1265.25 | 1368.44 | 1377.62 |
| `/open-insurance/consents/v3/consents` | 2 | 1406.03 | 1406.03 | 1410.99 | 1411.43 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:081919e5-0a2a-4acb-944e-048d57b114a1` | 1 | 697.98 | 697.98 | 697.98 | 697.98 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:7accb7ec-a0e1-4a14-8a8c-49173fd0a069` | 5 | 694.82 | 694.56 | 696.29 | 696.5 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 929.34 | 929.34 | 932.74 | 933.04 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/claim` | 2 | 931.14 | 931.14 | 935.88 | 936.31 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/policy-info` | 2 | 929.7 | 929.7 | 932.93 | 933.22 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/premium` | 2 | 925.6 | 925.6 | 926.23 | 926.29 |
| `/request` | 2 | 693.33 | 693.33 | 694.59 | 694.71 |
| `/root-ca.pem` | 2 | 814.55 | 814.55 | 1380.34 | 1430.63 |
| `/token` | 4 | 1164.97 | 1165.73 | 1867.59 | 1867.89 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 9 | 338.78 | 463.0 | 469.6 | 469.92 |
| OPIN processing | 58 | 625.34 | 244.0 | 1863.05 | 3117.83 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 13648.4 | 15440.0 | 16115.25 | 16127.85 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 130808 | 178011 |
| PKI/CRL | 10002 | 664 | 10666 |
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

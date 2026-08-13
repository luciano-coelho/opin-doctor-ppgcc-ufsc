# Baseline Report (Classical Cryptography)

Generated at: 2026-08-13T18:28:09.320134+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178027 bytes**
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
| `/issuer-ca.pem` | 2 | 301.13 | 301.13 | 549.41 | 571.48 |
| `/jwks` | 2 | 1265.62 | 1265.62 | 1378.57 | 1388.61 |
| `/open-insurance/consents/v3/consents` | 2 | 1403.55 | 1403.55 | 1406.39 | 1406.65 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:1cc3aecc-1b43-45a9-b9e3-19ff9828c9c6` | 5 | 697.68 | 694.39 | 707.08 | 707.67 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:fe5d121e-5afb-4f2b-8703-63b1d5991c59` | 1 | 692.02 | 692.02 | 692.02 | 692.02 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 926.07 | 926.07 | 926.48 | 926.52 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/claim` | 2 | 930.67 | 930.67 | 931.73 | 931.83 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/policy-info` | 2 | 928.02 | 928.02 | 929.67 | 929.82 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/premium` | 2 | 938.23 | 938.23 | 942.69 | 943.09 |
| `/request` | 2 | 694.99 | 694.99 | 699.73 | 700.15 |
| `/root-ca.pem` | 2 | 523.65 | 523.65 | 828.83 | 855.96 |
| `/token` | 4 | 1167.69 | 1159.11 | 1884.45 | 1889.52 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 458.33 | 458.0 | 461.25 | 461.85 |
| OPIN processing | 38 | 522.66 | 240.5 | 1687.75 | 2701.17 |

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
| Client (test tool, total traffic) | 47203 | 130824 | 178027 |
| PKI/CRL | 10002 | 664 | 10666 |
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

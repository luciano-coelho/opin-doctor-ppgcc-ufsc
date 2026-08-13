# Baseline Report (Classical Cryptography)

Generated at: 2026-08-13T18:25:23.642329+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 22.92 | 22.92 | 23.85 | 23.94 |
| `/jwks` | 2 | 105.1 | 105.1 | 113.25 | 113.98 |
| `/open-insurance/consents/v3/consents` | 2 | 194.76 | 194.76 | 197.53 | 197.77 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:780ef311-b0c4-480d-817f-6be0f20c3dd3` | 5 | 77.09 | 75.44 | 84.37 | 85.55 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:bc88a49d-6b2e-4a04-aea4-f21940254095` | 1 | 99.11 | 99.11 | 99.11 | 99.11 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 94.14 | 94.14 | 94.98 | 95.05 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/claim` | 2 | 100.3 | 100.3 | 102.1 | 102.26 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/policy-info` | 2 | 89.51 | 89.51 | 89.99 | 90.03 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/premium` | 2 | 100.31 | 100.31 | 101.87 | 102.01 |
| `/request` | 2 | 82.83 | 82.83 | 87.11 | 87.5 |
| `/root-ca.pem` | 2 | 122.96 | 122.96 | 128.45 | 128.94 |
| `/token` | 4 | 139.32 | 136.63 | 231.56 | 233.28 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 37.67 | 36.5 | 42.75 | 42.95 |
| OPIN processing | 38 | 60.61 | 35.0 | 202.1 | 243.61 |

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

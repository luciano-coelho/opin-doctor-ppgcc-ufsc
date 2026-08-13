# Baseline Report (Classical Cryptography)

Generated at: 2026-08-13T18:29:35.555646+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 308.87 | 308.87 | 563.38 | 586.01 |
| `/jwks` | 2 | 1777.9 | 1777.9 | 1922.87 | 1935.76 |
| `/open-insurance/consents/v3/consents` | 2 | 1974.83 | 1974.83 | 1977.18 | 1977.39 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:a39d3562-2c26-4f47-b0aa-d60afa7fea69` | 1 | 980.52 | 980.52 | 980.52 | 980.52 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f7829344-3b65-4bac-afd6-1c4e64286bf6` | 5 | 979.22 | 977.74 | 983.77 | 984.43 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1301.72 | 1301.72 | 1305.05 | 1305.35 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/claim` | 2 | 1306.46 | 1306.46 | 1308.71 | 1308.91 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/policy-info` | 2 | 1300.9 | 1300.9 | 1301.11 | 1301.12 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/premium` | 2 | 1299.47 | 1299.47 | 1301.24 | 1301.39 |
| `/request` | 2 | 973.1 | 973.1 | 974.27 | 974.38 |
| `/root-ca.pem` | 2 | 630.75 | 630.75 | 765.48 | 777.45 |
| `/token` | 4 | 1636.44 | 1638.4 | 2615.28 | 2615.41 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 648 | 648.5 | 649.75 | 649.95 |
| OPIN processing | 38 | 731.82 | 331.5 | 2337.2 | 3814.9 |

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

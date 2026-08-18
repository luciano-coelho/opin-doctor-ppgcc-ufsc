# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T03:36:22.870486+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 147.04 | 147.04 | 147.72 | 147.78 |
| `/jwks` | 2 | 811.31 | 811.31 | 878.81 | 884.82 |
| `/open-insurance/consents/v3/consents` | 2 | 955.24 | 955.24 | 962.12 | 962.73 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:96e317e0-8807-488a-ad08-b16dd8b89f31` | 1 | 459.46 | 459.46 | 459.46 | 459.46 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:c6e30175-095f-4fb5-9803-732d18ee70be` | 5 | 459.04 | 460.98 | 463.03 | 463.18 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 615.62 | 615.62 | 617.48 | 617.64 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/claim` | 2 | 633.5 | 633.5 | 655.84 | 657.82 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/policy-info` | 2 | 638.09 | 638.09 | 645.75 | 646.43 |
| `/open-insurance/insurance-person/v2/insurance-person/1a517b8c-3763-410a-b4b3-f90d98b7ab34/premium` | 2 | 618.98 | 618.98 | 621.59 | 621.82 |
| `/request` | 2 | 440.67 | 440.67 | 443.85 | 444.14 |
| `/root-ca.pem` | 2 | 588.68 | 588.68 | 589.54 | 589.62 |
| `/token` | 4 | 765.96 | 758.04 | 1243.27 | 1247.56 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 318 | 301.5 | 385.25 | 405.85 |
| OPIN processing | 38 | 348.11 | 169.0 | 1110.65 | 1743.03 |

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

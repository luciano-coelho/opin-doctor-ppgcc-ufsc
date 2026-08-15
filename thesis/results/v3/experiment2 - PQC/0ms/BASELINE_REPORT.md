# Baseline Report (Classical Cryptography)

Generated at: 2026-08-15T11:27:21.450571+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178025 bytes**
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
| `/issuer-ca.pem` | 2 | 305.65 | 305.65 | 558.22 | 580.67 |
| `/jwks` | 2 | 46.07 | 46.07 | 56.51 | 57.44 |
| `/open-insurance/consents/v3/consents` | 2 | 141.43 | 141.43 | 194.44 | 199.15 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f890e2e4-deda-47b6-a02b-c05c07c7487b` | 5 | 47.06 | 46.61 | 61.08 | 63.02 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:fb85e1fd-f62d-45cc-a920-474458a40d8a` | 1 | 35.1 | 35.1 | 35.1 | 35.1 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 48.92 | 48.92 | 49.22 | 49.25 |
| `/open-insurance/insurance-person/v2/insurance-person/f8157b90-c80c-47eb-9be5-11eba3f55aa0/claim` | 2 | 45.61 | 45.61 | 48.54 | 48.8 |
| `/open-insurance/insurance-person/v2/insurance-person/f8157b90-c80c-47eb-9be5-11eba3f55aa0/policy-info` | 2 | 41.16 | 41.16 | 44.29 | 44.57 |
| `/open-insurance/insurance-person/v2/insurance-person/f8157b90-c80c-47eb-9be5-11eba3f55aa0/premium` | 2 | 46.91 | 46.91 | 47.47 | 47.52 |
| `/request` | 2 | 22.26 | 22.26 | 26.29 | 26.65 |
| `/root-ca.pem` | 2 | 551.16 | 551.16 | 710.41 | 724.57 |
| `/token` | 4 | 73.38 | 68.54 | 132.11 | 136.48 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 10.17 | 9.5 | 15.75 | 15.95 |
| OPIN processing | 38 | 33.42 | 24.0 | 106.5 | 147.12 |

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
| Client (test tool, total traffic) | 47203 | 130822 | 178025 |
| PKI/CRL | 10000 | 664 | 10664 |
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

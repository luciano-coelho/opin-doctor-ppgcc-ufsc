# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T19:59:48.935497+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 4.34 | 4.34 | 6.04 | 6.2 |
| `/jwks` | 2 | 37.4 | 37.4 | 37.4 | 37.4 |
| `/open-insurance/consents/v3/consents` | 2 | 89.47 | 89.47 | 89.47 | 89.47 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:5db8d942-0767-4cf5-b8cf-5b8e8755f052` | 1 | 74.2 | 74.2 | 74.2 | 74.2 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:65615171-c6f6-424a-b502-07b0ccdae553` | 5 | 131.4 | 93.81 | 247.22 | 271.41 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 263.05 | 263.05 | 432.16 | 447.19 |
| `/open-insurance/insurance-person/v2/insurance-person/f8b86475-3859-44af-9f40-cd4edc2a896e/claim` | 2 | 138.19 | 138.19 | 162.77 | 164.95 |
| `/open-insurance/insurance-person/v2/insurance-person/f8b86475-3859-44af-9f40-cd4edc2a896e/policy-info` | 2 | 148.45 | 148.45 | 168.27 | 170.03 |
| `/open-insurance/insurance-person/v2/insurance-person/f8b86475-3859-44af-9f40-cd4edc2a896e/premium` | 2 | 151.91 | 151.91 | 174.38 | 176.38 |
| `/request` | 2 | 39.56 | 39.56 | 50.09 | 51.02 |
| `/root-ca.pem` | 2 | 33.59 | 33.59 | 42.91 | 43.74 |
| `/token` | 4 | 52.48 | 52.48 | 52.48 | 52.48 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 17.83 | 14.5 | 30.0 | 30.8 |
| OPIN processing | 38 | 199.53 | 81.5 | 429.0 | 2352.35 |

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

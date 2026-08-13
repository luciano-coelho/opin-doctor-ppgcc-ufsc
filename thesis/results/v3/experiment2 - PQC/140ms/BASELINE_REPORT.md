# Baseline Report (Classical Cryptography)

Generated at: 2026-08-13T18:27:00.421847+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178029 bytes**
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
| `/issuer-ca.pem` | 2 | 23.44 | 23.44 | 24.4 | 24.48 |
| `/jwks` | 2 | 792.41 | 792.41 | 858.04 | 863.87 |
| `/open-insurance/consents/v3/consents` | 2 | 897.02 | 897.02 | 899.2 | 899.39 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:9fc1fe75-0cf5-47a7-9812-20dedb0b2049` | 5 | 443.84 | 439.58 | 454.55 | 456.18 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:c28018fd-5ea6-4b6e-ba0d-e6a479e82214` | 1 | 439.43 | 439.43 | 439.43 | 439.43 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 591.57 | 591.57 | 593.91 | 594.12 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/claim` | 2 | 589.24 | 589.24 | 591.83 | 592.06 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/policy-info` | 2 | 597.61 | 597.61 | 608.12 | 609.05 |
| `/open-insurance/insurance-person/v2/insurance-person/9f2071e9-c08b-4768-9d57-1b17f2dab935/premium` | 2 | 585.44 | 585.44 | 586.05 | 586.1 |
| `/request` | 2 | 435.64 | 435.64 | 436.08 | 436.12 |
| `/root-ca.pem` | 2 | 400.36 | 400.36 | 648.54 | 670.6 |
| `/token` | 4 | 745.54 | 743.01 | 1195.26 | 1196.92 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 289.17 | 289.0 | 290.75 | 290.95 |
| OPIN processing | 38 | 333.26 | 156.0 | 1067.95 | 1701.39 |

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
| Client (test tool, total traffic) | 47203 | 130826 | 178029 |
| PKI/CRL | 10004 | 664 | 10668 |
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

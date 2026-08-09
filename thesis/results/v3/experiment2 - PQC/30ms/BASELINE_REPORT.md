# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:48:39.941834+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178009 bytes**
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
| `/issuer-ca.pem` | 2 | 311.17 | 311.17 | 567.58 | 590.37 |
| `/jwks` | 2 | 192.15 | 192.15 | 205.53 | 206.72 |
| `/open-insurance/consents/v3/consents` | 2 | 261.27 | 261.27 | 278.25 | 279.76 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:135c1bee-aee9-45ac-9a51-883b50065476` | 1 | 123.09 | 123.09 | 123.09 | 123.09 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:3a3a898f-c23f-49c8-93f6-66fad692e8c5` | 5 | 114.3 | 114.72 | 118.46 | 118.65 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 147.96 | 147.96 | 149.24 | 149.36 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/claim` | 2 | 154.63 | 154.63 | 159.6 | 160.04 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/policy-info` | 2 | 147.23 | 147.23 | 147.86 | 147.92 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/premium` | 2 | 148.04 | 148.04 | 150.64 | 150.87 |
| `/request` | 2 | 110.32 | 110.32 | 110.37 | 110.38 |
| `/root-ca.pem` | 2 | 388.24 | 388.24 | 647.16 | 670.18 |
| `/token` | 4 | 202.1 | 199.24 | 333.0 | 334.53 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 9 | 83.67 | 80.0 | 100.0 | 101.6 |
| OPIN processing | 58 | 97.6 | 44.5 | 301.05 | 459.72 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 13667.6 | 15440.0 | 16115.25 | 16127.85 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 130806 | 178009 |
| PKI/CRL | 10000 | 664 | 10664 |
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

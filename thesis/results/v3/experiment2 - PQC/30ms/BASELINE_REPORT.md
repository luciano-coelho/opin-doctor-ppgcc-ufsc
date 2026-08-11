# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T01:58:01.545975+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 344.46 | 344.46 | 561.37 | 580.65 |
| `/jwks` | 2 | 191.83 | 191.83 | 207.82 | 209.24 |
| `/open-insurance/consents/v3/consents` | 2 | 255.28 | 255.28 | 262.92 | 263.6 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:884f920a-7aac-48e3-92a5-bb36d2bbd34b` | 5 | 117.48 | 115.31 | 125.25 | 127.21 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:a8f8a229-f032-4feb-a4e1-df0d367a860f` | 1 | 117.94 | 117.94 | 117.94 | 117.94 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 169.95 | 169.95 | 173.99 | 174.35 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/claim` | 2 | 191.31 | 191.31 | 210.68 | 212.4 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/policy-info` | 2 | 157.62 | 157.62 | 161.66 | 162.02 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/premium` | 2 | 155.81 | 155.81 | 160.27 | 160.66 |
| `/request` | 2 | 109.3 | 109.3 | 110.43 | 110.53 |
| `/root-ca.pem` | 2 | 523.48 | 523.48 | 693.0 | 708.07 |
| `/token` | 4 | 200.58 | 195.24 | 331.93 | 334.87 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 76 | 75.0 | 79.25 | 79.85 |
| OPIN processing | 38 | 91.32 | 47.0 | 281.15 | 407.36 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 15611.83 | 15500.0 | 15995.75 | 16075.95 |

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

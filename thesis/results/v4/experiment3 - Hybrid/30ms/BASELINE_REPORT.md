# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T04:29:49.031549+00:00
Latency scenario: **30ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **144190 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **4123.88 bytes** (max: 7596 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 310.64 | 310.64 | 564.25 | 586.79 |
| `/jwks` | 2 | 232.03 | 232.03 | 276.29 | 280.22 |
| `/open-insurance/consents/v3/consents` | 2 | 1613.67 | 1613.67 | 2835.71 | 2944.34 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:41be80b7-703f-442e-8063-6b4b036c4901` | 1 | 120.35 | 120.35 | 120.35 | 120.35 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:a5511d5f-61ba-4931-95a9-68bbc039388f` | 5 | 179.85 | 162.17 | 295.77 | 320.18 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 201.4 | 201.4 | 246.39 | 250.39 |
| `/open-insurance/insurance-person/v2/insurance-person/e4487985-924a-4de8-9713-efb393ec062c/claim` | 2 | 168.13 | 168.13 | 170.33 | 170.53 |
| `/open-insurance/insurance-person/v2/insurance-person/e4487985-924a-4de8-9713-efb393ec062c/policy-info` | 2 | 163.85 | 163.85 | 171.16 | 171.81 |
| `/open-insurance/insurance-person/v2/insurance-person/e4487985-924a-4de8-9713-efb393ec062c/premium` | 2 | 164.62 | 164.62 | 176.16 | 177.19 |
| `/request` | 2 | 81.04 | 81.04 | 88.16 | 88.79 |
| `/root-ca.pem` | 2 | 546.74 | 546.74 | 802.26 | 824.98 |
| `/token` | 4 | 200.03 | 207.56 | 311.42 | 311.95 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 83.5 | 81.0 | 94.25 | 94.85 |
| OPIN processing | 38 | 191.66 | 63.5 | 573.15 | 1963.14 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25109.33 | 24991.0 | 25515.0 | 25602.2 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 19292 | 11955 | 31247 |
| Client (test tool, total traffic) | 17658 | 126532 | 144190 |
| PKI/CRL | 10004 | 704 | 10708 |
| RS | 97236 | 4999 | 102235 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 975 |
| 2 | 5658 |
| 3 | 5658 |
| 4 | 5658 |
| 5 | 5658 |
| 6 | 1555 |
| 7 | 977 |
| 8 | 975 |
| 9 | 1812 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 975 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 1368 |
| 16 | 977 |
| 17 | 975 |
| 18 | 1812 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

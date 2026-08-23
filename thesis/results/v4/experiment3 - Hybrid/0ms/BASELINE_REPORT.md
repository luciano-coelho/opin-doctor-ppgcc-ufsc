# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T04:25:16.494493+00:00
Latency scenario: **0ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **144186 bytes**
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
| `/issuer-ca.pem` | 2 | 303.73 | 303.73 | 557.63 | 580.2 |
| `/jwks` | 2 | 77.59 | 77.59 | 99.86 | 101.84 |
| `/open-insurance/consents/v3/consents` | 2 | 1315.42 | 1315.42 | 2423.24 | 2521.71 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:0459f531-7e34-4403-9e36-d26fe1ef4b31` | 5 | 64.71 | 61.48 | 114.5 | 122.93 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e66ca087-703f-4a54-8ec9-192c6b114bf8` | 1 | 22.26 | 22.26 | 22.26 | 22.26 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 97.77 | 97.77 | 143.49 | 147.55 |
| `/open-insurance/insurance-person/v2/insurance-person/de2997e9-ab2f-4218-bc6a-5295810051cc/claim` | 2 | 64.43 | 64.43 | 72.71 | 73.45 |
| `/open-insurance/insurance-person/v2/insurance-person/de2997e9-ab2f-4218-bc6a-5295810051cc/policy-info` | 2 | 47.61 | 47.61 | 52.3 | 52.72 |
| `/open-insurance/insurance-person/v2/insurance-person/de2997e9-ab2f-4218-bc6a-5295810051cc/premium` | 2 | 56.4 | 56.4 | 62.76 | 63.33 |
| `/request` | 2 | 21.02 | 21.02 | 29.09 | 29.81 |
| `/root-ca.pem` | 2 | 411.41 | 411.41 | 671.76 | 694.9 |
| `/token` | 4 | 63.03 | 61.42 | 111.06 | 117.14 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 19.67 | 17.5 | 28.5 | 29.7 |
| OPIN processing | 38 | 110.39 | 31.5 | 144.5 | 1627.81 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 19292 | 11955 | 31247 |
| Client (test tool, total traffic) | 17658 | 126528 | 144186 |
| PKI/CRL | 10000 | 704 | 10704 |
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

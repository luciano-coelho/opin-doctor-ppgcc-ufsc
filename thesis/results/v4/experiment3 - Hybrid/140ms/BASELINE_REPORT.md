# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T04:31:31.608123+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **144188 bytes**
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
| `/issuer-ca.pem` | 2 | 303.15 | 303.15 | 554.0 | 576.3 |
| `/jwks` | 2 | 945.28 | 945.28 | 1144.43 | 1162.13 |
| `/open-insurance/consents/v3/consents` | 2 | 1869.0 | 1869.0 | 2727.06 | 2803.34 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:637e95c2-32b9-4cca-af33-63c6310c18d8` | 5 | 459.45 | 454.07 | 486.16 | 491.89 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:d2083df9-da07-4e69-af0f-fe425ca96d66` | 1 | 442.39 | 442.39 | 442.39 | 442.39 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 623.53 | 623.53 | 652.64 | 655.23 |
| `/open-insurance/insurance-person/v2/insurance-person/82950e8a-0b42-44bf-9173-f2c90abca539/claim` | 2 | 600.34 | 600.34 | 608.53 | 609.26 |
| `/open-insurance/insurance-person/v2/insurance-person/82950e8a-0b42-44bf-9173-f2c90abca539/policy-info` | 2 | 596.22 | 596.22 | 600.1 | 600.44 |
| `/open-insurance/insurance-person/v2/insurance-person/82950e8a-0b42-44bf-9173-f2c90abca539/premium` | 2 | 618.02 | 618.02 | 631.24 | 632.41 |
| `/request` | 2 | 293.19 | 293.19 | 295.86 | 296.1 |
| `/root-ca.pem` | 2 | 441.38 | 441.38 | 712.54 | 736.64 |
| `/token` | 4 | 755.52 | 765.26 | 1199.13 | 1199.62 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 295.67 | 294.5 | 299.75 | 299.95 |
| OPIN processing | 38 | 396.66 | 164.0 | 1361.8 | 2137.03 |

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
| Client (test tool, total traffic) | 17658 | 126530 | 144188 |
| PKI/CRL | 10002 | 704 | 10706 |
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

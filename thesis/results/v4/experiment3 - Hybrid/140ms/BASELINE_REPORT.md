# Baseline Report (Classical Cryptography)

Generated at: 2026-08-24T13:11:28.761841+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **191252 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5933.96 bytes** (max: 7695 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 257.91 | 257.91 | 372.3 | 382.47 |
| `/jwks` | 2 | 989.0 | 989.0 | 1197.75 | 1216.31 |
| `/open-insurance/consents/v3/consents` | 2 | 3011.19 | 3011.19 | 4863.07 | 5027.68 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:36868e04-6386-4e12-8ab2-1456a787380a` | 5 | 508.68 | 501.29 | 552.81 | 553.01 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:87a6f6c4-d2d8-469d-92b6-c79b562f6ec0` | 1 | 457.34 | 457.34 | 457.34 | 457.34 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 684.29 | 684.29 | 747.34 | 752.94 |
| `/open-insurance/insurance-person/v2/insurance-person/7e28b563-ab00-4690-b7a5-8904aad051e1/claim` | 2 | 628.91 | 628.91 | 649.69 | 651.54 |
| `/open-insurance/insurance-person/v2/insurance-person/7e28b563-ab00-4690-b7a5-8904aad051e1/policy-info` | 2 | 594.51 | 594.51 | 599.25 | 599.67 |
| `/open-insurance/insurance-person/v2/insurance-person/7e28b563-ab00-4690-b7a5-8904aad051e1/premium` | 2 | 596.47 | 596.47 | 602.17 | 602.68 |
| `/request` | 2 | 461.89 | 461.89 | 474.74 | 475.89 |
| `/root-ca.pem` | 2 | 614.04 | 614.04 | 754.54 | 767.03 |
| `/token` | 4 | 1073.48 | 1100.2 | 1618.18 | 1635.48 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 323 | 321.0 | 339.75 | 342.35 |
| OPIN processing | 38 | 520.13 | 183.5 | 1606.8 | 3521.74 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25103.5 | 24991.0 | 25488.75 | 25568.95 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 31058 | 47253 | 78311 |
| Client (test tool, total traffic) | 52956 | 138296 | 191252 |
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
| 1 | 5387 |
| 2 | 5658 |
| 3 | 5658 |
| 4 | 5658 |
| 5 | 5658 |
| 6 | 5967 |
| 7 | 5389 |
| 8 | 5387 |
| 9 | 7695 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 5387 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 5780 |
| 16 | 5389 |
| 17 | 5387 |
| 18 | 7695 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

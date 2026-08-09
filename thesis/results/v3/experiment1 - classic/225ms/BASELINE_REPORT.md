# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T00:25:11.973428+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67866 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **1385.42 bytes** (max: 3146 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=classic) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=classic) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 319.35 | 319.35 | 584.8 | 608.39 |
| `/jwks` | 2 | 1266.23 | 1266.23 | 1374.23 | 1383.83 |
| `/open-insurance/consents/v3/consents` | 2 | 1402.04 | 1402.04 | 1404.87 | 1405.12 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e0825cd1-d354-4bf5-82ea-3e8a7ceec10c` | 1 | 690.56 | 690.56 | 690.56 | 690.56 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e8336664-1af1-440a-9d17-b7eceadaf5ed` | 5 | 694.73 | 694.78 | 697.77 | 698.26 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 918.5 | 918.5 | 918.76 | 918.78 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/claim` | 2 | 921.15 | 921.15 | 922.85 | 923.0 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/policy-info` | 2 | 923.18 | 923.18 | 925.84 | 926.07 |
| `/open-insurance/insurance-person/v2/insurance-person/f8cf8a6a-5796-429f-9bee-473d0ceb2f10/premium` | 2 | 925.39 | 925.39 | 927.63 | 927.83 |
| `/request` | 2 | 461.55 | 461.55 | 462.4 | 462.47 |
| `/root-ca.pem` | 2 | 4310.36 | 4310.36 | 7396.25 | 7670.55 |
| `/token` | 4 | 1212.26 | 1263.64 | 1856.97 | 1859.32 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **70**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 20 | 414 | 452.0 | 473.4 | 479.48 |
| OPIN processing | 70 | 552.01 | 243.0 | 1770.05 | 3063.47 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
2 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 22 | 10777.86 | 11455.0 | 12089.1 | 12091.0 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11955 | 26143 |
| Client (test tool, total traffic) | 17658 | 50208 | 67866 |
| PKI/CRL | 10002 | 704 | 10706 |
| RS | 26018 | 4999 | 31017 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM | RSA | sig | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 3 | xQLs45xYyJr1omHs4qnB2rhes9qNFHIHQ5YPQKVJliM | RSA | sig | 256 |
| 4 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 975 |
| 2 | 1208 |
| 3 | 1208 |
| 4 | 1208 |
| 5 | 1208 |
| 6 | 1555 |
| 7 | 977 |
| 8 | 975 |
| 9 | 1812 |
| 10 | 1192 |
| 11 | 1192 |
| 12 | 975 |
| 13 | 1254 |
| 14 | 1254 |
| 15 | 1368 |
| 16 | 977 |
| 17 | 975 |
| 18 | 1812 |
| 19 | 916 |
| 20 | 916 |
| 21 | 1403 |
| 22 | 1403 |
| 23 | 3146 |
| 24 | 3146 |
| 25 | 1483 |
| 26 | 1483 |

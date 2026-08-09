# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:38:28.821149+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67586 bytes**
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
| `/issuer-ca.pem` | 2 | 384.97 | 384.97 | 655.36 | 679.39 |
| `/jwks` | 2 | 1276.74 | 1276.74 | 1375.84 | 1384.65 |
| `/open-insurance/consents/v3/consents` | 2 | 1532.07 | 1532.07 | 1645.47 | 1655.55 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:170a69ec-6b02-4fe2-9897-1e89c2162367` | 1 | 697.58 | 697.58 | 697.58 | 697.58 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:6e4b728e-817e-4484-a72e-c44d93807b17` | 5 | 696.46 | 695.15 | 701.22 | 701.91 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 926.96 | 926.96 | 928.46 | 928.59 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/claim` | 2 | 929.21 | 929.21 | 932.1 | 932.36 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/policy-info` | 2 | 927.96 | 927.96 | 931.67 | 932.01 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/premium` | 2 | 924.21 | 924.21 | 925.88 | 926.03 |
| `/request` | 2 | 462.32 | 462.32 | 462.65 | 462.68 |
| `/root-ca.pem` | 2 | 442.74 | 442.74 | 703.79 | 726.99 |
| `/token` | 4 | 1157.08 | 1154.99 | 1854.96 | 1856.6 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 9 | 334.22 | 467.0 | 481.2 | 481.84 |
| OPIN processing | 58 | 625.17 | 240.0 | 1864.05 | 3133.91 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 10225.8 | 10398.5 | 10723.45 | 10823.89 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11875 | 26063 |
| Client (test tool, total traffic) | 17378 | 50208 | 67586 |
| PKI/CRL | 10002 | 664 | 10666 |
| RS | 26018 | 4839 | 30857 |

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

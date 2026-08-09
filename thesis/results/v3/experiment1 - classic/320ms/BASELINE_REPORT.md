# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:39:37.670774+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 310.08 | 310.08 | 569.66 | 592.74 |
| `/jwks` | 2 | 1787.25 | 1787.25 | 1930.85 | 1943.62 |
| `/open-insurance/consents/v3/consents` | 2 | 1971.13 | 1971.13 | 1972.71 | 1972.86 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:3b361261-0438-4a52-b8f4-7678ea136a3d` | 1 | 980.88 | 980.88 | 980.88 | 980.88 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:3df7247b-46a5-4e0f-a3bc-06249a3fda4b` | 5 | 978.94 | 979.52 | 980.7 | 980.82 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1303.24 | 1303.24 | 1305.15 | 1305.31 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/claim` | 2 | 1308.69 | 1308.69 | 1309.71 | 1309.8 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/policy-info` | 2 | 1304.78 | 1304.78 | 1308.06 | 1308.35 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/premium` | 2 | 1317.19 | 1317.19 | 1334.41 | 1335.94 |
| `/request` | 2 | 651.89 | 651.89 | 653.32 | 653.44 |
| `/root-ca.pem` | 2 | 633.33 | 633.33 | 1066.66 | 1105.18 |
| `/token` | 4 | 1626.09 | 1625.51 | 2603.47 | 2603.89 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 9 | 457.22 | 656.0 | 661.4 | 662.68 |
| OPIN processing | 58 | 874.6 | 333.5 | 2627.5 | 4357.75 |

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

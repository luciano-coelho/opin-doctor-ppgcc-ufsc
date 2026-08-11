# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T01:55:16.611131+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67602 bytes**
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
| `/issuer-ca.pem` | 2 | 363.09 | 363.09 | 608.95 | 630.8 |
| `/jwks` | 2 | 1795.81 | 1795.81 | 1937.94 | 1950.57 |
| `/open-insurance/consents/v3/consents` | 2 | 1967.87 | 1967.87 | 1970.51 | 1970.74 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:29923cac-26ea-487a-b16f-511cf80c40e9` | 5 | 977.61 | 978.12 | 979.71 | 979.92 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e5bee10b-d12b-4305-9ed6-b85724feefc2` | 1 | 981.36 | 981.36 | 981.36 | 981.36 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1302.88 | 1302.88 | 1303.15 | 1303.17 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/claim` | 2 | 1306.55 | 1306.55 | 1307.51 | 1307.59 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/policy-info` | 2 | 1302.25 | 1302.25 | 1304.98 | 1305.22 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/premium` | 2 | 1304.17 | 1304.17 | 1304.77 | 1304.82 |
| `/request` | 2 | 653.03 | 653.03 | 653.84 | 653.91 |
| `/root-ca.pem` | 2 | 1066.08 | 1066.08 | 1819.56 | 1886.54 |
| `/token` | 4 | 1711.07 | 1631.5 | 2884.95 | 2923.71 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 10 | 660.8 | 659.5 | 666.55 | 666.91 |
| OPIN processing | 58 | 850.98 | 332.0 | 2637.75 | 4343.75 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 10225.8 | 10398.5 | 10725.7 | 10824.34 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11875 | 26063 |
| Client (test tool, total traffic) | 17378 | 50224 | 67602 |
| PKI/CRL | 10002 | 664 | 10666 |
| RS | 26034 | 4839 | 30873 |

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

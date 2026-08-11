# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T01:53:54.456717+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 318.52 | 318.52 | 582.96 | 606.46 |
| `/jwks` | 2 | 1269.49 | 1269.49 | 1371.45 | 1380.51 |
| `/open-insurance/consents/v3/consents` | 2 | 1402.03 | 1402.03 | 1406.41 | 1406.8 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:05eb7314-14d9-412f-8142-0866650c1f2f` | 1 | 691.76 | 691.76 | 691.76 | 691.76 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:d14c08bd-0741-426c-b240-7462d5d36eb1` | 5 | 694.53 | 695.13 | 696.23 | 696.3 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 927.14 | 927.14 | 929.14 | 929.32 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/claim` | 2 | 941.09 | 941.09 | 955.35 | 956.62 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/policy-info` | 2 | 928.68 | 928.68 | 933.18 | 933.58 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/premium` | 2 | 931.11 | 931.11 | 931.7 | 931.76 |
| `/request` | 2 | 459.8 | 459.8 | 460.53 | 460.6 |
| `/root-ca.pem` | 2 | 482.94 | 482.94 | 813.46 | 842.84 |
| `/token` | 4 | 1158.02 | 1156.75 | 1851.52 | 1852.21 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 10 | 452 | 468.0 | 475.55 | 475.91 |
| OPIN processing | 58 | 612.02 | 238.5 | 1852.05 | 3157.85 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 10267.7 | 10398.5 | 10908.15 | 11042.43 |

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

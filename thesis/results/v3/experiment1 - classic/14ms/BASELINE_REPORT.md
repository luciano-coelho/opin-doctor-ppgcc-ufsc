# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T01:51:35.773343+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67606 bytes**
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
| `/issuer-ca.pem` | 2 | 54.31 | 54.31 | 76.16 | 78.1 |
| `/jwks` | 2 | 102.83 | 102.83 | 109.29 | 109.86 |
| `/open-insurance/consents/v3/consents` | 2 | 147.37 | 147.37 | 152.09 | 152.51 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:762486ff-a733-4de0-81fc-92a2e8152efb` | 5 | 61.02 | 59.0 | 68.91 | 70.74 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:875da183-7004-468c-879d-c5efd46bbe37` | 1 | 59.79 | 59.79 | 59.79 | 59.79 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 80.04 | 80.04 | 81.3 | 81.41 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/claim` | 2 | 84.8 | 84.8 | 85.79 | 85.87 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/policy-info` | 2 | 80.27 | 80.27 | 81.21 | 81.29 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/premium` | 2 | 82.52 | 82.52 | 83.53 | 83.62 |
| `/request` | 2 | 37.56 | 37.56 | 38.38 | 38.46 |
| `/root-ca.pem` | 2 | 205.21 | 205.21 | 248.62 | 252.48 |
| `/token` | 4 | 100.12 | 96.35 | 169.18 | 171.12 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 8 | 43 | 43.0 | 57.8 | 61.16 |
| OPIN processing | 58 | 54.22 | 27.5 | 172.15 | 275.66 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 9 | 10229.67 | 10381.0 | 10827.0 | 10895.8 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 14188 | 11875 | 26063 |
| Client (test tool, total traffic) | 17378 | 50228 | 67606 |
| PKI/CRL | 10006 | 664 | 10670 |
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

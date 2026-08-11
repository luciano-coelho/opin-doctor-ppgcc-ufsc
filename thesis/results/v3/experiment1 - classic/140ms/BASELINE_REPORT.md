# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T01:52:55.856505+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 53.24 | 53.24 | 76.0 | 78.02 |
| `/jwks` | 2 | 806.64 | 806.64 | 864.48 | 869.63 |
| `/open-insurance/consents/v3/consents` | 2 | 909.81 | 909.81 | 911.42 | 911.56 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:7fffaeb8-1d50-4636-8403-0056bdf46d87` | 1 | 439.64 | 439.64 | 439.64 | 439.64 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:88facb40-8440-400b-81fc-8ae6e7464f35` | 5 | 477.65 | 485.17 | 527.63 | 535.33 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 588.75 | 588.75 | 590.94 | 591.14 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/claim` | 2 | 592.2 | 592.2 | 592.57 | 592.61 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/policy-info` | 2 | 590.16 | 590.16 | 595.21 | 595.65 |
| `/open-insurance/insurance-person/v2/insurance-person/30741b50-febb-400b-b78d-3e31adc0dd47/premium` | 2 | 587.7 | 587.7 | 591.9 | 592.27 |
| `/request` | 2 | 303.72 | 303.72 | 315.23 | 316.25 |
| `/root-ca.pem` | 2 | 240.58 | 240.58 | 314.08 | 320.62 |
| `/token` | 4 | 733.82 | 733.85 | 1172.58 | 1172.62 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 16 | 298.81 | 297.5 | 310.5 | 311.7 |
| OPIN processing | 58 | 382.72 | 159.0 | 1164.95 | 1945.59 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 16 | 10410.25 | 10511.0 | 10905.75 | 11041.95 |

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

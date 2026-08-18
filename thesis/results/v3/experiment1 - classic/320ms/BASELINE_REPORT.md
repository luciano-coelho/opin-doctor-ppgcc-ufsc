# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T03:32:41.352648+00:00
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
| `/issuer-ca.pem` | 2 | 312.48 | 312.48 | 572.11 | 595.19 |
| `/jwks` | 2 | 1857.77 | 1857.77 | 2039.45 | 2055.6 |
| `/open-insurance/consents/v3/consents` | 2 | 2041.27 | 2041.27 | 2057.31 | 2058.73 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:6774348d-b2f9-4050-acdb-7ad45940bb30` | 1 | 993.84 | 993.84 | 993.84 | 993.84 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:88690a29-11e3-4d34-9c63-6feb204a1531` | 5 | 1002.4 | 997.2 | 1018.44 | 1020.44 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1344.4 | 1344.4 | 1347.84 | 1348.15 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/claim` | 2 | 1353.1 | 1353.1 | 1362.01 | 1362.8 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/policy-info` | 2 | 1323.52 | 1323.52 | 1327.02 | 1327.33 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/premium` | 2 | 1383.38 | 1383.38 | 1430.95 | 1435.18 |
| `/request` | 2 | 660.1 | 660.1 | 663.82 | 664.15 |
| `/root-ca.pem` | 2 | 520.5 | 520.5 | 886.34 | 918.86 |
| `/token` | 4 | 1660.04 | 1658.57 | 2660.92 | 2662.27 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 758.17 | 675.5 | 1005.75 | 1070.75 |
| OPIN processing | 38 | 733.55 | 344.5 | 2393.55 | 3872.62 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 9969.5 | 9785.0 | 10407.25 | 10414.25 |

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

# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:36:37.051447+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **67584 bytes**
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
| `/issuer-ca.pem` | 2 | 304.85 | 304.85 | 556.37 | 578.73 |
| `/jwks` | 2 | 120.59 | 120.59 | 142.7 | 144.67 |
| `/open-insurance/consents/v3/consents` | 2 | 162.07 | 162.07 | 185.15 | 187.21 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:540af6d7-666e-4b44-85c6-87f0c1caeac0` | 5 | 67.91 | 68.86 | 73.06 | 73.8 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:8dd63c4a-56d3-405f-9801-f23b35863be6` | 1 | 63.27 | 63.27 | 63.27 | 63.27 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 97.69 | 97.69 | 101.76 | 102.12 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/claim` | 2 | 88.63 | 88.63 | 90.25 | 90.39 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/policy-info` | 2 | 102.95 | 102.95 | 104.33 | 104.46 |
| `/open-insurance/insurance-person/v2/insurance-person/18bb0b70-0974-4c89-8948-40edcac85baa/premium` | 2 | 112.63 | 112.63 | 119.88 | 120.53 |
| `/request` | 2 | 39.06 | 39.06 | 39.42 | 39.45 |
| `/root-ca.pem` | 2 | 459.72 | 459.72 | 773.23 | 801.1 |
| `/token` | 4 | 109.43 | 106.91 | 184.13 | 185.61 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 9 | 51.56 | 54.0 | 60.6 | 62.52 |
| OPIN processing | 58 | 56.41 | 30.0 | 167.0 | 258.3 |

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
| Client (test tool, total traffic) | 17378 | 50206 | 67584 |
| PKI/CRL | 10000 | 664 | 10664 |
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

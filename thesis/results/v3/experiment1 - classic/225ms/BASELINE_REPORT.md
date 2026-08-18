# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T03:31:35.244256+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 22.37 | 22.37 | 22.6 | 22.62 |
| `/jwks` | 2 | 1488.98 | 1488.98 | 1494.75 | 1495.26 |
| `/open-insurance/consents/v3/consents` | 2 | 1487.95 | 1487.95 | 1501.33 | 1502.52 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:bbfc5896-3629-4255-80b3-c21d83363755` | 1 | 723.65 | 723.65 | 723.65 | 723.65 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:f67498be-a8ad-4525-8550-5dd202c13199` | 5 | 717.6 | 720.27 | 723.99 | 724.58 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 959.2 | 959.2 | 965.87 | 966.46 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/claim` | 2 | 964.45 | 964.45 | 975.41 | 976.38 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/policy-info` | 2 | 952.36 | 952.36 | 955.97 | 956.29 |
| `/open-insurance/insurance-person/v2/insurance-person/949ceb2c-6c00-4bb2-b0b6-69c972c3f075/premium` | 2 | 958.42 | 958.42 | 960.01 | 960.15 |
| `/request` | 2 | 474.73 | 474.73 | 481.03 | 481.59 |
| `/root-ca.pem` | 2 | 100.69 | 100.69 | 109.88 | 110.7 |
| `/token` | 4 | 1221.72 | 1231.48 | 1947.11 | 1951.67 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 506.33 | 502.0 | 539.5 | 544.7 |
| OPIN processing | 38 | 531.5 | 252.0 | 1720.65 | 2810.35 |

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

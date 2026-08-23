# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T04:33:21.546180+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **144188 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **4123.88 bytes** (max: 7596 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 304.32 | 304.32 | 555.15 | 577.45 |
| `/jwks` | 2 | 1505.31 | 1505.31 | 1810.45 | 1837.57 |
| `/open-insurance/consents/v3/consents` | 2 | 2325.89 | 2325.89 | 3121.85 | 3192.6 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:722646c9-73a2-455f-9b15-f67c922c1a8e` | 5 | 710.38 | 705.83 | 726.98 | 729.61 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:e064c22e-9e1e-4dd5-a0e7-224c1f81b0d3` | 1 | 716.17 | 716.17 | 716.17 | 716.17 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 970.42 | 970.42 | 1002.98 | 1005.88 |
| `/open-insurance/insurance-person/v2/insurance-person/704cb21a-091a-42c6-bcf8-291c78462e57/claim` | 2 | 933.71 | 933.71 | 938.02 | 938.4 |
| `/open-insurance/insurance-person/v2/insurance-person/704cb21a-091a-42c6-bcf8-291c78462e57/policy-info` | 2 | 937.34 | 937.34 | 941.43 | 941.8 |
| `/open-insurance/insurance-person/v2/insurance-person/704cb21a-091a-42c6-bcf8-291c78462e57/premium` | 2 | 946.32 | 946.32 | 947.84 | 947.97 |
| `/request` | 2 | 466.56 | 466.56 | 470.25 | 470.58 |
| `/root-ca.pem` | 2 | 530.48 | 530.48 | 892.03 | 924.17 |
| `/token` | 4 | 1178.6 | 1187.31 | 1876.98 | 1877.55 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 470.83 | 469.5 | 477.5 | 479.5 |
| OPIN processing | 38 | 579.61 | 250.0 | 1926.7 | 2834.02 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25176.17 | 24991.0 | 25615.25 | 25622.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 19292 | 11955 | 31247 |
| Client (test tool, total traffic) | 17658 | 126530 | 144188 |
| PKI/CRL | 10002 | 704 | 10706 |
| RS | 97236 | 4999 | 102235 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 975 |
| 2 | 5658 |
| 3 | 5658 |
| 4 | 5658 |
| 5 | 5658 |
| 6 | 1555 |
| 7 | 977 |
| 8 | 975 |
| 9 | 1812 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 975 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 1368 |
| 16 | 977 |
| 17 | 975 |
| 18 | 1812 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

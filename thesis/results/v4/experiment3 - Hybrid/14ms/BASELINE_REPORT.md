# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T20:45:52.874627+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **179486 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5481.42 bytes** (max: 7596 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 300.59 | 300.59 | 551.45 | 573.75 |
| `/jwks` | 2 | 154.53 | 154.53 | 168.5 | 169.74 |
| `/open-insurance/consents/v3/consents` | 2 | 1503.56 | 1503.56 | 2620.44 | 2719.71 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:6e9e5017-ac84-4fbb-9f78-060ac2729e67` | 1 | 86.48 | 86.48 | 86.48 | 86.48 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:a6406af3-8be9-4951-9ef6-05ff01ba512b` | 5 | 100.96 | 89.1 | 136.94 | 144.95 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 153.46 | 153.46 | 188.71 | 191.85 |
| `/open-insurance/insurance-person/v2/insurance-person/58123b30-cf97-4938-9318-2c701b3361c9/claim` | 2 | 137.45 | 137.45 | 143.55 | 144.09 |
| `/open-insurance/insurance-person/v2/insurance-person/58123b30-cf97-4938-9318-2c701b3361c9/policy-info` | 2 | 118.7 | 118.7 | 123.49 | 123.91 |
| `/open-insurance/insurance-person/v2/insurance-person/58123b30-cf97-4938-9318-2c701b3361c9/premium` | 2 | 133.36 | 133.36 | 140.64 | 141.29 |
| `/request` | 2 | 77.18 | 77.18 | 86.44 | 87.27 |
| `/root-ca.pem` | 2 | 547.35 | 547.35 | 919.05 | 952.09 |
| `/token` | 4 | 193.16 | 197.63 | 301.11 | 308.85 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 63.67 | 65.0 | 76.0 | 76.8 |
| OPIN processing | 38 | 154.11 | 54.0 | 303.65 | 1735.5 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 25103.5 | 24991.0 | 25488.75 | 25568.95 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 19292 | 47253 | 66545 |
| Client (test tool, total traffic) | 52956 | 126530 | 179486 |
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
| 1 | 5387 |
| 2 | 5658 |
| 3 | 5658 |
| 4 | 5658 |
| 5 | 5658 |
| 6 | 5967 |
| 7 | 5389 |
| 8 | 5387 |
| 9 | 1812 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 5387 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 5780 |
| 16 | 5389 |
| 17 | 5387 |
| 18 | 1812 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

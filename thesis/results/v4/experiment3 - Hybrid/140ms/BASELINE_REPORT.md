# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T20:48:56.814225+00:00
Latency scenario: **140ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 303.88 | 303.88 | 555.94 | 578.34 |
| `/jwks` | 2 | 946.2 | 946.2 | 1134.0 | 1150.7 |
| `/open-insurance/consents/v3/consents` | 2 | 1711.59 | 1711.59 | 2431.34 | 2495.32 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:172ef180-5195-49fd-b70b-5934efc647a5` | 5 | 468.68 | 469.23 | 479.05 | 480.22 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:8db511f5-f934-4878-ab0c-c594c02ec94a` | 1 | 439.86 | 439.86 | 439.86 | 439.86 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 631.41 | 631.41 | 643.59 | 644.68 |
| `/open-insurance/insurance-person/v2/insurance-person/5a0ba502-8787-4a87-9dbc-3a585cc0e333/claim` | 2 | 608.48 | 608.48 | 619.78 | 620.79 |
| `/open-insurance/insurance-person/v2/insurance-person/5a0ba502-8787-4a87-9dbc-3a585cc0e333/policy-info` | 2 | 594.14 | 594.14 | 601.12 | 601.74 |
| `/open-insurance/insurance-person/v2/insurance-person/5a0ba502-8787-4a87-9dbc-3a585cc0e333/premium` | 2 | 598.8 | 598.8 | 605.22 | 605.79 |
| `/request` | 2 | 445.92 | 445.92 | 452.59 | 453.19 |
| `/root-ca.pem` | 2 | 2824.61 | 2824.61 | 5210.58 | 5422.67 |
| `/token` | 4 | 933.31 | 971.58 | 1351.86 | 1353.49 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 301.83 | 302.5 | 305.75 | 305.95 |
| OPIN processing | 38 | 413 | 172.0 | 1292.2 | 1989.84 |

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

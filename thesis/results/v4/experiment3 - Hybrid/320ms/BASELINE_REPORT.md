# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T20:54:12.166121+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 311.2 | 311.2 | 564.85 | 587.39 |
| `/jwks` | 2 | 2118.5 | 2118.5 | 2550.88 | 2589.31 |
| `/open-insurance/consents/v3/consents` | 2 | 2909.04 | 2909.04 | 3741.78 | 3815.8 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:77c68d07-c059-4d56-80de-458e2c47880c` | 5 | 997.67 | 991.2 | 1012.95 | 1015.03 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:a1a10fd9-a238-4f09-b35f-1e2556f0164a` | 1 | 989.75 | 989.75 | 989.75 | 989.75 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1372.26 | 1372.26 | 1423.69 | 1428.26 |
| `/open-insurance/insurance-person/v2/insurance-person/b73b8210-c007-4f63-b936-c023bef5cdb6/claim` | 2 | 1325.56 | 1325.56 | 1326.59 | 1326.68 |
| `/open-insurance/insurance-person/v2/insurance-person/b73b8210-c007-4f63-b936-c023bef5cdb6/policy-info` | 2 | 1331.44 | 1331.44 | 1334.18 | 1334.42 |
| `/open-insurance/insurance-person/v2/insurance-person/b73b8210-c007-4f63-b936-c023bef5cdb6/premium` | 2 | 1335.93 | 1335.93 | 1356.45 | 1358.27 |
| `/request` | 2 | 979.74 | 979.74 | 984.44 | 984.86 |
| `/root-ca.pem` | 2 | 439.54 | 439.54 | 698.21 | 721.2 |
| `/token` | 4 | 1987.43 | 1992.08 | 2985.94 | 2987.97 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 660.83 | 660.5 | 666.5 | 666.9 |
| OPIN processing | 38 | 844.16 | 351.0 | 2653.8 | 3914.55 |

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

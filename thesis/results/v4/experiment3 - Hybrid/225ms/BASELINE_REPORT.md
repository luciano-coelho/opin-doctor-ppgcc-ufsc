# Baseline Report (Classical Cryptography)

Generated at: 2026-08-24T13:13:25.176700+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **191252 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5933.96 bytes** (max: 7695 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=hybrid) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=hybrid) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 305.6 | 305.6 | 554.68 | 576.82 |
| `/jwks` | 2 | 1516.5 | 1516.5 | 1851.5 | 1881.28 |
| `/open-insurance/consents/v3/consents` | 2 | 2715.4 | 2715.4 | 3842.46 | 3942.64 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:1a3f0f11-4b72-4c49-885a-63b40bedd137` | 5 | 720.94 | 709.8 | 750.08 | 754.71 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:764beb20-7e15-4465-bc85-dc291217053a` | 1 | 703.37 | 703.37 | 703.37 | 703.37 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 997.31 | 997.31 | 1049.12 | 1053.73 |
| `/open-insurance/insurance-person/v2/insurance-person/a20ece78-7741-4327-8419-aaaa15f44b18/claim` | 2 | 959.58 | 959.58 | 967.22 | 967.9 |
| `/open-insurance/insurance-person/v2/insurance-person/a20ece78-7741-4327-8419-aaaa15f44b18/policy-info` | 2 | 940.67 | 940.67 | 950.44 | 951.31 |
| `/open-insurance/insurance-person/v2/insurance-person/a20ece78-7741-4327-8419-aaaa15f44b18/premium` | 2 | 936.56 | 936.56 | 945.57 | 946.37 |
| `/request` | 2 | 709.2 | 709.2 | 715.48 | 716.03 |
| `/root-ca.pem` | 2 | 447.32 | 447.32 | 704.68 | 727.56 |
| `/token` | 4 | 1439.42 | 1438.27 | 2179.31 | 2188.0 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 481.33 | 478.5 | 505.25 | 510.65 |
| OPIN processing | 38 | 652.16 | 264.0 | 2082.7 | 3265.62 |

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
| AS | 31058 | 47253 | 78311 |
| Client (test tool, total traffic) | 52956 | 138296 | 191252 |
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
| 9 | 7695 |
| 10 | 5642 |
| 11 | 5642 |
| 12 | 5387 |
| 13 | 5704 |
| 14 | 5704 |
| 15 | 5780 |
| 16 | 5389 |
| 17 | 5387 |
| 18 | 7695 |
| 19 | 5366 |
| 20 | 5366 |
| 21 | 5853 |
| 22 | 5853 |
| 23 | 7596 |
| 24 | 7596 |
| 25 | 5933 |
| 26 | 5933 |

# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:58:14.251495+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178009 bytes**
- Total HTTP requests: **28**
- JWTs found: **26**
- Average JWT size: **5458.81 bytes** (max: 7246 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| opin_flow (crypto_profile=pqc) | opin-consent-api-status-test-v3 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |
| opin_flow (crypto_profile=pqc) | person_api_core_test-module_v2.0.0 (direct, no Conformance Suite) | FINISHED | PASSED | `(no raw CS log -- see baseline_metrics.json for the captured calls)` |

## Latency per endpoint (client-side, Conformance Suite)

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 2 | 317.37 | 317.37 | 581.27 | 604.73 |
| `/jwks` | 2 | 107.7 | 107.7 | 115.47 | 116.17 |
| `/open-insurance/consents/v3/consents` | 2 | 156.98 | 156.98 | 160.58 | 160.9 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:3cb9335b-0ea4-4ce1-bd47-d1601f5ef001` | 5 | 60.51 | 58.64 | 65.02 | 65.45 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:850d1e7e-7955-48a1-aeba-d65017f34664` | 1 | 65.2 | 65.2 | 65.2 | 65.2 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 85.63 | 85.63 | 90.14 | 90.54 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/claim` | 2 | 84.44 | 84.44 | 85.71 | 85.83 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/policy-info` | 2 | 81.48 | 81.48 | 82.16 | 82.22 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/premium` | 2 | 77.73 | 77.73 | 78.95 | 79.06 |
| `/request` | 2 | 64.04 | 64.04 | 66.93 | 67.18 |
| `/root-ca.pem` | 2 | 475.07 | 475.07 | 811.0 | 840.86 |
| `/token` | 4 | 120.6 | 115.99 | 203.9 | 206.41 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 46 | 47.0 | 55.0 | 56.6 |
| OPIN processing | 38 | 53.66 | 28.0 | 169.15 | 238.03 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 15684.5 | 15500.0 | 16122.25 | 16129.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 130806 | 178009 |
| PKI/CRL | 10000 | 664 | 10664 |
| RS | 91236 | 4839 | 96075 |

## JWK sizes found (isolated public key material)

| # | kid | kty | use | Size (bytes) |
|---|---|---|---|---|
| 1 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |
| 2 | AsnNSC2ubVrgn8NjhuQgItg7nTpgjuieL1G8R3HsG4k | RSA | enc | 256 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 4703 |
| 2 | 5284 |
| 3 | 5284 |
| 4 | 5284 |
| 5 | 5284 |
| 6 | 5283 |
| 7 | 4705 |
| 8 | 4703 |
| 9 | 7246 |
| 10 | 5268 |
| 11 | 5268 |
| 12 | 4703 |
| 13 | 5330 |
| 14 | 5330 |
| 15 | 5096 |
| 16 | 4705 |
| 17 | 4703 |
| 18 | 7246 |
| 19 | 4992 |
| 20 | 4992 |
| 21 | 5479 |
| 22 | 5479 |
| 23 | 7222 |
| 24 | 7222 |
| 25 | 5559 |
| 26 | 5559 |

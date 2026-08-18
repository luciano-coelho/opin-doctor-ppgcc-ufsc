# Baseline Report (Classical Cryptography)

Generated at: 2026-08-18T02:22:13.463479+00:00
Latency scenario: **14ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **184637 bytes**
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
| `/issuer-ca.pem` | 2 | 21.76 | 21.76 | 22.85 | 22.95 |
| `/jwks` | 2 | 109.48 | 109.48 | 118.69 | 119.5 |
| `/open-insurance/consents/v3/consents` | 2 | 223.03 | 223.03 | 236.79 | 238.01 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:061d9bd8-5f8b-432a-9612-3657d4a28a17` | 5 | 90.85 | 92.96 | 99.03 | 100.16 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:0a3b556c-15ef-4e52-ae02-cdd2fdab063d` | 1 | 77.84 | 77.84 | 77.84 | 77.84 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 153.55 | 153.55 | 172.34 | 174.01 |
| `/open-insurance/insurance-person/v2/insurance-person/10866a5e-74d9-4134-85d3-24b1ff63ea05/claim` | 2 | 160.77 | 160.77 | 176.07 | 177.43 |
| `/open-insurance/insurance-person/v2/insurance-person/10866a5e-74d9-4134-85d3-24b1ff63ea05/policy-info` | 2 | 171.6 | 171.6 | 175.94 | 176.32 |
| `/open-insurance/insurance-person/v2/insurance-person/10866a5e-74d9-4134-85d3-24b1ff63ea05/premium` | 2 | 156.24 | 156.24 | 180.09 | 182.21 |
| `/request` | 2 | 77.22 | 77.22 | 83.07 | 83.59 |
| `/root-ca.pem` | 2 | 95.52 | 95.52 | 107.15 | 108.18 |
| `/token` | 4 | 180.14 | 173.32 | 298.52 | 303.09 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 40.83 | 41.5 | 45.25 | 45.85 |
| OPIN processing | 38 | 82.5 | 50.0 | 251.95 | 298.9 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 19940.5 | 19756.0 | 20378.25 | 20385.25 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 137434 | 184637 |
| PKI/CRL | 16612 | 664 | 17276 |
| RS | 91252 | 4839 | 96091 |

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

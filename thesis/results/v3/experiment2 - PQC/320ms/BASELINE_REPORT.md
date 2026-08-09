# Baseline Report (Classical Cryptography)

Generated at: 2026-08-09T04:46:23.197068+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178011 bytes**
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
| `/issuer-ca.pem` | 2 | 353.48 | 353.48 | 557.29 | 575.4 |
| `/jwks` | 2 | 1783.98 | 1783.98 | 1930.46 | 1943.48 |
| `/open-insurance/consents/v3/consents` | 2 | 1972.33 | 1972.33 | 1973.47 | 1973.57 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:09fe5642-52e6-4ba6-aa58-b7fe99f726d6` | 5 | 978.89 | 977.92 | 984.92 | 986.14 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:70d6a9f5-8ad7-44d1-85aa-a98c0c5bb7d6` | 1 | 985.63 | 985.63 | 985.63 | 985.63 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1308.09 | 1308.09 | 1309.13 | 1309.22 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/claim` | 2 | 1306.46 | 1306.46 | 1310.11 | 1310.44 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/policy-info` | 2 | 1304.48 | 1304.48 | 1304.88 | 1304.92 |
| `/open-insurance/insurance-person/v2/insurance-person/0f6da2a1-0733-43ee-828e-ae46ef434933/premium` | 2 | 1303.43 | 1303.43 | 1306.04 | 1306.27 |
| `/request` | 2 | 981.83 | 981.83 | 985.79 | 986.15 |
| `/root-ca.pem` | 2 | 458.41 | 458.41 | 690.88 | 711.54 |
| `/token` | 4 | 1634.95 | 1633.13 | 2619.57 | 2620.61 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **58**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 9 | 466.33 | 650.0 | 672.0 | 680.0 |
| OPIN processing | 58 | 871.84 | 337.0 | 2602.9 | 4351.32 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
1 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 10 | 13648.4 | 15440.0 | 16115.25 | 16127.85 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 130808 | 178011 |
| PKI/CRL | 10002 | 664 | 10666 |
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

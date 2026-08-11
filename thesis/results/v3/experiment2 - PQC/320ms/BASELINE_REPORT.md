# Baseline Report (Classical Cryptography)

Generated at: 2026-08-11T02:01:32.884339+00:00
Latency scenario: **320ms** (see thesis/scripts/set_latency.sh)

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **178027 bytes**
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
| `/issuer-ca.pem` | 2 | 328.31 | 328.31 | 573.57 | 595.37 |
| `/jwks` | 2 | 1787.25 | 1787.25 | 1931.94 | 1944.8 |
| `/open-insurance/consents/v3/consents` | 2 | 1964.08 | 1964.08 | 1965.18 | 1965.28 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:23868e72-ee2f-44c3-9e99-e6d29b6ef350` | 1 | 980.66 | 980.66 | 980.66 | 980.66 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:4e0744d1-be87-4466-9061-ac7a408e06c0` | 5 | 979.53 | 978.79 | 983.87 | 984.53 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 1305.03 | 1305.03 | 1306.01 | 1306.1 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/claim` | 2 | 1307.77 | 1307.77 | 1309.44 | 1309.59 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/policy-info` | 2 | 1308.71 | 1308.71 | 1313.61 | 1314.04 |
| `/open-insurance/insurance-person/v2/insurance-person/0089a23e-23ec-49c0-aa0b-42861b9b43b5/premium` | 2 | 1306.6 | 1306.6 | 1308.92 | 1309.13 |
| `/request` | 2 | 971.7 | 971.7 | 971.74 | 971.74 |
| `/root-ca.pem` | 2 | 771.26 | 771.26 | 959.84 | 976.6 |
| `/token` | 4 | 1629.56 | 1625.47 | 2614.76 | 2616.98 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 652.5 | 651.5 | 656.5 | 656.9 |
| OPIN processing | 38 | 742.03 | 333.0 | 2367.7 | 3615.15 |

Note: for keep-alive connections, only the first request on a given connection pays the handshake cost -- every subsequent request on that same connection reports the same (already-past) handshake timestamps, which is expected.
0 handshake duration sample(s) discarded as outliers (> 3x this scenario's median; see filter_handshake_outliers).

### mTLS handshake size (wire bytes)

Total bytes read+written at the raw TCP level during the handshake (ClientHello through Finished), counted below crypto/tls so it captures the actual negotiated messages regardless of algorithm -- see countingConn in mock-service-os/mock_mtls/main.go. This is the number expected to grow substantially under PQC (larger KEM public keys/ciphertexts and signatures), unlike clientCertBytes above which is only one certificate.

| Requests | Mean (bytes) | P50 (bytes) | P95 (bytes) | P99 (bytes) |
|---|---|---|---|---|
| 6 | 15611.83 | 15500.0 | 15995.75 | 16075.95 |

0 handshake byte-size sample(s) discarded as outliers (same filter/reasoning as the duration outliers above).

## Bytes by participant

**Client** is the Conformance Suite itself (the OPIN client in this test harness) -- it is one of the two parties on every call this table is built from, so its sent+received always equals the scenario's total bytes exchanged by construction, not a measurement of a separate category. AS/RS/Directory/PKI-CRL are the actual breakdown: who specifically the client was talking to on each call, and they sum to the same total.

| Participant | Sent (bytes) | Received (bytes) | Total (bytes) |
|---|---|---|---|
| AS | 29570 | 41700 | 71270 |
| Client (test tool, total traffic) | 47203 | 130824 | 178027 |
| PKI/CRL | 10002 | 664 | 10666 |
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

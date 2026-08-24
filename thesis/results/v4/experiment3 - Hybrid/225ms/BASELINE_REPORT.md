# Baseline Report (Classical Cryptography)

Generated at: 2026-08-23T20:50:47.125911+00:00
Latency scenario: **225ms** (see thesis/scripts/set_latency.sh)

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
| `/issuer-ca.pem` | 2 | 308.79 | 308.79 | 563.45 | 586.09 |
| `/jwks` | 2 | 1503.44 | 1503.44 | 1810.44 | 1837.73 |
| `/open-insurance/consents/v3/consents` | 2 | 2383.14 | 2383.14 | 3247.41 | 3324.23 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:21e57c6a-af1f-4007-b01d-89664d7269aa` | 1 | 698.25 | 698.25 | 698.25 | 698.25 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:d49b199e-b36c-47ab-b29b-0334477c1f3b` | 5 | 717.94 | 714.62 | 736.84 | 740.17 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 958.71 | 958.71 | 985.8 | 988.2 |
| `/open-insurance/insurance-person/v2/insurance-person/39b27a19-e797-4c28-a391-96d710d52b60/claim` | 2 | 942.45 | 942.45 | 947.85 | 948.33 |
| `/open-insurance/insurance-person/v2/insurance-person/39b27a19-e797-4c28-a391-96d710d52b60/policy-info` | 2 | 937.51 | 937.51 | 945.45 | 946.15 |
| `/open-insurance/insurance-person/v2/insurance-person/39b27a19-e797-4c28-a391-96d710d52b60/premium` | 2 | 934.3 | 934.3 | 939.27 | 939.71 |
| `/request` | 2 | 720.07 | 720.07 | 736.52 | 737.98 |
| `/root-ca.pem` | 2 | 433.4 | 433.4 | 698.91 | 722.51 |
| `/token` | 4 | 1413.38 | 1425.5 | 2113.68 | 2114.41 |

## mTLS handshake vs. OPIN processing time (gateway-side)

Requests logged by the gateway in this run: **38**

| Phase | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| mTLS handshake | 6 | 474.83 | 472.0 | 484.75 | 486.55 |
| OPIN processing | 38 | 620.39 | 252.0 | 1938.7 | 2898.87 |

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

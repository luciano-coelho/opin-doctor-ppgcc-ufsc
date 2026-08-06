# Baseline Report (Classical Cryptography)

Generated at: 2026-07-20T23:10:55.827154+00:00

## Overview

- Total bytes exchanged across the full flow (classical OPINsize): **72886 bytes**
- Total HTTP requests: **38**
- JWTs found: **14**
- Average JWT size: **1144.57 bytes** (max: 1810 bytes)

## Modules run

| Plan | Module | Status | Result | Log |
|---|---|---|---|---|
| consents_v3 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `consents_v3__opin-consents_api_preflight_test-module_v3_20260720T230743Z.json` |
| consents_v3 | opin-consent-api-status-test-v3 | FINISHED | PASSED | `consents_v3__opin-consent-api-status-test-v3_20260720T231014Z.json` |
| person_v2 | opin-consents_api_preflight_test-module_v3 | FINISHED | FAILED | `person_v2__opin-consents_api_preflight_test-module_v3_20260720T231020Z.json` |
| person_v2 | person_api_core_test-module_v2.0.0 | FINISHED | FAILED | `person_v2__person_api_core_test-module_v2.0.0_20260720T231055Z.json` |

## Latency per endpoint

| Endpoint | Requests | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |
|---|---|---|---|---|---|
| `/issuer-ca.pem` | 4 | 464.75 | 532.5 | 676.0 | 676.0 |
| `/jwks` | 2 | 14 | 14.0 | 14.9 | 14.98 |
| `/open-insurance/consents/v3/consents` | 2 | 81 | 81.0 | 108.0 | 110.4 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:6a883bca-5140-4faf-9da6-3919abd6bb65` | 5 | 78.2 | 62.0 | 106.6 | 106.92 |
| `/open-insurance/consents/v3/consents/urn:raidiaminsurance:998e495b-7094-4cf3-9231-e41269fbf846` | 1 | 27 | 27 | 27 | 27 |
| `/open-insurance/insurance-person/v2/insurance-person` | 2 | 166.5 | 166.5 | 241.65 | 248.33 |
| `/open-insurance/insurance-person/v2/insurance-person/be6bfdfa-ced2-495e-815d-c8e5e9dff22b/claim` | 2 | 96 | 96.0 | 122.1 | 124.42 |
| `/open-insurance/insurance-person/v2/insurance-person/be6bfdfa-ced2-495e-815d-c8e5e9dff22b/policy-info` | 2 | 124 | 124.0 | 125.8 | 125.96 |
| `/open-insurance/insurance-person/v2/insurance-person/be6bfdfa-ced2-495e-815d-c8e5e9dff22b/premium` | 2 | 83 | 83.0 | 91.1 | 91.82 |
| `/organisations/76b370e3-def5-4798-8b6a-915cb5d6dd74/softwarestatements/c5eb976f-8a98-4eda-a773-a8a0fa286322/assertion` | 2 | 34.5 | 34.5 | 50.25 | 51.65 |
| `/request` | 2 | 44.5 | 44.5 | 62.05 | 63.61 |
| `/root-ca.pem` | 4 | 598 | 620.5 | 949.1 | 969.02 |
| `/token` | 8 | 48.88 | 29.5 | 116.2 | 124.04 |

## JWT sizes found

| # | Size (bytes) |
|---|---|
| 1 | 953 |
| 2 | 950 |
| 3 | 953 |
| 4 | 1549 |
| 5 | 937 |
| 6 | 953 |
| 7 | 1810 |
| 8 | 953 |
| 9 | 950 |
| 10 | 953 |
| 11 | 1363 |
| 12 | 937 |
| 13 | 953 |
| 14 | 1810 |

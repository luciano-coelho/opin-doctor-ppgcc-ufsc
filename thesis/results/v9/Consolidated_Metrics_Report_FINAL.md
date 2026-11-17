# Consolidated Experimental Metrics Report: real multi-region AWS campaign

**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, Hybrid, and Control -- real network, single window, 320 executions**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

## 1. Campaign parameters

- **Profiles:** 4 (Classic, PQC, Control, Hybrid) x **8 real routes** (3 installations: `sa-east-1`, `us-east-1`, `ap-northeast-1`).
- **N per cell:** 10 official executions + 5 discarded warm-ups (never read by any statistic below).
- **Total:** 320/320 official executions, 160 warm-ups, 32/32 dedicated captures (0 failures).
- **Single window:** `2026-11-15T17:37:59.293861+00:00` -> `2026-11-16T00:06:40.838058+00:00`.
- **Randomization seed:** `20261107` (profile order recorded per route in the manifest itself -- `route_orders`).
- **cost_stop:** `None` (never triggered).

## 2. Size results: the OPINsize equation

Equation for this research line (extension of Schardong et al., Eq. 3.1, with the PKI term):

```
OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x PKI_bytes
```

### 2.1 Total OPINsize per profile (signature+raw-key variant) and ratio against Classic

Central comparison of this thesis: **Classic / PQC / Hybrid**. The Control profile is for support/diagnostics -- reported separately right below, never mixed into this table.

| Profile | OPINsize (bytes) | Ratio vs. Classic |
|---|---:|---:|
| Classic | 34.584,00 | 1,00x |
| PQC | 263.048 | 7,61x |
| Hybrid | 293.332,00 | 8,48x |

**Hybrid minus PQC: 30.284,00 bytes** (11,51% more than pure PQC).

**Control profile, separate (not included in the central Classic/PQC/Hybrid comparison above):**

| Profile | OPINsize (bytes) | Ratio vs. Classic |
|---|---:|---:|
| Control | 249.138 | 7,20x |

### 2.2 OPINsize by term, by profile, N counts

| Term | N per execution | Classic | PQC | Hybrid |
|---|---:|---:|---:|---:|
| mTLS (handshake) | 6 | 18.750 | 129.636 | 144.474 |
| JWT (signature only) | 28 | 7.168 | 92.652 | 99.820 |
| JWK (raw key) | 4 | 1.536 | 8.320 | 9.856 |
| PKI (CA certificates) | 4 | 7.130,00 | 32.440 | 39.182,00 |
| **OPINsize (total)** | 44 calls/execution | **34.584,00** | **263.048** | **293.332,00** |

**Control profile, by term (separate):**

| Term | N per execution | Control |
|---|---:|---:|
| mTLS (handshake) | 6 | 101.694 |
| JWT (signature only) | 28 | 99.820 |
| JWK (raw key) | 4 | 9.856 |
| PKI (CA certificates) | 4 | 37.768 |
| **OPINsize (total)** | 44 calls/execution | **249.138** |

**On the "PKI" label:** the 4 calls of this term are, confirmed in code (`thesis/scripts/opinsize_v9_oficial.py`, `PKI_ENDPOINTS = {"/root-ca.pem", "/issuer-ca.pem"}`), retrieval of the CA certificates (root + issuer, once per sub-flow) -- **never** a revocation list (CRL). The pipeline's internal field is named `term_pki_crl` due to an inherited naming convention, not because a CRL is actually fetched; this report uses "PKI (CA certificates)", which describes what the actual call does.

**Verification external to the measurement pipeline (mTLS term, non-circular):** `evaluate_criteria.expected_handshake_bytes()` derives the expected number of handshake bytes per connection (inbound+outbound) from the actual DER size of the certificates actually deployed in `certs/generated/` -- a source INDEPENDENT of the campaign's traffic capture. Run live, now, by this script (not copied from a previous report):

| Profile | Expected (actual certificate DER, bytes/connection) | Measured (campaign, bytes/connection) | Match? |
|---|---:|---:|---|
| Classic | 3.125 | 3.125 | YES |
| PQC | 21.606 | 21.606 | YES |
| Hybrid | 24.079 | 24.079 | YES |

**Control profile, separate:** expected 16.949 bytes/connection, measured 16.949 bytes/connection -- match? YES.

### 2.3 Verification status by term

| Term | Verification source | Result |
|---|---|---|
| mTLS | Independent of the measurement pipeline (actual DER of deployed certificates, Section 2.2 above) | Matches exactly, 4/4 profiles |
| JWT | Independent of the measurement pipeline (signature size per specification -- RSA-2048/ML-DSA-65, FIPS 204) | Matches exactly, 4/4 profiles, 0 residual (see Section 2.4) |
| JWK | Independent of the measurement pipeline (public key size per specification + actual composition of each call) | Matches exactly, 4/4 profiles (see Section 2.4) |
| PKI | Independent of the measurement pipeline (actual size of the CA files on disk + HTTP framing overhead, both confirmed in code) | Matches exactly, 4/4 profiles (see Section 2.4) |

### 2.4 Verification by specification (independent of the pipeline), by term and by profile

#### 2.4.1 JWT -- signature bytes per specification

Specification: RSA-2048 PS256 signature = 256B; pure ML-DSA-65 signature (FIPS 204) = 3309B; dual-signed constructions (Hybrid/Control) sum both. Confirmed in the actual data (2.240 samples/profile) that `classical_sig_bytes`/`pq_sig_bytes` are CONSTANT across the entire dataset, with no variation at all -- never assumed from the specification without checking.

| Profile | Constructions per execution (actual count) | Expected sum/execution (specification) | Expected average (w/ pipeline rounding) | Expected term | Measured term | Difference |
|---|---|---:|---:|---:|---:|---:|
| Classic | classic_only=26, jwe=2 | 7.168 | 256,00 | 7.168,00 | 7.168 | 0,00 |
| PQC | jwe=2, pqc_pure=26 | 92.652 | 3.309,00 | 92.652,00 | 92.652 | 0,00 |
| Hybrid | jwe=2, payload_extension=24, strong_nesting=2 | 99.820 | 3.565,00 | 99.820,00 | 99.820 | 0,00 |

**Control profile, separate:**

| Profile | Constructions per execution (actual count) | Expected sum/execution (specification) | Expected average (w/ pipeline rounding) | Expected term | Measured term | Difference |
|---|---|---:|---:|---:|---:|---:|
| Control | jwe=2, payload_extension=24, strong_nesting=2 | 99.820 | 3.565,00 | 99.820,00 | 99.820 | 0,00 |

**Rounding mechanism, confirmed in code, not assumed:** `thesis/scripts/opinsize_v9_oficial.py` computes `jwt_sig_avg = round(statistics.mean(jwt_sig_sizes_all), 2)` and only then `term_jwt = round(n_jwt * jwt_sig_avg, 2)` -- the per-token average is rounded to 2 decimal places BEFORE being multiplied by N_JWT=28. Before the id_token correction (Section 9), the 2 `jwe` tokens/execution entered the average as 0 bytes, diluting it and producing a fractional residual of up to ±0,16 byte between the exact sum per specification and the measured term (e.g., previous revisions of this report). **After the correction, this residual disappears across all 4 profiles** -- the table above confirms this: with the id_token's internal signature equal to that of every other token of the same profile, the 28 per-execution values become uniform, the average is exact, and the "Difference" column closes at 0,00 for all 4 profiles, with no residual left to explain.

**Contribution of JWE tokens -- correction of Decision 147 (see Decision 216 and its Amendment in `DECISIONS.md`):** the original Decision 147 assumed that a `jwe` token (the encrypted id_token) contributed **0 bytes** to this term because "it is never signed via JWS". That premise was wrong: the id_token has a real internal signature, which the client verifies after decrypting the JWE (`opin_flow.py`) -- the real-time capture pipeline simply never extracted it, because it never decrypts the JWE during the campaign's actual execution. Measured now for real, in an actual local execution (never the AWS fleet -- `thesis/results/v9/opinsize_correction_id_token/`), this internal signature is worth 256B in Classic, 3309B in PQC, and 3565B in Hybrid/Control -- the same 2 `jwe` tokens per execution, across all 4 profiles, now contribute this value to the JWT term instead of 0, and all OPINsize figures in this report already reflect this correction.

#### 2.4.2 JWK -- public key size per specification

Specification (raw key, no envelope): RSA-2048 (modulus) = 256B; ML-DSA-65 (FIPS 204) = 1952B.

| Profile | Key per specification (bytes) | Actual measured average (4 calls) | Difference vs. specification | Confirmed actual composition |
|---|---:|---:|---:|---|
| Classic | 256 | 384 | +128 | RSA:256+RSA:256 / RSA:256 / RSA:256+RSA:256 / RSA:256 |
| PQC | 1.952 | 2.080 | +128 | AKP:1952+RSA:256 / AKP:1952 / AKP:1952+RSA:256 / AKP:1952 |
| Hybrid | 2.208 | 2.464 | +256 | HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 |

**Control profile, separate:**

| Profile | Key per specification (bytes) | Actual measured average (4 calls) | Difference vs. specification | Confirmed actual composition |
|---|---:|---:|---:|---|
| Control | 2.208 | 2.464 | +256 | HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 / HYBRID:2208+RSA:256 |

**What makes up the increment over the pure key, confirmed call by call (not speculated):** of the 4 actual `/jwks` calls per execution, **half (2 of 4)** carry a SECOND JWK entry in addition to the profile's own signing key -- for Classic/PQC, this second entry is always a 256B RSA-2048 key with `use="enc"` (the `id_token` encryption public key, JWE, classical across all profiles by already-stated design); the other 2 of 4 calls carry no second entry. This gives an average of +128B/call for Classic and PQC -- but **it is not a fixed 128B increment on each individual call**, it is a 256B increment on exactly half the calls. For Hybrid/Control, **all 4 calls** carry a second 256B entry -- 2 of them the same `use="enc"` key as Classic/PQC, and the other 2 a **duplicated** RSA `use="sig"` entry (the same `kid` as the classical half of the composite key, republished separately for a standard JWKS consumer that performs discovery by `kid`+`alg` without support for the hybrid key). This is why Hybrid/Control adds 256B on ALL 4 calls, not 128B -- the table above confirms this with the actual composition of each of the 4 calls of a real execution.

#### 2.4.3 PKI -- actual CA file size + HTTP framing overhead

| Profile | File(s) served (root / issuer) | Actual PEM (root+issuer, bytes) | HTTP framing | Expected (PEM+framing) | Measured | Difference |
|---|---|---:|---|---:|---:|---:|
| Classic | root_ca_rsa2048.crt / issuer_ca_rsa2048.crt | 1.679+1.692 | content-length (+97B) | 7.130,00 | 7.130,00 | 0,00 |
| PQC | root_ca_pqc.crt / issuer_ca_pqc.crt | 8.001+8.013 | chunked (+103B) | 32.440,00 | 32.440 | 0,00 |
| Hybrid | root_ca_rsa2048.crt+root_ca_pqc.crt / issuer_ca_rsa2048.crt+issuer_ca_pqc.crt | 9.680+9.705 | chunked (+103B) | 39.182,00 | 39.182,00 | 0,00 |

**Control profile, separate:**

| Profile | File(s) served (root / issuer) | Actual PEM (root+issuer, bytes) | HTTP framing | Expected (PEM+framing) | Measured | Difference |
|---|---|---:|---|---:|---:|---:|
| Control | root_ca_hybrid.crt / issuer_ca_hybrid.crt | 9.337+9.341 | chunked (+103B) | 37.768,00 | 37.768 | 0,00 |

**Sources, cited with file:line (not estimated):** the CA file served per profile comes from `realCAFilesForProfile` (`thesis/results/v9/integration/gateway/business_server.go:283-294`) -- Hybrid concatenates TWO files per slot (RSA-2048 + ML-DSA-65) into a single response body, the other 3 profiles serve a single file. The actual PEM size of each file comes from `certs_manifest.json` (generated by `cert_manifest.py`, reading the actual files from `mock-service-os/certs/`). The HTTP framing overhead (97B content-length, 103B chunked) comes from `headerOverheadByFraming`/`wantFramingByProfile` (`thesis/results/v9/integration/gateway/ca_handler_test.go:142-144` and `:280`) -- Classic uses content-length, the other 3 profiles use chunked. **Zero difference across all 4 profiles** -- this is the only one of the three verifications in this section with no rounding residual at all, because the framing overhead is an exact integer, not a statistical average over many samples.

### 2.5 Structural invariants by term (Classic < PQC < Hybrid)

| Term | Classic | PQC | Hybrid | Classic<PQC<Hybrid? |
|---|---:|---:|---:|---|
| mTLS (handshake) | 18.750 | 129.636 | 144.474 | YES |
| JWT (signature only) | 7.168 | 92.652 | 99.820 | YES |
| JWK (raw key) | 1.536 | 8.320 | 9.856 | YES |
| PKI (CA certificates) | 7.130,00 | 32.440 | 39.182,00 | YES |

**Separate check involving Control (Hybrid >= Control, by term):**

| Term | Hybrid | Control | Hybrid >= Control? |
|---|---:|---:|---|
| mTLS (handshake) | 144.474 | 101.694 | YES |
| JWT (signature only) | 99.820 | 99.820 | YES |
| JWK (raw key) | 9.856 | 9.856 | YES |
| PKI (CA certificates) | 39.182,00 | 37.768 | YES |

**Handshake-byte divergence per connection -- confirmed zero.** `handshake_bytes_alert.json`: 2880 mTLS connections audited, **0 divergent**.

## 3. Control by term: where it falls below and where it falls above PQC (no contradiction between text and table)

The Control total falls below the PQC total (ratios from Section 2.1), but this is **not** true term by term -- recalculated here directly from the 4 terms of Section 2.2, without copying any pre-computed number:

| Term | Control | PQC | Control − PQC |
|---|---:|---:|---:|
| mTLS (handshake) | 101.694 | 129.636 | -27.942 |
| JWT (signature only) | 99.820 | 92.652 | +7.168 |
| JWK (raw key) | 9.856 | 8.320 | +1.536 |
| PKI (CA certificates) | 37.768 | 32.440 | +5.328 |
| **Total** | **249.138** | **263.048** | **-13.910,00** |

**Correct reading, by term:** Control falls **below** PQC only in the mTLS term (certificate chain still RSA-based on the Control side versus PQC's pure ML-DSA-65 chain) -- and falls **above** PQC in the 3 other terms (JWT, JWK, PKI), where both use an equivalent signature construction but Control carries additional material that pure PQC does not carry. The final negative balance (Control below PQC in the total) comes entirely from the saving in the mTLS term, which is large enough to offset the 3 combined increments.

## 4. Latency results

### 4.1 T_fluxo per cell (median, standard deviation, minimum, maximum; n=10 per cell, single window)

| Installation | Scenario | Profile | Median | Standard deviation | Minimum | Maximum |
|---|---|---|---:|---:|---:|---:|
| sa-east-1 | L0-sa-east-1 | Classic | 2.357,9 ms | 50,96 ms | 2.270,3 ms | 2.439,9 ms |
| sa-east-1 | L0-sa-east-1 | PQC | 2.288,9 ms | 142,19 ms | 1.919,2 ms | 2.425,9 ms |
| sa-east-1 | L0-sa-east-1 | Hybrid | 2.564,6 ms | 83,58 ms | 2.406,0 ms | 2.712,0 ms |
| sa-east-1 | L123 | Classic | 10.879,8 ms | 59,92 ms | 10.811,9 ms | 11.021,8 ms |
| sa-east-1 | L123 | PQC | 11.143,3 ms | 65,40 ms | 11.052,0 ms | 11.253,6 ms |
| sa-east-1 | L123 | Hybrid | 11.349,1 ms | 77,24 ms | 11.255,7 ms | 11.502,8 ms |
| sa-east-1 | L219 | Classic | 17.683,3 ms | 50,11 ms | 17.608,2 ms | 17.776,4 ms |
| sa-east-1 | L219 | PQC | 18.105,6 ms | 46,77 ms | 18.050,1 ms | 18.197,8 ms |
| sa-east-1 | L219 | Hybrid | 18.396,5 ms | 107,86 ms | 18.203,5 ms | 18.483,4 ms |
| sa-east-1 | L325 | Classic | 25.559,2 ms | 178,49 ms | 25.311,2 ms | 25.801,6 ms |
| sa-east-1 | L325 | PQC | 26.136,5 ms | 205,24 ms | 25.934,8 ms | 26.612,2 ms |
| sa-east-1 | L325 | Hybrid | 26.531,6 ms | 305,82 ms | 26.064,8 ms | 27.131,4 ms |
| us-east-1 | L0-us-east-1 | Classic | 3.817,0 ms | 60,52 ms | 3.790,9 ms | 3.935,3 ms |
| us-east-1 | L0-us-east-1 | PQC | 4.040,4 ms | 81,17 ms | 3.943,0 ms | 4.165,9 ms |
| us-east-1 | L0-us-east-1 | Hybrid | 4.208,1 ms | 117,28 ms | 4.044,0 ms | 4.409,6 ms |
| us-east-1 | L14 | Classic | 4.744,6 ms | 48,97 ms | 4.694,9 ms | 4.864,6 ms |
| us-east-1 | L14 | PQC | 5.032,4 ms | 46,92 ms | 4.942,2 ms | 5.085,5 ms |
| us-east-1 | L14 | Hybrid | 5.202,5 ms | 93,31 ms | 5.053,9 ms | 5.363,9 ms |
| ap-northeast-1 | L0-ap-northeast-1 | Classic | 5.786,2 ms | 52,76 ms | 5.688,1 ms | 5.857,5 ms |
| ap-northeast-1 | L0-ap-northeast-1 | PQC | 6.248,6 ms | 82,15 ms | 6.141,1 ms | 6.394,4 ms |
| ap-northeast-1 | L0-ap-northeast-1 | Hybrid | 6.616,3 ms | 155,70 ms | 6.328,1 ms | 6.814,4 ms |
| ap-northeast-1 | L30 | Classic | 8.214,5 ms | 151,14 ms | 8.003,7 ms | 8.518,7 ms |
| ap-northeast-1 | L30 | PQC | 8.769,4 ms | 102,18 ms | 8.540,3 ms | 8.864,0 ms |
| ap-northeast-1 | L30 | Hybrid | 9.028,6 ms | 125,66 ms | 8.859,3 ms | 9.233,5 ms |

**Control profile, by route (separate table):**

| Installation | Scenario | Median | Standard deviation | Minimum | Maximum |
|---|---|---:|---:|---:|---:|
| sa-east-1 | L0-sa-east-1 | 2.472,1 ms | 49,94 ms | 2.408,3 ms | 2.550,5 ms |
| sa-east-1 | L123 | 11.263,4 ms | 78,84 ms | 11.145,7 ms | 11.416,7 ms |
| sa-east-1 | L219 | 18.302,0 ms | 117,71 ms | 18.153,5 ms | 18.513,0 ms |
| sa-east-1 | L325 | 26.523,1 ms | 224,60 ms | 26.211,8 ms | 26.878,4 ms |
| us-east-1 | L0-us-east-1 | 4.247,7 ms | 137,51 ms | 4.067,2 ms | 4.529,6 ms |
| us-east-1 | L14 | 5.145,7 ms | 90,21 ms | 5.067,7 ms | 5.316,7 ms |
| ap-northeast-1 | L0-ap-northeast-1 | 6.634,2 ms | 192,58 ms | 6.295,2 ms | 6.786,1 ms |
| ap-northeast-1 | L30 | 9.018,1 ms | 166,88 ms | 8.718,3 ms | 9.270,3 ms |

### 4.2 Order of medians by route and percentage difference (PQC vs. Classic, Hybrid vs. PQC)

*Correction note: the previous version of this table included Control in the "Order" column, mixed in with the central comparison -- corrected here to list only Classic/PQC/Hybrid, consistent with the rest of this section (Control was never part of the percentage-difference calculation, only of the order shown).*

| Route | Order (lowest -> highest median) | PQC vs. Classic | Hybrid vs. PQC |
|---|---|---:|---:|
| L0-sa-east-1 | PQC < Classic < Hybrid | -2,93% | +12,04% |
| L123 | Classic < PQC < Hybrid | +2,42% | +1,85% |
| L219 | Classic < PQC < Hybrid | +2,39% | +1,61% |
| L325 | Classic < PQC < Hybrid | +2,26% | +1,51% |
| L0-us-east-1 | Classic < PQC < Hybrid | +5,85% | +4,15% |
| L14 | Classic < PQC < Hybrid | +6,07% | +3,38% |
| L0-ap-northeast-1 | Classic < PQC < Hybrid | +7,99% | +5,88% |
| L30 | Classic < PQC < Hybrid | +6,75% | +2,96% |

**Aggregated counts (8 routes):** Hybrid > PQC (median) in **8/8** routes; PQC > Classic (median) in **7/8** routes.

### 4.3 Overlap of [minimum;maximum] interval by route (Classic×PQC and PQC×Hybrid)

| Route | Classic×PQC overlap? | PQC×Hybrid overlap? |
|---|---|---|
| L0-sa-east-1 | YES | YES |
| L123 | NO | NO |
| L219 | NO | NO |
| L325 | NO | YES |
| L0-us-east-1 | NO | YES |
| L14 | NO | YES |
| L0-ap-northeast-1 | NO | YES |
| L30 | NO | YES |

**Aggregated counts:** Classic×PQC overlap in **1/8** routes; PQC×Hybrid overlap in **6/8** routes. Where the intervals overlap, the order of medians for that specific route is not read as robust based solely on this table -- see the significance analysis in Section 5.

### 4.4 Inversion in L0-sa-east-1 (PQC with median below Classic): the 10 actual values, with no cause attributed

10 actual T_fluxo values (seconds), sorted, for this route:

- **Classic:** 2,270337, 2,320785, 2,327829, 2,341451, 2,353749, 2,362013, 2,362613, 2,401444, 2,425318, 2,439924
- **PQC:** 1,919165, 2,271329, 2,274855, 2,279327, 2,282256, 2,295532, 2,342916, 2,367430, 2,418240, 2,425901

**PQC median with the 10 values:** 2,288894s. **PQC median excluding the single lowest value** (1,919165s): 2,295532s -- a 6,6ms shift from removing that value. **Classic median:** 2,357881s. The PQC median remains below the Classic median even excluding the lowest value -- the inversion does not depend entirely on a single extreme value; the other 9 PQC values, as a set, also sit at the same level as or below the bulk of the Classic distribution on this specific route.

**Execution order of the profile blocks on this route** (`manifest.route_orders["L0-sa-east-1"]`): Control -> Classic -> PQC -> Hybrid. PQC runs as the 3rd of the 4 blocks on this route, after Classic -- the data does not show, by itself, any specific cause for the inversion beyond what is listed above; no cause is proposed beyond what the values and the order directly show.

## 5. Statistical significance of the contrasts between profiles (exploratory analysis)

**Explicit scope statement:** this is an **EXPLORATORY, non-pre-registered** analysis -- the 16 main contrasts below (Classic×PQC and PQC×Hybrid, by adjacent pair, across the 8 routes) were **chosen after describing the data** in Sections 4.1-4.4 of this same version of the report, not before data collection. It does not carry the weight of a confirmatory analysis -- it quantifies and tests what has already been observed descriptively, it does not validate a hypothesis fixed in advance.

### 5.1 Tests by route -- Classic×PQC and PQC×Hybrid (16 main tests)

Exact two-sided Mann-Whitney U, n=10 per group (continuous measurement, no ties expected). Holm-adjusted p-value over the set of the 16 main tests below -- its OWN family, separate from the 16 tests with Control (Section 5.2). Hodges-Lehmann: median of all pairwise differences (not the difference of the medians, reported separately); 95% CI via bootstrap, fixed seed, 10.000 resamples (see reproducibility note below). Cliff's delta chosen as the effect-size measure (instead of raw probability of superiority) as it is the more standard convention in non-parametric comparisons of small samples -- it is numerically equivalent to 2×P(superiority)-1, so the probability-of-superiority information remains recoverable from it.

*Note: the smallest raw p mathematically possible in the exact two-sided Mann-Whitney with n=10 per group is 2/C(20,10) = 1.08e-05 -- confirmed by running the test itself on two groups with no overlap at all (total separation), not just calculated analytically. This is why no "raw p" cell in this section's tables shows "0,0000" (which would suggest an exact p=0, impossible here) -- values below the 4-decimal-place resolution appear as "<0,0001".*

**Sign convention, valid in Sections 5.1 and 5.2:** "Diff" = Median B − Median A; a positive Cliff's delta means B is systematically larger than A, negative means the opposite. Consistent cell by cell with the rows below (e.g., L0-sa-east-1, PQC vs. Classic -- here B=PQC, A=Classic -- has a negative Diff AND a negative Cliff's delta, both agreeing that PQC came out below Classic on this route).

| Route | Pair | Median A (reference, ms) | Median B (compared, ms) | Diff (ms) | Diff (%) | raw p | Holm p (16) | Hodges-Lehmann (ms) | 95% CI bootstrap (ms) | Cliff's delta | Significant (Holm, α=0,05)? |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| L0-sa-east-1 | PQC vs. Classic | 2.357,9 | 2.288,9 | -69,0 | -2,93% | 0,2176 | 0,2176 | -54,7 | [-105,9;11,9] | -0,340 | NO |
| L123 | PQC vs. Classic | 10.879,8 | 11.143,3 | 263,4 | 2,42% | <0,0001 | 0,0002 | 253,9 | [198,3;319,2] | 1,000 | YES |
| L219 | PQC vs. Classic | 17.683,3 | 18.105,6 | 422,3 | 2,39% | <0,0001 | 0,0002 | 421,4 | [386,3;462,5] | 1,000 | YES |
| L325 | PQC vs. Classic | 25.559,2 | 26.136,5 | 577,3 | 2,26% | <0,0001 | 0,0002 | 622,3 | [454,9;800,5] | 1,000 | YES |
| L0-us-east-1 | PQC vs. Classic | 3.817,0 | 4.040,4 | 223,4 | 5,85% | <0,0001 | 0,0002 | 193,9 | [138,8;274,7] | 1,000 | YES |
| L14 | PQC vs. Classic | 4.744,6 | 5.032,4 | 287,9 | 6,07% | <0,0001 | 0,0002 | 275,0 | [222,7;311,9] | 1,000 | YES |
| L0-ap-northeast-1 | PQC vs. Classic | 5.786,2 | 6.248,6 | 462,4 | 7,99% | <0,0001 | 0,0002 | 471,5 | [410,8;544,6] | 1,000 | YES |
| L30 | PQC vs. Classic | 8.214,5 | 8.769,4 | 554,8 | 6,75% | <0,0001 | 0,0002 | 552,6 | [425,2;661,6] | 1,000 | YES |
| L0-sa-east-1 | Hybrid vs. PQC | 2.288,9 | 2.564,6 | 275,7 | 12,04% | <0,0001 | 0,0003 | 240,0 | [163,8;310,3] | 0,960 | YES |
| L123 | Hybrid vs. PQC | 11.143,3 | 11.349,1 | 205,9 | 1,85% | <0,0001 | 0,0002 | 204,1 | [146,1;282,0] | 1,000 | YES |
| L219 | Hybrid vs. PQC | 18.105,6 | 18.396,5 | 290,9 | 1,61% | <0,0001 | 0,0002 | 274,1 | [138,4;340,7] | 1,000 | YES |
| L325 | Hybrid vs. PQC | 26.136,5 | 26.531,6 | 395,1 | 1,51% | 0,0052 | 0,0104 | 395,4 | [149,4;655,2] | 0,720 | YES |
| L0-us-east-1 | Hybrid vs. PQC | 4.040,4 | 4.208,1 | 167,7 | 4,15% | 0,0005 | 0,0015 | 174,7 | [81,7;278,1] | 0,860 | YES |
| L14 | Hybrid vs. PQC | 5.032,4 | 5.202,5 | 170,1 | 3,38% | 0,0001 | 0,0006 | 189,9 | [114,4;255,8] | 0,920 | YES |
| L0-ap-northeast-1 | Hybrid vs. PQC | 6.248,6 | 6.616,3 | 367,7 | 5,88% | 0,0001 | 0,0006 | 332,5 | [178,3;425,9] | 0,920 | YES |
| L30 | Hybrid vs. PQC | 8.769,4 | 9.028,6 | 259,2 | 2,96% | <0,0001 | 0,0002 | 298,4 | [181,7;396,6] | 0,980 | YES |

### 5.2 Contrasts with Control -- Control×Hybrid and Control×PQC (16 tests, OUT OF THE SCOPE of the thesis)

**Outside the central scope of this thesis** -- consistent with the separation of Control from the main comparisons (Section 2). Reported here only for methodological completeness, in its OWN Holm family (separate from the 16 main tests of Section 5.1 -- never mixed into the same adjustment).

| Route | Pair | Median A (reference, ms) | Median B (compared, ms) | Diff (ms) | Diff (%) | raw p | Holm p (16) | Hodges-Lehmann (ms) | 95% CI bootstrap (ms) | Cliff's delta | Significant (Holm, α=0,05)? |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| L0-sa-east-1 | Control vs. Hybrid | 2.564,6 | 2.472,1 | -92,5 | -3,61% | 0,0185 | 0,1483 | -78,0 | [-141,4;-19,2] | -0,620 | NO |
| L123 | Control vs. Hybrid | 11.349,1 | 11.263,4 | -85,7 | -0,76% | 0,0288 | 0,2016 | -78,5 | [-143,4;-11,5] | -0,580 | NO |
| L219 | Control vs. Hybrid | 18.396,5 | 18.302,0 | -94,5 | -0,51% | 0,5787 | 1,0000 | -32,8 | [-158,1;51,0] | -0,160 | NO |
| L325 | Control vs. Hybrid | 26.531,6 | 26.523,1 | -8,5 | -0,03% | 0,9705 | 1,0000 | 7,1 | [-290,2;254,0] | 0,020 | NO |
| L0-us-east-1 | Control vs. Hybrid | 4.208,1 | 4.247,7 | 39,5 | 0,94% | 0,9705 | 1,0000 | -6,2 | [-105,9;119,9] | -0,020 | NO |
| L14 | Control vs. Hybrid | 5.202,5 | 5.145,7 | -56,9 | -1,09% | 0,2799 | 1,0000 | -48,9 | [-126,5;43,9] | -0,300 | NO |
| L0-ap-northeast-1 | Control vs. Hybrid | 6.616,3 | 6.634,2 | 17,9 | 0,27% | 0,9118 | 1,0000 | 8,7 | [-182,4;137,3] | 0,040 | NO |
| L30 | Control vs. Hybrid | 9.028,6 | 9.018,1 | -10,4 | -0,12% | 0,6842 | 1,0000 | -18,0 | [-159,8;100,1] | -0,120 | NO |
| L0-sa-east-1 | Control vs. PQC | 2.288,9 | 2.472,1 | 183,2 | 8,00% | <0,0001 | 0,0007 | 158,9 | [101,8;224,0] | 0,960 | YES |
| L123 | Control vs. PQC | 11.143,3 | 11.263,4 | 120,2 | 1,08% | 0,0007 | 0,0094 | 126,7 | [58,1;196,1] | 0,840 | YES |
| L219 | Control vs. PQC | 18.105,6 | 18.302,0 | 196,4 | 1,08% | <0,0001 | 0,0007 | 194,0 | [116,6;313,9] | 0,960 | YES |
| L325 | Control vs. PQC | 26.136,5 | 26.523,1 | 386,6 | 1,48% | 0,0015 | 0,0150 | 372,3 | [195,8;583,8] | 0,800 | YES |
| L0-us-east-1 | Control vs. PQC | 4.040,4 | 4.247,7 | 207,2 | 5,13% | 0,0021 | 0,0188 | 175,9 | [93,1;291,9] | 0,780 | YES |
| L14 | Control vs. PQC | 5.032,4 | 5.145,7 | 113,2 | 2,25% | 0,0001 | 0,0018 | 125,6 | [65,2;218,9] | 0,920 | YES |
| L0-ap-northeast-1 | Control vs. PQC | 6.248,6 | 6.634,2 | 385,6 | 6,17% | 0,0007 | 0,0094 | 350,1 | [117,4;468,8] | 0,840 | YES |
| L30 | Control vs. PQC | 8.769,4 | 9.018,1 | 248,8 | 2,84% | 0,0007 | 0,0094 | 259,7 | [146,1;406,2] | 0,840 | YES |

### 5.3 Aggregated test across routes

**Exact two-sided sign test** (count of routes, out of the 8, where the median of the 2nd profile exceeds that of the 1st):

| Comparison | Routes where it exceeds | p-value (sign, exact) |
|---|---:|---:|
| PQC > Classic | 7/8 | 0,0703 |
| Hybrid > PQC | 8/8 | 0,0078 |

**Wilcoxon signed-rank over the 8 per-route median percentage differences** (not a test per individual execution -- one value per route, 8 total):

| Comparison | p-value (Wilcoxon signed-rank) |
|---|---:|
| PQC vs. Classic (8 % differences) | 0,0547 |
| Hybrid vs. PQC (8 % differences) | 0,0078 |

### 5.4 Factual reading (without claiming robustness where the test does not support it)

**PQC vs. Classic:** significant after Holm (α=0,05) in **7/8** routes; not significant in the other 1/8. **Hybrid vs. PQC:** significant after Holm in **8/8** routes; not significant in the other 0/8.

**Inversion in L0-sa-east-1 (Section 4.4, PQC with median below Classic):** by the exact Mann-Whitney test with Holm correction over the 16 main tests, this difference **is NOT** statistically significant (raw p=0,2176, Holm p=0,2176, Cliff's delta=-0,340). No claim of robustness is made for any contrast whose Holm-adjusted p-value does not exclude the null hypothesis at α=0,05 -- the cells marked "NO" in the tables above remain read as non-significant, not as "nearly significant" or similar.

**Reading of the aggregated tests (Section 5.3), without softening the interpretation:** for PQC vs. Classic, **NEITHER** of the two aggregated tests reaches α=0,05 -- sign test p=0,0703, Wilcoxon signed-rank p=0,0547 (both above 0,05). For Hybrid vs. PQC, both reach α=0,05 -- sign p=0,0078, Wilcoxon p=0,0078.

**The 8 routes are NOT statistically independent of one another** -- they share only 3 physical installations (`sa-east-1`, `us-east-1`, `ap-northeast-1`), each hosting several routes simultaneously (e.g., `L0-sa-east-1`, `L123`, `L219`, and `L325` all run from the same physical server in `sa-east-1`). For this reason, the aggregated cross-route tests in this section (sign test, Wilcoxon) are **INDICATIVE ONLY** -- they do not constitute a formally valid inference under the independence assumption that these tests require. The 32 per-route tests (Sections 5.1/5.2) do not depend on this cross-route assumption (each one compares only the 10 executions of one profile against the 10 of another, WITHIN THE SAME route) -- the independence caveat applies only to the aggregates in this section, not to the per-route tests.

**Methodological caveat on T_fluxo (added after the exploratory "Degrau 1" investigation -- see `thesis/results/v9/analise_origem/RELATORIO_ORIGEM.md`):** the "T_fluxo" field used in this section measures the end-to-end execution time observed by the orchestrating process (via SSH, from the control host to the client host), not just the HTTP calls between client and server. SSH overhead and the client process's cold start are common to all profiles (they do not introduce bias between profiles). It also includes an RSA signing-key preparation cost, paid exactly once per execution by Classic, Hybrid, and Control, not paid by PQC -- measured locally at ~26-30ms (RSA-2048 key, the actual size used in the campaign, Decision 113), with an attention factor of up to 1,5x for a possible CPU performance difference between the measurement notebook and the actual m7i-flex.large instances (never measured directly). Even at the upper bound of this range (~45ms), a sensitivity estimate (Degrau 1, Item 8) confirms: none of the 16 published comparisons flips sign in the point estimates, and no already-published Hodges-Lehmann confidence interval changes its relationship to zero when shifted by this bias -- the statistical significance itself was not reassessed.

### 5.5 Design caveat (network drift within the sequential block of each route)

Within each route, the 4 profile blocks run **sequentially** (order drawn per route, seed `20261107`, already documented in Section 1 -- `route_orders`) -- so network drift over time (e.g., variation in network conditions between the start and the end of that specific route's window) may contribute to part of the differences observed between profiles WITHIN the same route. Randomizing the order ACROSS routes (each route has a potentially different order, Section 1) reduces, but **does not eliminate**, this effect -- there is no block control within a single route (the 4 profiles do not run interleaved/alternated within the same route, they run in 4 consecutive blocks).

**Actual order of the profile blocks, by route** (`manifest.route_orders`, raw data, with no further interpretation):

| Route | Block order (1st -> 2nd -> 3rd -> 4th) |
|---|---|
| L0-sa-east-1 | Control -> Classic -> PQC -> Hybrid |
| L123 | Classic -> Hybrid -> Control -> PQC |
| L219 | Hybrid -> Control -> Classic -> PQC |
| L325 | PQC -> Hybrid -> Classic -> Control |
| L0-us-east-1 | Control -> Classic -> Hybrid -> PQC |
| L14 | Hybrid -> PQC -> Classic -> Control |
| L0-ap-northeast-1 | Hybrid -> Classic -> Control -> PQC |
| L30 | PQC -> Classic -> Hybrid -> Control |

**Bootstrap reproducibility note:** fixed seed `20261116`, 10.000 resamples, `numpy.random.default_rng` -- never a system/clock seed. Running this same script again reproduces exactly the same confidence intervals.

## 6. Technical criteria (1-7)

| Criterion | Result |
|---|---|
| 1 (per-message sizes (campaign)) | PASS |
| 2 (actual initcwnd (campaign)) | PASS |
| 3 (zero errors on the most distant route (campaign)) | PASS |
| 4 (flow counts (campaign)) | PASS |
| 5 (zero errors) | PASS |
| 6 (complete instrumentation + assertions (campaign)) | PASS |
| 7 (per-route latency sanity (campaign)) | **FAIL** |

### 6.1 Criterion 7 -- nominal vs. measured RTT, by route (documented exception in L30)

| Route | Nominal RTT (ms) | Measured RTT, probe (ms) | Measured RTT, pcap (ms) | Within ±10%? |
|---|---:|---:|---:|---|
| L0-sa-east-1 | 0 | 0,160 | 0,129 | YES |
| L123 | 123 | 122,618 | 122,642 | YES |
| L219 | 219 | 220,175 | 220,151 | YES |
| L325 | 325 | 333,501 | 323,406 | YES |
| L0-us-east-1 | 0 | 0,264 | 0,287 | YES |
| L14 | 14 | 15,076 | 14,759 | YES |
| L0-ap-northeast-1 | 0 | 0,144 | 0,105 | YES |
| L30 | 30 | 34,079 | 33,423 | **NO -- documented exception** |

*`L0-*` routes are co-located (nominal RTT registered as 0); the actual evaluator applies a tolerance check to these routes that differs from the ±10% percentage used for the others, never a division by zero -- "YES" there reflects the actual result of `evaluate_criteria.py`, not a percentage calculation over a nominal value of 0.*

**Decision on L30 (not corrected, not recalibrated):** accepted as a documented exception. The actual RTT of `L30` measures ~33,4-34,1ms (probe channel and pcap channel agree with each other) against the 30ms nominal registered in the topology baseline -- 11-14% outside the ±10% tolerance the criterion requires. The measurement baseline was not changed. The comparison between profiles (Classic/PQC/Control/Hybrid, Section 4) always occurs WITHIN the same route -- each profile runs under the same actual RTT on L30, so this exception does not compromise any comparison between profiles, only the absolute sanity criterion for this specific route against its registered nominal value.

### 6.2 Transport retries: 0 (zero)

`retries_report.json`: `total_retries=0`, `por_celula={}` -- none of the 320 official executions needed an HTTP/mTLS transport retry.

## 7. Internal AS<->RS channel (remains classical across all 4 profiles)

**Mechanism, confirmed by code (not assumed):** `thesis/results/v9/integration/gateway/business_server.go:246-250` -- `attachInternalCallerCarveOut` builds a `cfg.GetConfigForClient` whose only condition is `hello.ServerName == internalCallerSNI` (`"matls-api.local"`, line 164); when true, it always returns the SAME `internalCfg`, whose `CurvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}` (line 242) is a fixed value, with no `if`/`switch` on `profile` inside the closure itself. `business_server.go:104` confirms the same on the runtime enforcement side: it only applies the PROFILE-EXPECTED curve to connections that are NOT the internal call -- by construction, valid for all 4 profiles.

**Actual evidence from this campaign (320 executions), full source (not just the last profile block):** `piloto_combined.log` is a log continuously appended throughout the whole window (it survives container restarts between profile blocks, unlike `full_container_logs`) -- **2.240 actual connections** with `sni="matls-api.local"`, **100% with curve=CurveP256**, in the central Classic/PQC/Hybrid set: Classic=560, Hybrid=560, PQC=560. **Control profile, separate:** 560 connections, same curve, same result (100% compliant).

**Corroborating evidence from an earlier real pilot (18 executions, the SAME code and the SAME Docker images as this campaign, run before it on the same account/infrastructure):** **126 actual connections** with `sni="matls-api.local"`, **100% with curve=CurveP256**, in the same central Classic/PQC/Hybrid set: Classic=42, Hybrid=42, PQC=21. **Control profile, separate:** 21 connections, same curve. Two independent real collections, the same code mechanism, the same result -- 0 violations in either.

## 8. Cost (formula-based estimate -- NEVER the actual amount billed)

Formula from `cost_tracker.CostTracker` (actual fleet: 12 instances -- 1 `t4g.micro` + 11 `m7i-flex.large`, 12 EIPs), `window_start_utc` derived from the first actual line of `cost_tracker.jsonl` (`2026-11-15T04:17:09Z`). **Every value below is a FORMULA-BASED ESTIMATE, never a "final cost" nor an amount actually billed -- the real, definitive value is whatever appears in the account's AWS Billing/Cost Explorer, never this local formula.**

**The fleet was stopped via `StopInstances` ("User initiated") before `2026-11-16T04:26:00Z`** -- confirmed by `describe-instances` across the 7 regions (`stopped` state on all 12 instances, never `terminated`). **The exact time of each stop could not be determined via the API:** `cloudtrail:LookupEvents` and `cloudwatch:GetMetricStatistics` returned `AccessDeniedException` (the same already-documented least-privilege policy never included trail/billing/metrics permission) -- reconfirmed here again, by reading the RAW `StateTransitionReason` field directly on all 12 instances (7 regions): the value is, literally and without exception, the string `"User initiated"` -- no parentheses, no date, no embedded time -- on all 12. `describe-instances` does not carry a state-transition timestamp in any field. The already-confirmed conservative upper bound is used here -- if the actual stop occurred before this (it certainly did), using this instant as the cutoff slightly overestimates the compute time billed, never underestimates it.

**`cost_tracker.py` does not model instance shutdown** -- it was designed assuming the fleet continuously running since `window_start_utc`; without the adjustment below, the pure formula would keep counting compute cost that is no longer being billed since the shutdown, overestimating the actual value from that instant onward.

| Moment | Timestamp (UTC) | Accumulated formula-based estimate |
|---|---|---:|
| last automatically recorded reading (cost_tracker.jsonl) -- continuous formula, fleet still running | 2026-11-15T23:36:12Z | US\$27,69 |
| end of the official window (manifest.window_end_utc) -- continuous formula, fleet still running | 2026-11-16T00:06:40Z | US\$28,42 |
| end of the dedicated-criteria collection (last actual event in the gateway logs) -- continuous formula, fleet still running | 2026-11-16T00:22:57Z | US\$28,81 |
| now (the moment this report was generated) -- TWO-PHASE formula: continuous until the fleet stopped, EBS+EIP only afterward | 2026-11-17T15:32:11Z | US\$38,24 |

**Actual rate for the STOPPED fleet, reconfirmed here** (same constants from `cost_tracker.py`, 12 gp3 volumes of 30GB each + 12 EIPs still associated, 0 compute): EBS US\$1,04/day + EIP US\$1,44/day = **US\$2,48/day** (US\$0,1034/h). Applied for 35,10h from the shutdown to the "now" reading above.

- **cost_stop:** never triggered (`None`); ceiling for this phase: warning US\$70 / stop US\$90 -- both already without practical meaning now that the fleet is stopped (the continuous formula no longer applies).
- **Raw data integrity:** 720/720 files copied from control, verified by local sha256, 0 divergences.

## 9. Transparency and scope limits

- **This revision corrects Decision 147 (`DECISIONS.md`): the JWT term now includes the actual internal signature of the 2 id_tokens (JWE) per execution, previously counted as 0 bytes.** The original justification ("the id_token is never signed via JWS") was wrong -- the id_token has a real internal signature, verified by the client after decrypting the JWE; the real-time capture pipeline simply never extracted it (an instrumentation gap, not a real absence of the signature). Measured locally (never on the AWS fleet), the correction is recorded, with full proof and raw data, in Decision 216 and its Amendment (`DECISIONS.md`) -- see also `thesis/results/v9/opinsize_correction_id_token/`. All OPINsize figures in this document (Sections 2.1-2.5) already reflect this correction; the pre-correction value is preserved only for audit purposes in `opinsize_oficial_conta_nova.json` (`term_jwt_sem_correcao_id_token`), never added into any OPINsize variant.
- **RSA-4096 catalyst files for the Control profile's CA were not migrated** -- the Control profile reuses the classical RSA root/issuer for its certificate chain, by design.
- **The Control total falls below the PQC total, but not term by term** -- see the full reconciliation in Section 3: Control falls below PQC only in the mTLS term, and above in the other 3 terms.
- **Exception to criterion 7 in L30**, documented and accepted without baseline recalibration (Section 6.1).
- **Internal AS->RS connections fall outside the OPINsize equation** -- the term measures only what traverses the client-facing channel (mTLS gateway); the internal channel remains classical and unmigrated, by design (Section 7).
- **Reproducibility caveat:** operating-system packages (AMI and `dnf`) installed at the time this campaign was provisioned do not have their exact versions re-pinned by any manifest beyond what the host facts document (a read-only audit, delivered separately) recorded -- a future rebuild from a newer AMI may obtain different package versions than those observed here, without this indicating any change to this thesis's code/binaries (those remain pinned, verified as described in Section 10).

## 10. Reproducibility

**Docker image integrity, per image, with the actual guarantee for each one (not a generic statement):**

- **`gateway` and `proxy`:** **bit-for-bit identical** binaries to the registered pin -- the sha256 of the compiled binary matches exactly against the pinned value, with no tolerance at all.
- **`measure`:** equivalence, **not** bit-for-bit -- the `gateway`/`proxy` binaries embedded inside the image are identical to the pin, the image's stable layers (positions 0 and 4 of `rootfs_layers`) and the `config_subset` are identical; the volatile layers (positions 1, 2, and 3) vary from build to build due to a timestamp that BuildKit embeds, not due to a content difference -- documented since Decision 159.
- **`auth`, `mongo_seed`, `mockapi`:** identity via `rootfs_layers`+`config_subset`, **equivalent** reconstruction, not bit-for-bit -- the actual, already identified causes of byte-for-byte non-determinism between different builds/operating systems are: line-ending normalization (CRLF/LF), ephemeral key material generated by the AS itself on each execution (never persisted, always of fixed size/type), and resolution of `npm`'s platform-specific optional dependencies (package variants per build operating system, never an actual runtime dependency).
- **Delivery gate (all images):** verified by content (`rootfs_layers`, `config_subset`, `binary_sha256` of the embedded binaries), never by `tar_sha256` -- two `docker save` runs of the EXACT same content produce `.tar` files with different SHA-256 hashes from each other (instability of the tar format/packaging metadata itself, not of the content), so comparing by `tar_sha256` would produce false negatives.

- Every number in this document was read or computed by `thesis/results/v9/campaign/scripts/generate_final_report_oficial_conta_nova.py`, from `thesis/results/v9/campaign_oficial_conta_nova_raw/`, `thesis/results/v9/campaign_oficial_conta_nova_organized/`, and from a verification external to the pipeline run live (`evaluate_criteria.expected_handshake_bytes`, Section 2.2) -- no value was typed in manually.
- This report was independently audited (a separate agent, with no access to this document's text as a source, only to the organized data/manifest) before its final delivery -- a verification table is in the corresponding Decision in `DECISIONS.md`.

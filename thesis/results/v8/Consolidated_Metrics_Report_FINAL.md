# Consolidated Experimental Metrics Report: v8, real multi-region AWS campaign

**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, and Hybrid -- real network, three windows, 720 executions**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

## 1. Scope and what changed from v7

### 1.1. From emulated to real network latency

Every prior version of this thesis (v1-v7) measured the cost of the OPIN post-quantum migration under network latency **emulated** with `tc`/`netem` on a single machine, one Docker Desktop host running every participant. This version (v8) replaces that emulation with a **real multi-region AWS deployment**: one complete server stack (the mTLS gateway, the authorization server, the resource server, and the directory mock) per installation, and a separate client instance in a different AWS region, so the measured round-trip time is the real network's own, not an injected value.

**Topology.** Three server installations (`sa-east-1`, `us-east-1`, `ap-northeast-1`), eight client scenarios across them (four routes from `sa-east-1` -- `L0`, co-located; `L123`, `L219`, `L325` -- and two each from `us-east-1` and `ap-northeast-1` -- `L0` and `L14`/`L30`), chosen empirically by real measured RTT rather than assumed from the literature. Each of the three crypto profiles (Classic, PQC, Hybrid) runs the identical client code against every route.

**Collection.** Three official windows of 10 executions per profile per route (`24 cells x 10 = 240 executions per window`), run in sequential campaign mode with automatic advance between windows (zero errors and mean CPU steal below 5% required), for **720 total official executions**. Each window follows a circulant Latin square (seed 0) rotating the order in which the three profiles run within each installation block, so no single profile is always measured first or last across the campaign. Before any official execution, **K=5 warm-up runs per cell are discarded and kept separately** (`warmup/w{window}_warm{01..05}.json`, never read by any statistic in this report) -- a number chosen from a real finding in a prior pilot (10/24 cells showed a significant settling trend with fewer warm-up runs; K=5 covers 100% of cells).

**Pre-registration.** Five quantitative predictions were derived from window 1's own data and pre-registered, before windows 2 and 3 were analyzed, as confirmatory for those two windows (`ANALYSIS_PLAN.md`, tag `v8-prereg-3`). Section 7 reports the outcome of all five, per window and combined, including the one that did not hold up.

Every number in this document originates from `thesis/results/v8/global_v2/report_data_v8_combined.json` and `consolidated_combined.json`, independently recomputed from the raw per-execution files and pcaps (`thesis/scripts/audit_v8_from_raw.py`) -- same convention as v7's own `audit_v7_from_raw.py`.

### 1.2. The three profiles (unchanged from v7)

| Profile | Signatures | TLS key exchange |
|---|---|---|
| Classic | RSA (PS256) | ECDHE, single P-384 curve |
| PQC | Pure ML-DSA-65 (NIST FIPS 204) throughout: tokens, subject keys, and every certificate's own issuer signature, root included | Pure ML-KEM-1024 (NIST FIPS 203) |
| Hybrid | RSA and ML-DSA-65 combined: certificates with a dual signature in non-critical X.509 extensions; payload extension on client-issued JWTs; Strong Nesting on server-issued JWTs | SecP384r1MLKEM1024 (P-384 + ML-KEM-1024) |

Across all three profiles, `id_token` encryption (RSA-OAEP with AES-256-GCM) remains classical, by explicit, declared scope decision -- there is no post-quantum JOSE encryption standard, and the encryption key exchange was never part of this project's migration scope (`thesis/scripts/opin_flow.py:798-802`).

## 2. Profiles and the layer matrix

A live, pre-destroy audit (Decision 116) verified every cryptographic layer of a real, still-running deployment -- not a re-derivation from static files. `openssl s_client` independently confirmed Classic's and Hybrid's negotiated TLS group, TLS version, cipher, and signature algorithm; PQC's own group (`MLKEM1024`) does not interoperate with plain OpenSSL (a real cross-implementation finding, not a project defect) and was instead confirmed from the real gateway log of an official execution. `mock-service-os/certs/main.go -verify-pqc-cert`/`-verify-hybrid` performed a real signed-challenge/preTBS verification against the live certificate and key material, not merely a size/OID check.

| Layer | Classic | PQC | Hybrid | Verified how |
|---|---|---|---|---|
| TLS key exchange | ECDH secp384r1 | ML-KEM-1024 | SecP384r1MLKEM1024 | `openssl s_client` (Classic/Hybrid, live); gateway log (PQC) |
| TLS server certificate | RSA-4096 | ML-DSA-65 (pure) | RSA-4096 base + ML-DSA-65 extension | `openssl x509 -text`, live |
| TLS client certificate | RSA-4096 | ML-DSA-65 (pure) | RSA-4096 + AltSignatureValue (ML-DSA-65) | Signed-challenge verification, live |
| Certificate chain (root, issuer) | RSA | **ML-DSA-65** (both levels) | RSA (classical root reused) | `openssl x509 -text`, live |
| JWT signatures (client_assertion, request object, id_token, JARM) | PS256 | ML-DSA-65 (pure) | Strong Nesting (PS256+ML-DSA-65) or payload-extension (RS256+ML-DSA-65), by artifact | Dual-signature verification |
| JWE (`id_token` encryption) | RSA-OAEP + A256GCM | **identical to Classic** | **identical to Classic** | Declared scope limitation, not migrated |
| Internal AS->RS connection | CurveP256 (classical carve-out) | **identical to Classic** | **identical to Classic** | Gateway-log correlation, all 720 executions, 0 violations |
| Directory/PKI chain | RSA | **ML-DSA-65** (both levels) | RSA (classical root reused) | `openssl x509 -text`, live |

**Two cells read differently from what their profile's label suggests, by design, not by omission.** The Hybrid JWT's own `alg` header reads `PS256` even when the underlying signature is the dual Strong Nesting construction -- a reader who checks only the header sees a classical algorithm where a second, real ML-DSA-65 signature also exists. And the JWE term above is identical across all three profiles by an explicit, already-documented scope decision, not a migration gap discovered late. Full matrix, with file:line evidence for every cell: `thesis/results/v8/artifacts/item1_layer_matrix.md`.

## 3. Size results: the OPINsize equation

Same equation this thesis has used since v5 (extending Schardong et al.'s Eq. 3.1 with the PKI term):

```
OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x PKI_bytes
```

All four `N_x` counts are identical across profiles (`N_mTLS=6`, `N_JWT=28`, `N_JWK=2`, `N_PKI=4`) and identical across all 8 real routes (verified by `audit_v8_from_raw.py`); only the per-item byte size changes.

| Term | Classic | PQC | Hybrid |
|---|---:|---:|---:|
| handshake_bytes (per connection) | 5,179 | 22,607 | 19,017 |
| JWT_size (average) | 1,330.82 | 5,404.32 | 7,163.11 |
| JWK_PK_size | 512 | 3,904 | 4,416 |
| PKI_bytes (average, PEM body) | 2,110 | 8,007 | 9,339 |
| **OPINsize (total)** | **77,801** | **326,799** | **360,857** |

PQC is 4.20x Classic (+320.04%); Hybrid is 4.64x Classic (+363.82%) and 1.10x PQC (+10.42%). With the PQC profile's certificate chain confirmed ML-DSA-65 end-to-end in this campaign's own live deployment (Section 2), the pattern already found in v7 holds here too: most of Hybrid's premium over Classic is already paid by PQC alone.

### Bytes per participant (application layer, per execution, median)

v8's byte accounting groups outbound traffic into two categories (`Other` -- AS+RS application traffic -- and `PKI/CRL` -- CA certificate downloads), coarser than v7's three-way AS/RS/Directory split.

| Category | Classic | PQC | Hybrid |
|---|---:|---:|---:|
| Other (received) | 95,571 | 197,035 | 231,523 |
| Other (sent) | 21,622 | 51,447 | 69,122 |
| PKI/CRL (received) | 8,852 | 32,440 | 37,768 |
| PKI/CRL (sent) | 732 | 732 | 732 |

## 4. Latency results

### T_fluxo per cell (median, bootstrap 95% CI, min, max; n=30 per cell, pooled across the 3 windows)

| Installation | Scenario | Profile | Median | 95% CI | Min | Max |
|---|---|---|---:|---:|---:|---:|
| sa-east-1 | L0 | Classic | 1,721.0 ms | [1,693.5;1,764.1] | 1,651.5 ms | 1,825.6 ms |
| sa-east-1 | L0 | PQC | 1,755.4 ms | [1,730.1;1,766.2] | 1,659.8 ms | 1,885.6 ms |
| sa-east-1 | L0 | Hybrid | 1,816.4 ms | [1,788.6;1,833.8] | 1,747.0 ms | 1,903.9 ms |
| sa-east-1 | L123 | Classic | 8,631.6 ms | [8,609.2;8,660.5] | 8,558.9 ms | 8,691.6 ms |
| sa-east-1 | L123 | PQC | 8,671.0 ms | [8,653.2;8,683.8] | 8,604.2 ms | 8,748.9 ms |
| sa-east-1 | L123 | Hybrid | 8,733.1 ms | [8,711.0;8,752.0] | 8,661.8 ms | 8,819.9 ms |
| sa-east-1 | L219 | Classic | 14,077.2 ms | [14,063.0;14,090.3] | 13,999.9 ms | 14,185.4 ms |
| sa-east-1 | L219 | PQC | 14,087.9 ms | [14,075.0;14,111.7] | 14,047.6 ms | 14,264.7 ms |
| sa-east-1 | L219 | Hybrid | 14,142.4 ms | [14,130.1;14,166.0] | 14,084.2 ms | 14,255.2 ms |
| sa-east-1 | L325 | Classic | 20,226.0 ms | [20,166.3;20,381.6] | 19,788.7 ms | 20,620.0 ms |
| sa-east-1 | L325 | PQC | 20,339.8 ms | [20,272.8;20,373.5] | 19,871.4 ms | 20,493.7 ms |
| sa-east-1 | L325 | Hybrid | 20,353.1 ms | [20,295.0;20,390.6] | 19,960.5 ms | 20,794.8 ms |
| us-east-1 | L0 | Classic | 1,742.5 ms | [1,725.7;1,758.9] | 1,656.5 ms | 1,826.1 ms |
| us-east-1 | L0 | PQC | 1,747.2 ms | [1,718.3;1,783.1] | 1,652.4 ms | 1,858.8 ms |
| us-east-1 | L0 | Hybrid | 1,837.0 ms | [1,815.1;1,851.2] | 1,745.2 ms | 1,967.6 ms |
| us-east-1 | L14 | Classic | 2,581.4 ms | [2,569.3;2,642.5] | 2,521.1 ms | 2,731.4 ms |
| us-east-1 | L14 | PQC | 2,604.7 ms | [2,584.1;2,636.7] | 2,515.7 ms | 2,756.0 ms |
| us-east-1 | L14 | Hybrid | 2,660.7 ms | [2,644.8;2,691.1] | 2,552.0 ms | 2,780.4 ms |
| ap-northeast-1 | L0 | Classic | 1,753.3 ms | [1,726.1;1,765.9] | 1,669.3 ms | 1,888.3 ms |
| ap-northeast-1 | L0 | PQC | 1,751.7 ms | [1,737.1;1,774.3] | 1,667.5 ms | 1,843.2 ms |
| ap-northeast-1 | L0 | Hybrid | 1,844.6 ms | [1,827.7;1,862.6] | 1,740.4 ms | 1,974.1 ms |
| ap-northeast-1 | L30 | Classic | 3,549.8 ms | [3,532.0;3,557.9] | 3,484.5 ms | 3,724.9 ms |
| ap-northeast-1 | L30 | PQC | 3,585.9 ms | [3,568.0;3,605.8] | 3,508.5 ms | 3,673.6 ms |
| ap-northeast-1 | L30 | Hybrid | 3,638.1 ms | [3,621.6;3,661.9] | 3,544.7 ms | 3,746.5 ms |

RTT in this table is **measured** from the pcap SYN/SYN-ACK of each execution's own mTLS connections, never assumed from the scenario's label -- confirmed identical within sampling noise across profiles at the same route by `audit_v8_from_raw.py`.

### Differences against Classic (delta = a + b x RTT_measured model, pooled 30 runs/cell)

| Profile | a (fixed cost) | a crosses zero? | b (per unit of RTT) | b crosses zero? |
|---|---:|---|---:|---|
| Hybrid | 87.88 ms [79.92;96.07] | does NOT cross zero | 0.0550 [-0.1483;0.1298] | crosses zero |
| PQC | 13.74 ms [-1.26;30.32] | crosses zero | 0.2094 [-0.0602;0.3520] | crosses zero |

Hybrid carries a real, statistically detectable fixed cost over Classic (`a` does not cross zero): the extra signature/verification work, independent of distance. PQC's fixed cost is not detectable in the combined (30-run) dataset -- see Section 7 for how this differs window by window.

### Order between profiles (Mann-Whitney U, pooled 30 vs. 30 runs per route; sign test across the 8 routes)

| Comparison | Routes where left > right | Statistically significant (p<0.05) |
|---|---:|---:|
| Hybrid > Classic | 8/8 | 8/8 |
| PQC > Classic | 7/8 | 2/8 |
| Hybrid > PQC | 8/8 | 7/8 |

Hybrid is slower than Classic in all 8 routes, and the difference is statistically significant in all 8 (Mann-Whitney, p<0.05 at every route) -- the one ordering this report treats as robust. PQC vs. Classic shows a less consistent, weaker-magnitude pattern (most routes favor PQC>Classic, but only a minority reach significance) -- reported as **not a reliably detectable, fixed ordering**, not forced into one.

## 5. Network metrics

| Installation | Scenario | Profile | RTT measured (median, ms) | Jitter (median, ms) | Retransmissions/segments | Duplicate-ACK (own field) | Out-of-order (own field) |
|---|---|---|---:|---:|---:|---:|---:|
| sa-east-1 | L0 | Classic | 0.24 | 0.13 | 0 (0.0394% upper bound) | 0.2760% (21) | 0.0000% (0) |
| sa-east-1 | L0 | PQC | 0.21 | 0.15 | 0 (0.0262% upper bound) | 0.2181% (25) | 0.0000% (0) |
| sa-east-1 | L0 | Hybrid | 0.22 | 0.14 | 0 (0.0247% upper bound) | 0.1646% (20) | 0.0000% (0) |
| sa-east-1 | L123 | Classic | 122.65 | 0.39 | 0 (0.0372% upper bound) | 0.2106% (17) | 0.0000% (0) |
| sa-east-1 | L123 | PQC | 122.65 | 0.39 | 0 (0.0221% upper bound) | 0.1251% (17) | 0.0000% (0) |
| sa-east-1 | L123 | Hybrid | 122.68 | 0.36 | 0 (0.0208% upper bound) | 0.1524% (22) | 0.0000% (0) |
| sa-east-1 | L219 | Classic | 219.64 | 0.48 | 0 (0.0371% upper bound) | 0.2596% (21) | 0.0000% (0) |
| sa-east-1 | L219 | PQC | 219.71 | 0.39 | 0 (0.0216% upper bound) | 0.1510% (21) | 0.0000% (0) |
| sa-east-1 | L219 | Hybrid | 219.72 | 0.45 | 0 (0.0205% upper bound) | 0.1642% (24) | 0.0000% (0) |
| sa-east-1 | L325 | Classic | 330.41 | 7.37 | 0 (0.0371% upper bound) | 0.2597% (21) | 0.0000% (0) |
| sa-east-1 | L325 | PQC | 331.14 | 6.34 | 0 (0.0216% upper bound) | 0.0936% (13) | 0.0000% (0) |
| sa-east-1 | L325 | Hybrid | 331.07 | 7.78 | 0 (0.0206% upper bound) | 0.1165% (17) | 0.0000% (0) |
| us-east-1 | L0 | Classic | 0.33 | 0.16 | 0 (0.0391% upper bound) | 0.5473% (42) | 0.0000% (0) |
| us-east-1 | L0 | PQC | 0.30 | 0.15 | 0 (0.0261% upper bound) | 0.1827% (21) | 0.0000% (0) |
| us-east-1 | L0 | Hybrid | 0.28 | 0.15 | 0 (0.0250% upper bound) | 0.1832% (22) | 0.0000% (0) |
| us-east-1 | L14 | Classic | 14.51 | 0.46 | 0 (0.0370% upper bound) | 0.4070% (33) | 0.0000% (0) |
| us-east-1 | L14 | PQC | 14.45 | 0.51 | 0 (0.0221% upper bound) | 0.1841% (25) | 0.0000% (0) |
| us-east-1 | L14 | Hybrid | 14.46 | 0.54 | 0 (0.0209% upper bound) | 0.1464% (21) | 0.0000% (0) |
| ap-northeast-1 | L0 | Classic | 0.24 | 0.18 | 0 (0.0394% upper bound) | 0.3417% (26) | 0.0000% (0) |
| ap-northeast-1 | L0 | PQC | 0.20 | 0.19 | 0 (0.0261% upper bound) | 0.2005% (23) | 0.0000% (0) |
| ap-northeast-1 | L0 | Hybrid | 0.22 | 0.14 | 1 (0.0083%) | 0.1913% (23) | 0.0000% (0) |
| ap-northeast-1 | L30 | Classic | 32.04 | 0.41 | 0 (0.0372% upper bound) | 0.1364% (11) | 0.0000% (0) |
| ap-northeast-1 | L30 | PQC | 32.07 | 0.58 | 0 (0.0220% upper bound) | 0.1837% (25) | 0.0000% (0) |
| ap-northeast-1 | L30 | Hybrid | 32.08 | 0.46 | 0 (0.0208% upper bound) | 0.1525% (22) | 0.0000% (0) |

**Packet loss, strictly defined, means retransmissions divided by segments.** Duplicate-ACK and out-of-order events are reported in their own fields and are never summed into a "loss" figure -- both can occur from ordinary reordering, with no packet actually lost (Decision 115, item 4; this correction's own rationale is recorded there in full).

## 6. CPU and phase accounting

### T_fluxo phase decomposition (sa-east-1/L0, the near-zero-RTT reference route)

| Phase | Classic | PQC | Hybrid |
|---|---:|---:|---:|
| HTTP calls | 361.9 ms | 335.4 ms | 410.7 ms |
| Signing | 16.2 ms | 26.9 ms | 44.7 ms |
| Verification | 25.1 ms | 26.3 ms | 28.2 ms |
| Explicit wait | 0.0 ms | 0.0 ms | 0.0 ms |
| Setup/teardown (fixed) | 1,071.2 ms | 1,095.2 ms | 1,071.6 ms |
| Residual | 240.1 ms | 260.3 ms | 253.9 ms |
| Residual, % of T_fluxo | 13.8% | 15.0% | 14.0% |

Setup/teardown (~1.07s: a fixed callback-server teardown wait plus certificate generation) is declared as a fixed, profile-independent component, not part of any profile's cryptographic cost -- same amount in all three columns, by construction of the test harness.

**Handshake in round trips (sum of the 6 connections' own handshake time, divided by measured RTT), L123/L219/L325, median per cell, window 1 (Decision 112):**

- Classic: L123=12.33, L219=12.20, L325=12.10
- PQC: L123=12.07, L219=12.03, L325=12.03
- Hybrid: L123=12.35, L219=12.20, L325=12.19

All three profiles sit close to 12 -- direct confirmation that larger certificates/keys (PQC/Hybrid) do not cost extra handshake round trips.

**The ~6-trip residual beyond the 6-connection handshake was investigated and explicitly not attributed** (Decision 112, item 2): a full per-connection timeline (SYN through FIN) of one real L325 execution found gaps of several RTTs that look more consistent with client-side sequencing (the 6 connections are not kept busy continuously or run in parallel) than with extra network round trips inside a single connection's own handshake. Within the 30-minute budget allotted, no specific cause could be isolated with confidence -- recorded as **not attributed**, not as an unexplained anomaly glossed over.

## 7. Model: T_fluxo = T0 + k x RTT_measured, per profile

| Profile | T0 (fixed cost) | k | k 95% CI | k contains 56? |
|---|---:|---:|---:|---|
| Classic | 1.7425s | 56.03 | [55.91;56.78] | yes |
| PQC | 1.7605s | 56.13 | [56.03;57.52] | **no** |
| Hybrid | 1.8341s | 55.99 | [55.91;56.55] | yes |

56 is the expected trip count: 44 application calls + 2 round trips for each of the flow's 6 mTLS connections (12, confirmed above). Classic and Hybrid's k contains 56 in the combined (30-run) fit; **PQC's does not** -- its point estimate, 56.14, sits inside a tolerance band of 56+-1 but its own bootstrap confidence interval sits entirely above 56. `audit_v8_from_raw.py` independently reproduced this point estimate exactly and found the discrepancy's exact upper bound sensitive to the bootstrap's own random-number stream at this sample size (8 routes feeding the slope) -- the point estimate is robust, the exact upper edge of the interval is not.

### Pre-registered confirmatory check (5 predictions from window 1, tag `v8-prereg-3`), per window and combined

| Prediction | Window 1 (exploratory) | Window 2 | Window 3 | Combined (30 runs/cell) |
|---|---|---|---|---|
| 1. k=56+-1, all 3 profiles | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=FAIL, Hybrid=PASS | Classic=FAIL, PQC=FAIL, Hybrid=PASS | Classic=PASS, PQC=FAIL, Hybrid=PASS |
| 2. Hybrid a>0 (does not cross zero) | PASS | PASS | PASS | PASS |
| 3. PQC a~0 (crosses zero) | PASS | FAIL | PASS | PASS |
| 4. b~0, both profiles | Hybrid=PASS, PQC=PASS | Hybrid=PASS, PQC=FAIL | Hybrid=PASS, PQC=PASS | Hybrid=PASS, PQC=PASS |
| 5. Order: Hybrid>Classic 8/8; PQC vs Classic no fixed direction | Hybrid 8/8; PQC 6/8 | Hybrid 8/8; PQC 7/8 | Hybrid 8/8; PQC 7/8 | Hybrid 8/8; PQC 7/8 |

**Prediction 1 is the only one that does not hold cleanly, and PQC is the reason in every window.** Predictions 2, 4, and 5 pass in the combined dataset; prediction 3 (PQC's fixed cost indistinguishable from zero) **failed in window 2 specifically** (`a`=+32.33ms, 95% CI [+15.26;+52.30]ms, with a negative, significant `b` too) but passed again in windows 1 and 3, and passes in the combined fit. A heterogeneity test across the three windows' own `a` estimates (pairwise Z-test and Cochran's Q, Decision 115 item 4) found window 2 vs. window 3 significantly different (p=0.0086) and the omnibus test across all three significant too (Q=7.160, df=2, p=0.0279) -- **this is reported as a real, statistically detectable difference between windows, not dismissed as sampling noise**, even though its specific cause (profile-order effect, a real non-stationarity in the network or hardware, or something else) is **not attributed**.

## 8. Statistical validity

**Drift (Mann-Kendall trend test), all 72 cells (24 cells x 3 windows):** 10/72 cells show a statistically significant trend (p<0.05) -- 3/24 in window 1, 4/24 in window 2, 3/24 in window 3. Every one of those significant cells trends downward (settling), none upward -- consistent with residual warm-up/settling effect, not with a systematic drift that would bias one profile over another, since the direction is the same regardless of which profile runs in which position within a window.

**Shapiro-Wilk normality** was computed for every distribution reported throughout this document (T_fluxo, RTT, jitter, CPU, signing/verification/setup timings) and is available per cell in `consolidated_combined.json`; several distributions reject normality at alpha=0.05 (e.g., the setup-phase `generate_callback_cert` timing, spread 752%), which is why every statistic in this report is a median with a bootstrap confidence interval, not a mean with a parametric one.

**Position and window as covariates.** The Latin square rotates each profile's position within every window's block; the heterogeneity test in Section 7 treats window explicitly as a covariate for PQC's fixed cost. No systematic ordering effect across positions was tested beyond the sign test in Section 4 and the per-window confirmatory check in Section 7.

**No execution was removed from any statistic in this report.** All 720 official executions across the 3 windows, 0 recorded errors, feed every table above.

## 9. Mapping to the independent review items

Against the advisor's/reviewer's parecer técnico (which evaluated an earlier, shorter version of this report, not this v8 document) and the project's own pre-registration/metrics-coverage documents. Full citations: `thesis/results/v8/artifacts/item3_promise_evidence_matrix.md`.

| Item | Status |
|---|---|
| 4.2 (latency model / round-trip count) | **Closed** -- Section 7's k-model |
| 4.3 (PQC/Hybrid asymmetry, CA signature) | **Closed** -- Section 2, PQC's chain confirmed ML-DSA-65 end-to-end live |
| 4.4 (transport/front-channel realism) | **Partially closed** -- real network/MTU now in scope; no real browser/app front-channel tested |
| 4.6a (single unit of measure for JWT/keys) | **Not done** |
| 4.6c (Classic profile's conformance to OPIN's live security profile) | **Not done** |
| 4.6e (hybrid certificate model vs. composite signatures) | **Declared limitation** -- mechanism documented, alternative not tested |
| Rec. 1 (add a 4th, hybrid-KEM-classical-signature profile) | **Not done** |
| Rec. 2 (symmetrize PQC/Hybrid) | **Closed** -- same as 4.3 |
| Rec. 3 (decompose client/server/handshake/wait time) | **Closed** -- Section 6 |
| Rec. 4 (explain round-trip count) | **Closed** -- Section 6/7 |
| Rec. 5 (realistic bandwidth/MTU) | **Closed** (partially -- real condition, not a deliberate sweep) |
| Rec. 6 (real browser/app front-channel) | **Not done** |
| Rec. 7 (reformulate "fixed cost per flow" conclusions) | **Not done** -- this report's own Section 7 text is the first pass at that reformulation |
| Rec. 8 (uniform unit of measure / RSA algorithm; justify parameters) | **Declared limitation** -- parameters justified in code comments; unit/RSA not uniformized |
| Advisor: metrics at least equal to Schardong et al. (2022) | **Closed** |
| Advisor: distribution statistics, not just the median | **Closed** -- Shapiro-Wilk, bootstrap CI, Mann-Whitney, sign test throughout |

## 10. Limitations

- **JWE stays classical in every profile.** `id_token` encryption (RSA-OAEP + A256GCM) was never in this migration's scope; no post-quantum JOSE encryption standard exists to migrate to.
- **Hybrid's TLS server/client authentication reuses Classic's RSA key as its base**, adding ML-DSA-65 as an extension rather than replacing the key material -- "Hybrid" at this layer means an added signature, not a swapped key.
- **A single server image per profile/installation**, not independently rebuilt per window -- `code_hash`/image digest were checked at every profile-block switch (Decision 108) but the binary itself is shared infrastructure, not a per-window variable.
- **ICMP is blocked by the security groups**; RTT and loss come from TCP/pcap evidence (SYN/SYN-ACK, retransmissions), never from `ping`.
- **No real browser or app front-channel was tested** -- the client is this project's own HTTP client, not a real user agent subject to URL-length or redirect-chain limits.
- **Each window covers a few real hours**, not a long-term deployment -- the heterogeneity found for PQC's fixed cost across windows (Section 7) spans this scale of time, not weeks or months.
- **4.6a/4.6c** (a single declared unit of measure for JWTs/keys; the Classic profile's documented conformance to OPIN's own live security profile) remain open, by scope, not by oversight.
- **No fourth profile** (hybrid KEM with classical-only signatures) was added.
- **The AWS instances are burstable-credit VM types**; CPU steal was monitored throughout the campaign (mean below 5% in every window) but burstable-credit exhaustion over a longer run was not specifically tested.
- **The ~6-trip residual beyond the 6-connection handshake is not attributed** (Section 6) -- investigated within a fixed time budget, no specific cause isolated with confidence.
- **PQC's k and fixed-cost estimates show real, statistically detectable variation across the 3 windows** (Section 7) -- the cause is not attributed; the combined estimate across all 3 windows is this report's best single figure, not a claim that the underlying quantity is provably stable.

## 11. Reproducibility and integrity

- **Git tags:** `v8-prereg` (acceptance criteria, before any official window), `v8-prereg-3` (the 5 confirmatory predictions, before windows 2/3 were analyzed), `v8-official-data` and `v8-official-data-2` (the official 720-execution dataset and its corrected/extended consolidate).
- **Code/image integrity:** every profile block checked `CODE_HASH` against a registered value and the live gateway image digest against `sha256:0839867545f3170f6198e7e2f6f3a9a7f6803c2b4feba2bb54f181195b341901`, every block, all 3 windows -- 0 violations (Decision 108's `check_artifact_health`).
- **sha256 manifests:** every file in `janela1/`, `janela2/`, `janela3/` has a per-file sha256 manifest under `_campaign-control/sha256_manifest.txt`.
- **Data inventory:** 720 official execution files + 360 discarded warm-up files + 744 client/server pcaps each, matching exactly between the control instance's cumulative data tree and this repository (Decision 115, item 2).
- **Secret scanning:** every commit in this campaign's history passed the project's secret scanner (staged diff, full history, and a manual decompress-and-grep pass over every pcap) before being pushed.
- **Cost and fleet hours:** approximately US$22 of AWS spend from this boot's own ~17 hours of fleet uptime (estimated via the project's own hourly-rate model; AWS Cost Explorer access is not available to this project's IAM user).
- **This audit:** `thesis/scripts/audit_v8_from_raw.py` independently recomputed T_fluxo (24 cells), bytes-per-participant, RTT measured, OPINsize constancy, the k-model, and the 72-cell drift table directly from the raw run files, calls.jsonl, and pcaps, pooled across all 3 windows -- **0 divergences** against the published consolidate outputs (one noted finding, not a divergence: the PQC k bootstrap CI's upper tail is sensitive to the resampling stream at this sample size -- see Section 7).

## 12. Equivalence with the reference article (Schardong et al., CANS 2022)

| Metric (Schardong et al., 2022) | Measured in v8? | Where |
|---|---|---|
| Total flow size (bytes transferred) | Yes | Section 3 (OPINsize) |
| mTLS handshake size | Yes | Section 3 |
| JWT/token size | Yes | Section 3 |
| Public key size | Yes | Section 3 (JWK_PK_size) |
| Flow latency under network delay | Yes -- with **real**, not emulated, delay | Section 4 |
| Per-endpoint latency breakdown | Yes | `consolidated_combined.json`'s `latency_per_endpoint_ms`, referenced in Section 4/6 |
| RTT | Yes -- measured from pcap, not assumed | Section 5 |
| Packet loss | Yes -- strictly as retransmissions/segments (Decision 115 correction) | Section 5 |
| CA/PKI certificate cost | Yes -- this thesis's own extension to Schardong's equation (the PKI term), carried forward from v5 | Section 3 |

## References

- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017.
- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019). *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.* Journal of Open Source Software, 4(40), 1606.
- Schardong et al. (2022), Eq. 3.1 (original flow-size equation).
- NIST FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA).

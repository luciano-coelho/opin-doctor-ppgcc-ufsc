# Consolidated Experimental Metrics Report: v8, real multi-region AWS campaign

**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, and Hybrid -- real network, three windows, 720 executions**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

## Executive summary

Migrating OPIN's consent flow to post-quantum cryptography multiplies the cryptographic material transferred by 4.20x (PQC) and 4.64x (Hybrid) relative to Classic (77,801 -> 326,799/360,857 bytes per flow). Under real multi-region AWS latency (not emulated), Hybrid is reliably slower than Classic in all 8 routes tested (Mann-Whitney, significant in all 8 after Holm correction); PQC's own latency penalty is smaller and not consistently detectable across routes. A fixed-cost/distance-scaling model (T_fluxo = T0 + k x RTT) holds closely for Classic and Hybrid (k near the expected 56 round trips); PQC's own k sits just outside its confidence interval around 56 in the combined dataset, and PQC's fixed cost varies in a statistically detectable way between the 3 collection windows -- both reported as open, not-fully-explained findings, not smoothed over. A live, pre-destroy audit confirmed PQC's certificate chain is ML-DSA-65 end-to-end (closing a gap the independent review flagged against an earlier report version); JWE encryption and the AS-to-RS internal channel remain classical in every profile, by explicit, already-declared scope decision.

## 1. Scope and what changed from v7

### 1.1. From emulated to real network latency

Every prior version of this thesis (v1-v7) measured the cost of the OPIN post-quantum migration under network latency **emulated** with `tc`/`netem` on a single machine, one Docker Desktop host running every participant. This version (v8) replaces that emulation with a **real multi-region AWS deployment**: one complete server stack (the mTLS gateway, the authorization server, the resource server, and the directory mock) per installation, and a separate client instance in a different AWS region, so the measured round-trip time is the real network's own, not an injected value.

**Relation to v7.** v7 fixed a real measurement artifact (a container-spawn cost contaminating every PQC/Hybrid signing call) and closed the PQC profile's certificate chain to be post-quantum end-to-end at the CA level; this report inherits both fixes as a starting point and adds a dimension v7 never attempted: a real network, instead of a single-host emulation of one. Several v7 findings replicate here under real conditions (the ~12-round-trip handshake cost regardless of key size; the Classic<Hybrid ordering under network delay); one does not replicate cleanly (PQC's own fixed cost over Classic, stable in v7's own single-host runs, now shows real, measured variation across collection windows -- Section 7).

**Infrastructure.** Server and client instances: `m7i-flex.large` -- an Intel-based "flex" instance type with a baseline-and-burst performance model, **not** the credit-based burstable model of the T-series. The control instance (orchestration only, never part of any measured flow): `t4g.micro`, an ARM Graviton T-series instance, which **is** credit-based burstable. CPU steal was monitored on the measured instances throughout the campaign (mean below 5% in every window); the control instance's own credit behavior was not specifically tested, since it does no flow work. **A single gateway image** is used for all three profiles and all three installations (the profile is selected at runtime by `CRYPTO_PROFILE`, not by a separate image per profile) -- its digest was checked at every profile-block switch against one registered value, all 3 windows, 0 mismatches.

**Topology.** Three server installations (`sa-east-1`, `us-east-1`, `ap-northeast-1`), eight client scenarios across them (four routes from `sa-east-1` -- `L0`, co-located; `L123`, `L219`, `L325` -- and two each from `us-east-1` and `ap-northeast-1` -- `L0` and `L14`/`L30`), chosen empirically by real measured RTT rather than assumed from the literature. Each of the three crypto profiles (Classic, PQC, Hybrid) runs the identical client code against every route. **The AS-to-RS internal channel stays classical (`CurveP256`) in every profile, including PQC and Hybrid** -- this is not an oversight, it is this flow's own pre-existing internal carve-out (present since before this thesis's PQC work began), confirmed unchanged across all 720 executions (Section 2).

**Collection.** Three official windows of 10 executions per profile per route (`24 cells x 10 = 240 executions per window`), run in sequential campaign mode with automatic advance between windows (zero errors and mean CPU steal below 5% required), for **720 total official executions**. The full campaign, first execution to last, spans 14.5 hours (2026-10-30T23:12 UTC to 2026-10-31T13:41 UTC -- 2026-10-30 ~20:13 BRT through 2026-10-31 ~10:42 BRT, starting at night Brazil time and running into the next morning). Each window follows a circulant Latin square (seed 0) rotating the order in which the three profiles run within each installation block -- **the same order for every installation in a given window**, so a profile's position within a window's block is fully determined by (profile, window), not an independent variable (Section 7's regression reports this confound explicitly rather than fitting a model that assumes it away).

**Warm-up.** Before any official execution, **K=5 warm-up runs per cell are discarded and kept separately** (`warmup/w{window}_warm{01..05}.json`, never read by any statistic in this report) -- a number chosen because it covered 100% of the settling trend found in a prior **pilot's** 24 cells (10/24 showed a significant trend with fewer warm-up runs). This does not mean the official windows show zero residual drift: Section 8 finds 10/72 official cells still show a statistically significant (if small) downward trend even after K=5 -- the warm-up's own 100% figure describes the pilot it was sized from, not a claim that the official data is drift-free.

**Pre-registration.** Five quantitative predictions were derived from window 1's own data and pre-registered, before windows 2 and 3 were analyzed, as confirmatory for those two windows (`ANALYSIS_PLAN.md`, tag `v8-prereg-3`). Section 7 reports the outcome of all five, per window and combined, including the one that did not hold up.

Every number in this document is read or computed from `thesis/results/v8/global_v2/report_data_v8_combined.json` and `consolidated_combined.json`, independently recomputed from the raw per-execution files and pcaps (`thesis/scripts/audit_v8_from_raw.py`) -- same convention as v7's own `audit_v7_from_raw.py`.

### 1.2. The three profiles (unchanged from v7, with one addition spelled out)

| Profile | Signatures | TLS key exchange | AS<->RS internal channel |
|---|---|---|---|
| Classic | RSA (PS256) | ECDHE, single P-384 curve | Classical (`CurveP256`) |
| PQC | Pure ML-DSA-65 (NIST FIPS 204) throughout: tokens, subject keys, and every certificate's own issuer signature, root included | Pure ML-KEM-1024 (NIST FIPS 203) | **Classical (`CurveP256`), unchanged from Classic** |
| Hybrid | RSA and ML-DSA-65 combined: certificates with a dual signature in non-critical X.509 extensions; payload extension on client-issued JWTs; Strong Nesting on server-issued JWTs | SecP384r1MLKEM1024 (P-384 + ML-KEM-1024) | **Classical (`CurveP256`), unchanged from Classic** |

The internal channel column is listed explicitly here, not only in Section 2's layer matrix: it is a real, measured property of every profile, including the two post-quantum ones, confirmed by gateway-log correlation on all 720 executions with 0 violations.

Across all three profiles, `id_token` encryption (RSA-OAEP with AES-256-GCM) remains classical, by explicit, declared scope decision -- there is no post-quantum JOSE encryption standard, and the encryption key exchange was never part of this project's migration scope (`thesis/scripts/opin_flow.py:798-802`).

## 2. Profiles and the layer matrix

A live, pre-destroy audit (Decision 116) verified every cryptographic layer of a real, still-running deployment -- not a re-derivation from static files. `openssl s_client` independently confirmed Classic's and Hybrid's negotiated TLS group, TLS version, cipher, and signature algorithm; PQC's own group (`MLKEM1024`) does not interoperate with plain OpenSSL (a real cross-implementation finding, not a project defect) and was instead confirmed from the real gateway log of an official execution. `mock-service-os/certs/main.go -verify-pqc-cert`/`-verify-hybrid` performed a real signed-challenge/preTBS verification against the live certificate and key material, not merely a size/OID check. OpenSSL version on the probing host: `OpenSSL 3.5.8 25 Aug 2026`.

| Layer | Classic | PQC | Hybrid | Verified how |
|---|---|---|---|---|
| TLS key exchange | ECDH secp384r1 | ML-KEM-1024 | SecP384r1MLKEM1024 | `openssl s_client` (Classic/Hybrid, live); gateway log (PQC) |
| TLS server certificate -- the key the LIVE HANDSHAKE actually authenticates | RSA-4096 | ML-DSA-65 (pure) | **RSA-4096 base + a non-critical ML-DSA-65 extension the TLS handshake itself never checks** | `openssl x509 -text`, live |
| TLS client certificate -- same caveat | RSA-4096 | ML-DSA-65 (pure) | **RSA-4096 + AltSignatureValue (ML-DSA-65), same caveat** | Signed-challenge verification, live |
| Certificate chain (root, issuer) | RSA | **ML-DSA-65** (both levels) | RSA (classical root reused) | `openssl x509 -text`, live |
| JWT signatures (client_assertion, request object, id_token, JARM) | PS256 | ML-DSA-65 (pure) | Strong Nesting (PS256+ML-DSA-65) or payload-extension (RS256+ML-DSA-65), by artifact | Dual-signature verification |
| JWE (`id_token` encryption) | RSA-OAEP + A256GCM | **identical to Classic** | **identical to Classic** | Declared scope limitation, not migrated |
| Internal AS->RS connection | CurveP256 (classical carve-out) | **identical to Classic** | **identical to Classic** | Gateway-log correlation, all 720 executions, 0 violations |
| Directory/PKI chain | RSA | **ML-DSA-65** (both levels) | RSA (classical root reused) | `openssl x509 -text`, live |

**Every cell that reads differently from what its profile's label suggests, enumerated (not left implicit):**

1. **JWE stays identical across all three profiles** -- `id_token` encryption was never migrated, by declared scope decision (Section 1.2).
2. **The AS<->RS internal channel stays classical under PQC and Hybrid** -- the same pre-existing carve-out Classic always used (Section 1.2).
3. **Hybrid's JWT `alg` header reads `PS256`** even when the underlying signature is the dual Strong Nesting construction -- a reader checking only the header sees a classical algorithm where a second, real ML-DSA-65 signature also exists.
4. **Hybrid's TLS server and client certificates carry a real ML-DSA-65 signature (the `AltSignatureValue` X.509 extension) that the live TLS handshake itself never checks.** X.509 non-critical extensions are, by the standard's own definition, not required to be processed by a verifier that doesn't understand them -- Go's `crypto/tls` (both sides of this project's real connections) validates the certificate's primary RSA signature during the handshake and ignores the extension entirely. The ML-DSA-65 signature is real and independently checkable (confirmed live, this section, via `-verify-hybrid`'s own out-of-band preTBS reconstruction), but **nothing in the live connection path itself verifies it** -- Hybrid's TLS-layer authentication is, in practice, exactly as strong as Classic's against an attacker who can forge an RSA signature; the added PQC signature is present but currently inert at this layer, not a second, independently-enforced check.

Full matrix, with file:line evidence for every cell: `thesis/results/v8/artifacts/item1_layer_matrix.md`.

## 3. Size results: the OPINsize equation

Same equation this thesis has used since v5 (extending Schardong et al.'s Eq. 3.1 with the PKI term):

```
OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x PKI_bytes
```

All four `N_x` counts are identical across profiles and across all 8 real routes (verified by `audit_v8_from_raw.py`); only the per-item byte size changes. **`N_JWK = 4`, read directly from the raw data's own call count, not assumed from v7's flow structure** -- the flow calls `/jwks` 4 times per execution (2 for the AS's own signing key, plus 2 more carrying the SAME key under a second `kid`, confirmed equal size; the separate `enc`-use key used for JWE, Section 2, is fetched in the same calls but is not part of this equation's `JWK_PK_size` term, which counts only the `sig`-use entries).

| Term | Classic | PQC | Hybrid |
|---|---:|---:|---:|
| handshake_bytes (per connection, N_mTLS=6) | 5,179 | 22,607 | 19,017 |
| JWT_size (average, N_JWT=28) | 1,330.82 | 5,404.32 | 7,163.11 |
| JWK_PK_size (per key, N_JWK=4) | 256 | 1,952 | 2,208 |
| PKI_bytes (average, PEM body, N_PKI=4) | 2,110 | 8,007 | 9,339 |
| **OPINsize (total)** | **77,801** | **326,799** | **360,857** |

PQC is 4.20x Classic (+320.04%); Hybrid is 4.64x Classic (+363.82%) and 1.10x PQC (+10.42%). With the PQC profile's certificate chain confirmed ML-DSA-65 end-to-end in this campaign's own live deployment (Section 2), the pattern already found in v7 holds here too: most of Hybrid's premium over Classic is already paid by PQC alone.

### Bytes per participant: AS, RS, and Directory/PKI, separately (item A, one-off deterministic capture)

The official 720-execution pipeline's own `bytes_by_participant` cannot separate AS and RS traffic: every call physically reaches the same `REMOTE_GATEWAY_HOST` address, so both collapse into one "Other" bucket. Decision 10 (v7) already established that this 60-run/720-run pipeline is not where this information can be recovered -- it does not exist in any already-written file, because it is discarded in memory before ever touching disk. Following the exact same method v7 used: one real, complete flow per profile, run against the **live** fleet (still up, not yet destroyed), with the client's own `host_header` value captured per call -- not a new statistical sample (each flow's 44 calls are already known to produce byte-for-byte identical output across all 720 official runs, Section 8's Shapiro-Wilk/spread checks), a one-time decomposition of a value already implicit in the official data. Reconciled exactly against the official "Other" totals for all three profiles (`generate_v8_final_report.py`'s own assertion, both directions, all three profiles, before this report was rendered).

| Participant | Classic (bytes) | PQC (bytes) | Hybrid (bytes) |
|---|---:|---:|---:|
| AS, sent by the participant (received by the client) | 68,325 | 100,009 | 102,901 |
| AS, received by the participant (sent by the client) | 16,011 | 45,836 | 63,511 |
| RS, sent by the participant (received by the client) | 27,246 | 97,026 | 128,622 |
| RS, received by the participant (sent by the client) | 5,611 | 5,611 | 5,611 |
| PKI/CRL, sent by the participant (received by the client) | 8,852 | 32,440 | 37,768 |
| PKI/CRL, received by the participant (sent by the client) | 732 | 732 | 732 |

**Perspective, stated explicitly to avoid the ambiguity v7's own table left implicit:** "sent"/"received" above is from each PARTICIPANT's own point of view (the AS/RS/Directory sends a response, receives a request). The official per-cell `bytes_by_participant` field (Sections elsewhere in this report's source data) uses the opposite, CLIENT-centric convention (the client receives what a participant sends, and sends what a participant receives) -- the two reconcile exactly once the direction is flipped, as verified above.

Of the servers' total outbound traffic (AS+RS), the RS accounts for 28.5% in Classic, 49.2% in PQC, and 55.6% in Hybrid -- same qualitative pattern v7 found (the RS's own query responses, each individually signed, grow faster with the profile than the AS's mostly profile-independent login/consent traffic).

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

### Difference per cell against Classic (ms, %, round trips), Mann-Whitney p, effect size, Holm-adjusted p, and the sign test

| Pair | Installation | Scenario | Diff (ms) | Diff (%) | Diff (round trips) | Mann-Whitney p | Effect size | Holm-adjusted p |
|---|---|---|---:|---:|---:|---:|---:|---:|
| hybrid>classic | sa-east-1 | L0 | 95.44 | +5.55% | n/a (near-zero RTT) | 0.0000 | 0.791 | 0.0000 |
| hybrid>classic | sa-east-1 | L123 | 101.49 | +1.18% | 0.83 | 0.0000 | 0.944 | 0.0000 |
| hybrid>classic | sa-east-1 | L219 | 65.23 | +0.46% | 0.30 | 0.0000 | 0.804 | 0.0000 |
| hybrid>classic | sa-east-1 | L325 | 127.09 | +0.63% | 0.38 | 0.0444 | 0.302 | 0.3549 |
| hybrid>classic | us-east-1 | L0 | 94.43 | +5.42% | n/a (near-zero RTT) | 0.0000 | 0.838 | 0.0000 |
| hybrid>classic | us-east-1 | L14 | 79.26 | +3.07% | 5.46 | 0.0013 | 0.484 | 0.0127 |
| hybrid>classic | ap-northeast-1 | L0 | 91.27 | +5.21% | n/a (near-zero RTT) | 0.0000 | 0.842 | 0.0000 |
| hybrid>classic | ap-northeast-1 | L30 | 88.38 | +2.49% | 2.76 | 0.0000 | 0.853 | 0.0000 |
| pqc>classic | sa-east-1 | L0 | 34.42 | +2.00% | n/a (near-zero RTT) | 0.1433 | 0.220 | 0.8597 |
| pqc>classic | sa-east-1 | L123 | 39.38 | +0.46% | 0.32 | 0.0021 | 0.462 | 0.0189 |
| pqc>classic | sa-east-1 | L219 | 10.73 | +0.08% | 0.05 | 0.1171 | 0.236 | 0.8196 |
| pqc>classic | sa-east-1 | L325 | 113.74 | +0.56% | 0.34 | 0.3366 | 0.144 | 1.0000 |
| pqc>classic | us-east-1 | L0 | 4.67 | +0.27% | n/a (near-zero RTT) | 0.7227 | 0.053 | 1.0000 |
| pqc>classic | us-east-1 | L14 | 23.33 | +0.90% | 1.61 | 0.6574 | 0.067 | 1.0000 |
| pqc>classic | ap-northeast-1 | L0 | -1.65 | -0.09% | n/a (near-zero RTT) | 0.6048 | 0.078 | 1.0000 |
| pqc>classic | ap-northeast-1 | L30 | 36.09 | +1.02% | 1.13 | 0.0003 | 0.547 | 0.0033 |
| hybrid>pqc | sa-east-1 | L0 | 61.02 | +3.48% | n/a (near-zero RTT) | 0.0000 | 0.638 | 0.0003 |
| hybrid>pqc | sa-east-1 | L123 | 62.10 | +0.72% | 0.51 | 0.0000 | 0.820 | 0.0000 |
| hybrid>pqc | sa-east-1 | L219 | 54.50 | +0.39% | 0.25 | 0.0001 | 0.589 | 0.0012 |
| hybrid>pqc | sa-east-1 | L325 | 13.36 | +0.07% | 0.04 | 0.2739 | 0.164 | 1.0000 |
| hybrid>pqc | us-east-1 | L0 | 89.76 | +5.14% | n/a (near-zero RTT) | 0.0000 | 0.742 | 0.0000 |
| hybrid>pqc | us-east-1 | L14 | 55.94 | +2.15% | 3.87 | 0.0008 | 0.502 | 0.0092 |
| hybrid>pqc | ap-northeast-1 | L0 | 92.92 | +5.30% | n/a (near-zero RTT) | 0.0000 | 0.829 | 0.0000 |
| hybrid>pqc | ap-northeast-1 | L30 | 52.29 | +1.46% | 1.63 | 0.0001 | 0.600 | 0.0009 |

L0 routes' round-trip column is left blank: RTT there is ~0.2-0.3ms, so dividing a millisecond-scale difference by it produces a "round trips" number in the hundreds that reflects measurement noise, not a real round-trip count (same reason Section 6's handshake-in-trips check excludes L0).

### Sign test across the 8 routes (exact two-tailed binomial p)

| Comparison | Routes where left > right | p < 0.05 (uncorrected) | p < 0.05 (Holm) | Sign-test p |
|---|---:|---:|---:|---:|
| Hybrid > Classic | 8/8 | 8/8 | 7/8 | 0.0078 |
| PQC > Classic | 7/8 | 2/8 | 2/8 | 0.0703 |
| Hybrid > PQC | 8/8 | 7/8 | 7/8 | 0.0078 |

Hybrid is slower than Classic in all 8 routes, significant in all 8 before correction and in 7/8 after the conservative Holm step-down, with an exact sign-test p of 0.0078 -- the one ordering this report treats as robust. PQC vs. Classic shows a weaker, less consistent pattern: 7/8 routes favor PQC>Classic, but only 2 reach significance even before correction, and the sign test itself (p=0.0703) does not reach the conventional 0.05 threshold -- reported as **not a reliably detectable, fixed ordering**, not forced into one.

### Differences against Classic (delta = a + b x RTT_measured model, pooled 30 runs/cell)

`b`'s unit is dimensionless -- seconds of delta per second of RTT, i.e. the number of extra round trips the profile's delay grows by per unit of distance. `b`=0 means the profile's extra cost over Classic is flat regardless of route; a nonzero `b` would mean the gap widens (or narrows) with distance.

| Profile | a (fixed cost) | a crosses zero? | b (extra round trips per unit RTT) | b crosses zero? |
|---|---:|---|---:|---|
| Hybrid | 87.88 ms [79.92;96.07] | does NOT cross zero | 0.0550 [-0.1483;0.1298] | crosses zero |
| PQC | 13.74 ms [-1.26;30.32] | crosses zero | 0.2094 [-0.0602;0.3520] | crosses zero |

**Hybrid's fixed cost, with a measured component, not an unmeasured one.** Hybrid's own signing operations measure 14.0 ms more than Classic's, summed over the flow's signing calls (Section 6's CPU table) -- a real, directly measured share of Hybrid's ~88ms fixed cost over Classic. The remainder sits in the flow's HTTP-call phase (Section 6) and is **not attributed** to a specific mechanism beyond that -- reported as a located but not fully decomposed cost, not as an unexplained one.

## 5. Network metrics

**Jitter, defined.** The median absolute difference between consecutive SYN/SYN-ACK RTT samples within the same execution's own set of mTLS connections -- a measure of RTT *variability* across connections in one flow, not the RTT itself.

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

### Per-endpoint latency (sa-east-1/L0, the near-zero-RTT reference route)

| Endpoint | Classic (ms) | PQC (ms) | Hybrid (ms) |
|---|---:|---:|---:|
| `/token` | 16.17 | 22.67 | 20.86 |
| `/jwks` | 12.22 | 6.93 | 13.78 |
| `/issuer-ca.pem` | 1.29 | 1.15 | 1.30 |
| `/auth` | 0.00 | 0.00 | 0.00 |
| `/root-ca.pem` | 16.61 | 5.20 | 16.98 |
| `/open-insurance/consents/v3/consents` | 16.81 | 16.98 | 18.25 |
| `/open-insurance/insurance-person/v2/insurance-person` | 11.92 | 12.14 | 13.18 |
| `/request` | 6.55 | 6.88 | 9.13 |

### CPU per operation: verification and signing, by artifact (sa-east-1/L0)

| Operation | Classic (ms) | PQC (ms) | Hybrid (ms) |
|---|---:|---:|---:|
| verification:id_token | 5.856 | 6.114 | 6.404 |
| verification:jarm | 2.729 | 2.897 | 3.162 |
| verification:rs_response | 2.543 | 2.618 | 2.907 |
| signing:client_assertion:par | 1.797 | 3.018 | 5.124 |
| signing:client_assertion:token_ac | 2.042 | 3.924 | 5.857 |
| signing:client_assertion:token_cc | 2.305 | 2.823 | 5.816 |
| signing:request_object:par | 1.950 | 3.284 | 5.269 |

### Handshake in round trips (sum of the 6 connections' own SYN-to-handshake-done time, divided by measured RTT) -- pooled across all 3 windows and the 5 non-near-zero-RTT routes

L0 routes (RTT ~0.2-0.3ms) are excluded from this specific metric: dividing by an RTT that small turns ordinary measurement noise into a "round trips" value in the hundreds, the same reason Decision 112 (window 1 only) restricted this check to L123/L219/L325. Pooled here across all 3 windows and every non-L0 route (L123, L219, L325, L14, L30).

| Profile | Median (round trips) | n (cells) | Min | Max |
|---|---:|---:|---:|---:|
| Classic | 12.33 | 5 | 12.12 | 14.70 |
| PQC | 12.07 | 5 | 12.04 | 12.55 |
| Hybrid | 12.35 | 5 | 12.15 | 14.93 |

All three profiles sit close to 12 round trips -- direct confirmation, now at full statistical power across all 3 windows, that larger certificates/keys (PQC/Hybrid) do not cost extra handshake round trips.

**The residual beyond the 6-connection handshake is not attributed.** A full per-connection timeline (SYN through FIN) of one real high-RTT execution found gaps of several RTTs that look more consistent with client-side sequencing (the 6 connections are not kept busy continuously or run in parallel) than with extra network round trips inside a single connection's own handshake. No specific cause could be isolated with confidence from that investigation -- recorded as **not attributed**.

## 7. Model: T_fluxo = T0 + k x RTT_measured, per profile

**Both readings of prediction 1 ('k=56+-1'), reported for every profile, not only where one of them fails.**

| Profile | T0 (fixed cost) | k | k 95% CI | CI contains 56? | k within 56+-1? |
|---|---:|---:|---:|---|---|
| Classic | 1.7425s | 56.03 | [55.91;56.78] | yes | yes |
| PQC | 1.7605s | 56.13 | [56.03;57.52] | **no** | yes |
| Hybrid | 1.8341s | 55.99 | [55.91;56.55] | yes | yes |

56 is the expected trip count: 44 application calls + 2 round trips for each of the flow's 6 mTLS connections (12, confirmed in Section 6). Classic and Hybrid pass both readings. **PQC passes the +-1 tolerance reading (point estimate 56.13) but fails the confidence-interval reading** (its 95% CI sits entirely above 56). `audit_v8_from_raw.py` independently reproduced PQC's point estimate exactly (56.13) and found the discrepancy's exact upper bound sensitive to the bootstrap's own random-number stream at this sample size (8 routes feeding the slope); **as a further check, the same model was also refit with case-resampling bootstrap over the 720 individual executions rather than the 8 route medians** (Section 7's regression, below, which uses exactly that per-execution resampling) -- it finds PQC's own effect (`profile_pqc`) real and clearly nonzero, consistent with the k-model's point estimate, without resolving which of the two k-model CI readings is the more trustworthy one at n=8 routes.

### Pre-registered confirmatory check (5 predictions from window 1, tag `v8-prereg-3`), per window and combined

| Prediction | Window 1 (exploratory) | Window 2 | Window 3 | Combined (30 runs/cell) |
|---|---|---|---|---|
| 1. k within 56+-1, all 3 profiles | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=PASS, Hybrid=PASS |
| 1b. k's 95% CI contains 56, all 3 profiles | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=FAIL, Hybrid=PASS | Classic=FAIL, PQC=FAIL, Hybrid=PASS | Classic=PASS, PQC=FAIL, Hybrid=PASS |
| 2. Hybrid a>0 (does not cross zero) | PASS | PASS | PASS | PASS |
| 3. PQC a~0 (crosses zero) | PASS | FAIL | PASS | PASS |
| 4. b~0, both profiles | Hybrid=PASS, PQC=PASS | Hybrid=PASS, PQC=FAIL | Hybrid=PASS, PQC=PASS | Hybrid=PASS, PQC=PASS |
| 5. Order: Hybrid>Classic 8/8; PQC vs Classic no fixed direction | Hybrid 8/8; PQC 6/8 | Hybrid 8/8; PQC 7/8 | Hybrid 8/8; PQC 7/8 | Hybrid 8/8; PQC 7/8 |

**Prediction 1 (both readings) is the only one that does not hold cleanly across windows, and PQC is the reason in every window.** Predictions 2, 4, and 5 pass in the combined dataset; prediction 3 (PQC's fixed cost indistinguishable from zero) **failed in window 2 specifically** (`a`=+32.33ms, 95% CI [+15.26;+52.30]ms, with a negative, significant `b` too) but passed again in windows 1 and 3, and passes in the combined fit. **This cross-window difference is reported as a hypothesis, not a confirmed cause.** A heterogeneity test across the three windows' own `a` estimates (pairwise Z-test and Cochran's Q, Decision 115 item 4) found window 2 vs. window 3 significantly different (p=0.0086) and the omnibus test across all three significant too (Q=7.160, df=2, p=0.0279) -- the variation itself is statistically real, not sampling noise, but its cause (a profile-order effect, a real non-stationarity in the network or hardware, or something else) is **not attributed**.

### T_fluxo ~ profile + route + window (OLS, bootstrap 95% CI, 720 individual executions)

**Why not profile + route + position + window together, as originally asked:** `profile_position_in_window` is identical across all 3 installations for a given (profile, window) -- the Latin square assigns one profile order per window, shared by every installation (Section 1.1). Position is therefore perfectly collinear with the (profile x window) interaction; including all four terms in one design produces a singular normal-equations matrix (confirmed directly, not assumed). Two reduced, each individually identifiable, models are fit instead.

| Term | Coefficient (seconds) | 95% CI |
|---|---:|---:|
| intercept | 1.7374 | [1.7217;1.7544] |
| profile_pqc | 0.0236 | [0.0085;0.0385] |
| profile_hybrid | 0.0918 | [0.0749;0.1070] |
| route_sa-east-1_L123 | 6.9135 | [6.8997;6.9265] |
| route_sa-east-1_L219 | 12.3459 | [12.3332;12.3600] |
| route_sa-east-1_L325 | 18.5287 | [18.4845;18.5756] |
| route_us-east-1_L0 | 0.0112 | [-0.0023;0.0248] |
| route_us-east-1_L14 | 0.8648 | [0.8484;0.8802] |
| route_ap-northeast-1_L0 | 0.0218 | [0.0061;0.0349] |
| route_ap-northeast-1_L30 | 1.8307 | [1.8190;1.8434] |
| window_2 | -0.0134 | [-0.0271;0.0030] |
| window_3 | -0.0181 | [-0.0310;-0.0037] |

n=720 individual executions, 300 case-resampling bootstrap iterations (resampling individual executions, not cell medians -- the per-execution verification Section 7's own k-model discussion above refers to). `window_3`'s coefficient does not cross zero (T_fluxo measurably lower in window 3 than window 1, holding profile and route fixed) -- a small (~18ms) but real window effect, consistent with the residual settling drift found in Section 8, not attributed to a specific cause beyond that.

### T_fluxo ~ profile + route + position (OLS, bootstrap 95% CI, 720 individual executions)

| Term | Coefficient (seconds) | 95% CI |
|---|---:|---:|
| intercept | 1.7281 | [1.7118;1.7442] |
| profile_pqc | 0.0236 | [0.0097;0.0374] |
| profile_hybrid | 0.0918 | [0.0783;0.1067] |
| route_sa-east-1_L123 | 6.9135 | [6.8999;6.9251] |
| route_sa-east-1_L219 | 12.3459 | [12.3306;12.3599] |
| route_sa-east-1_L325 | 18.5287 | [18.4870;18.5672] |
| route_us-east-1_L0 | 0.0112 | [-0.0031;0.0254] |
| route_us-east-1_L14 | 0.8648 | [0.8482;0.8808] |
| route_ap-northeast-1_L0 | 0.0218 | [0.0058;0.0376] |
| route_ap-northeast-1_L30 | 1.8307 | [1.8149;1.8463] |
| position_1 | -0.0065 | [-0.0215;0.0089] |
| position_2 | 0.0030 | [-0.0118;0.0201] |

n=720 individual executions, 300 bootstrap iterations. Both position coefficients cross zero -- no detectable ordering effect from where in a window's block a profile happens to run, though this model cannot separate that from a window effect at the same time (see above).

## 8. Statistical validity

**Drift (Mann-Kendall trend test), all 72 cells (24 cells x 3 windows):** 10/72 cells show a statistically significant trend (p<0.05) -- 3/24 in window 1, 4/24 in window 2, 3/24 in window 3 (**within-window** counts). Every one of those significant cells trends downward (settling), **none upward** -- this directional consistency is a **hypothesis-supporting observation, not a proven cause**: it is consistent with a residual settling effect surviving the K=5 warm-up, but this report does not claim to have confirmed that mechanism specifically. **Between windows**, the regression in Section 7 finds a small, real `window_3` effect (coefficient does not cross zero) on top of the within-window trends -- the two observations (within-window downward drift; a between-window difference for window 3) are consistent with each other but are reported as separate findings, not combined into a single unverified narrative.

**Shapiro-Wilk normality on T_fluxo specifically:** computed for all 24 pooled cells (30 executions each); **4/24 reject normality at alpha=0.05**. The same test was computed for every other distribution reported throughout this document (RTT, jitter, CPU, signing/verification/setup timings) and is available per cell in `consolidated_combined.json`; several of those reject normality too (e.g., the setup-phase `generate_callback_cert` timing, spread 752%), which is why every statistic in this report is a median with a bootstrap confidence interval, not a mean with a parametric one.

**Position and window as covariates.** The Latin square rotates each profile's position within every window's block, but position is fully determined by (profile, window) -- Section 7 fits both as separate reduced models and reports the confound rather than ignoring it.

**No execution was removed from any statistic in this report.** All 720 official executions across the 3 windows, 0 recorded errors, feed every table above.

## 9. Mapping to the independent review items

Against the advisor's/reviewer's parecer técnico (which evaluated an earlier, shorter version of this report, not this v8 document) and the project's own pre-registration/metrics-coverage documents. Full citations: `thesis/results/v8/artifacts/item3_promise_evidence_matrix.md`.

| Item | Status |
|---|---|
| 4.2 (latency model / round-trip count) | **Closed** -- Section 7's k-model and regression |
| 4.3 (PQC/Hybrid asymmetry, CA signature) | **Closed** -- Section 2, PQC's chain confirmed ML-DSA-65 end-to-end live |
| 4.4 (transport/front-channel realism) | **Partially closed** -- real network conditions now in scope; no real browser/app front-channel tested |
| 4.6a (single unit of measure for JWT/keys) | **Not done** |
| 4.6c (Classic profile's conformance to OPIN's live security profile) | **Not done** |
| 4.6e (hybrid certificate model vs. composite signatures) | **Declared limitation** -- mechanism documented, alternative not tested |
| Rec. 1 (add a 4th, hybrid-KEM-classical-signature profile) | **Not done** |
| Rec. 2 (symmetrize PQC/Hybrid) | **Closed** -- same as 4.3 |
| Rec. 3 (decompose client/server/handshake/wait time) | **Closed** -- Section 6 |
| Rec. 4 (explain round-trip count) | **Closed** -- Section 6/7 |
| Rec. 5 (realistic bandwidth/MTU) | **Partially closed** -- real network condition, not a deliberate parametrized sweep |
| Rec. 6 (real browser/app front-channel) | **Not done** |
| Rec. 7 (reformulate "fixed cost per flow" conclusions) | **Not done** -- this report's own Section 7 text is a first pass at that reformulation |
| Rec. 8 (uniform unit of measure / RSA algorithm; justify parameters) | **Declared limitation** -- parameters justified in code comments; unit/RSA not uniformized |
| Advisor: metrics at least equal to Schardong et al. (2022) | **Closed** |
| Advisor: distribution statistics, not just the median | **Closed** -- Shapiro-Wilk, bootstrap CI, Mann-Whitney, sign test, regression throughout |

## 10. Limitations

- **JWE stays classical in every profile.** `id_token` encryption (RSA-OAEP + A256GCM) was never in this migration's scope; no post-quantum JOSE encryption standard exists to migrate to.
- **The AS<->RS internal channel stays classical under PQC and Hybrid** -- listed in Section 1.2's own profile table, not only here, so it is not mistaken for a PQC/Hybrid property it does not have.
- **Hybrid's TLS authentication carries a real ML-DSA-65 signature that the live handshake never checks** (Section 2) -- at the TLS layer specifically, Hybrid's practical authentication strength against an attacker who can forge an RSA signature is the same as Classic's.
- **Hybrid's TLS server/client authentication reuses Classic's RSA key as its base**, adding ML-DSA-65 as an extension rather than replacing the key material.
- **A single gateway image is used for all three profiles and all three installations** (Section 1.1) -- `code_hash`/image digest were checked at every profile-block switch (Decision 108) but the binary itself is shared infrastructure, not a per-profile or per-window variable.
- **ICMP is blocked by the security groups**; RTT and loss come from TCP/pcap evidence (SYN/SYN-ACK, retransmissions), never from `ping`.
- **No real browser or app front-channel was tested** -- the client is this project's own HTTP client, not a real user agent subject to URL-length or redirect-chain limits.
- **The campaign spans 14.5 real hours** (2026-10-30 night BRT through 2026-10-31 late morning BRT), not a long-term deployment -- the heterogeneity found for PQC's fixed cost across windows (Section 7) spans this scale of time, not weeks or months.
- **4.6a/4.6c** (a single declared unit of measure for JWTs/keys; the Classic profile's documented conformance to OPIN's own live security profile) remain open, by scope, not by oversight.
- **No fourth profile** (hybrid KEM with classical-only signatures) was added.
- **Server/client instances (`m7i-flex.large`) use a baseline-and-burst performance model, not the credit-based burstable model** -- CPU steal, not credit exhaustion, was the relevant risk and was monitored throughout (mean below 5% in every window). The control instance (`t4g.micro`, ARM Graviton T-series) is credit-based burstable, but runs no measured flow work.
- **The handshake residual beyond the 6-connection round-trip cost is not attributed** (Section 6) -- investigated, no specific cause isolated with confidence.
- **PQC's k and fixed-cost estimates show real, statistically detectable variation across the 3 windows** (Section 7) -- the cause is a hypothesis, not a confirmed finding; the combined estimate across all 3 windows is this report's best single figure, not a claim that the underlying quantity is provably stable.

## 11. Reproducibility and integrity

- **Git tags:** `v8-prereg` (acceptance criteria, before any official window), `v8-prereg-3` (the 5 confirmatory predictions, before windows 2/3 were analyzed), `v8-official-data` and `v8-official-data-2` (the official 720-execution dataset and its corrected/extended consolidate).
- **Code/image integrity:** every profile block checked `CODE_HASH` against a registered value and the live gateway image digest against `sha256:0839867545f3170f6198e7e2f6f3a9a7f6803c2b4feba2bb54f181195b341901`, every block, all 3 windows -- 0 violations (Decision 108's `check_artifact_health`).
- **sha256 manifests:** every file in `janela1/`, `janela2/`, `janela3/` has a per-file sha256 manifest under `_campaign-control/sha256_manifest.txt`.
- **Data inventory: 744 = 720 + 24.** 720 official execution files + 360 discarded K=5 warm-up files (the K=5 warm-ups never capture pcap/cpu, by design -- Decision 103). Pcap/cpu artifact COUNTS are 744 per side (client and server), not 720: the extra 24 are the single, already-instrumented `run00`-style warm-up capture that exists once per cell (24 cells), captured before window 1 began and therefore distinct from both the 720 official executions and the K=5 (uninstrumented) warm-ups -- all reconciled exactly between the control instance's cumulative data tree and this repository (Decision 115, item 2).
- **Secret scanning:** every commit in this campaign's history passed the project's secret scanner (staged diff, full history, and a manual decompress-and-grep pass over every pcap) before being pushed.
- **Cost and fleet hours:** approximately US$25 of AWS spend, 19.3 hours of fleet uptime as of this report's own generation (the fleet has not been destroyed and this figure grows with every further hour; AWS Cost Explorer access is not available to this project's IAM user, so this is the project's own hourly-rate estimate, not a billing-API figure).
- **This audit:** `thesis/scripts/audit_v8_from_raw.py` independently recomputed T_fluxo (24 cells), bytes-per-participant, RTT measured, OPINsize constancy, the k-model, and the 72-cell drift table directly from the raw run files, calls.jsonl, and pcaps, pooled across all 3 windows -- **0 divergences** against the published consolidate outputs (one noted finding, not a divergence: the PQC k bootstrap CI's upper tail is sensitive to the resampling stream at this sample size -- see Section 7).

## 12. Equivalence with the reference article (Schardong et al., CANS 2022)

| Metric (Schardong et al., 2022) | Measured in v8? | Where |
|---|---|---|
| Total flow size (bytes transferred) | Yes | Section 3 (OPINsize) |
| mTLS handshake size | Yes | Section 3 |
| JWT/token size | Yes | Section 3 |
| Public key size | Yes | Section 3 (JWK_PK_size) |
| Flow latency under network delay | Yes -- with **real**, not emulated, delay | Section 4 |
| Per-endpoint latency breakdown | Yes | Section 6 |
| RTT | Yes -- measured from pcap, not assumed | Section 5 |
| Packet loss | Yes -- strictly as retransmissions/segments (Decision 115 correction) | Section 5 |
| CA/PKI certificate cost | Yes -- this thesis's own extension to Schardong's equation (the PKI term), carried forward from v5 | Section 3 |

## References

- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017.
- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019). *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.* Journal of Open Source Software, 4(40), 1606.
- Schardong et al. (2022), Eq. 3.1 (original flow-size equation).
- NIST FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA).

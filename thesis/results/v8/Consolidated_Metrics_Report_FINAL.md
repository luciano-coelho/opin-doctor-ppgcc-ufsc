# Consolidated Experimental Metrics Report: v8, real multi-region AWS campaign

**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, and Hybrid -- real network, three windows, 720 executions**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

## Executive summary

Migrating OPIN's consent flow to post-quantum cryptography multiplies the cryptographic material transferred by 4.20x (PQC) and 4.64x (Hybrid) relative to Classic (77,801 -> 326,799/360,857 bytes per flow). Under real multi-region AWS latency (not emulated), Hybrid is slower than Classic in all 8 routes tested, significant in 7/8 after the conservative Holm correction (exact sign-test p=0.0078) -- the joint regression model (profile+route+position+window, Section 7) puts Hybrid's own effect at 91.8ms per execution. PQC's measured effect is smaller but still real and nonzero: 23.6ms per execution [9.0;38.1] (95% CI, 10,000-iteration bootstrap over the 720 individual executions) -- detectable in the regression even though PQC vs. Classic's own route-by-route ordering is not consistent enough to pass the sign test (p=0.070). A fixed-cost/distance-scaling model (T_fluxo = T0 + k x RTT) holds closely for Classic and Hybrid (k near the expected 56 round trips); PQC's own k sits just outside its confidence interval around 56 in the combined dataset, and PQC's fixed cost varies in a statistically detectable way between the 3 collection windows -- both reported as open, not-fully-explained findings, not smoothed over. A live, pre-destroy audit confirmed PQC's certificate chain is ML-DSA-65 end-to-end, and a second live diagnostic session confirmed PQC **does** interoperate with a standard OpenSSL 3.5.8 client once the correct TLS signature-algorithm flag is set -- an earlier draft of this report wrongly called the opposite a "library finding" (Section 2). JWE encryption and the AS-to-RS internal channel remain classical in every profile, by explicit, already-declared scope decision.

## 1. Scope and what changed from v7

### 1.1. From emulated to real network latency

Every prior version of this thesis (v1-v7) measured the cost of the OPIN post-quantum migration under network latency **emulated** with `tc`/`netem` on a single machine, one Docker Desktop host running every participant. This version (v8) replaces that emulation with a **real multi-region AWS deployment**: one complete server stack (the mTLS gateway, the authorization server, the resource server, and the directory mock) per installation, and a separate client instance in a different AWS region, so the measured round-trip time is the real network's own, not an injected value.

**Relation to v7.** v7 fixed a real measurement artifact (a container-spawn cost contaminating every PQC/Hybrid signing call) and closed the PQC profile's certificate chain to be post-quantum end-to-end at the CA level; this report inherits both fixes as a starting point and adds a dimension v7 never attempted: a real network, instead of a single-host emulation of one. v7 itself never measured handshake round trips or repeated the experiment across multiple independent collection windows, so neither "12 round trips" nor "PQC's fixed cost is stable" are v7 findings being replicated here -- both are new to v8 (Decision 112; Section 7). What does carry over directly is a real accounting gap: v7's own published Classic OPINsize (76,929 bytes) undercounts `N_JWK` the same way this report's own first draft did (2 instead of the real 4 `/jwks` calls per execution, Section 3) -- correcting for that alone accounts for 512 of the 872-byte gap between v7's reported Classic total and v8's own (77,801 bytes); the remaining 360 bytes come from a slightly larger measured `handshake_bytes` in this real environment. This is reported here as a reconciliation of v8's own number against v7's published one, not as a correction this document makes to v7's own results.

**Infrastructure.** Server and client instances: `m7i-flex.large` -- an Intel-based "flex" instance type with a baseline-and-burst performance model, **not** the credit-based burstable model of the T-series. The control instance (orchestration only, never part of any measured flow): `t4g.micro`, an ARM Graviton T-series instance, which **is** credit-based burstable. CPU steal was monitored on the measured instances throughout the campaign (mean below 5% in every window); the control instance's own credit behavior was not specifically tested, since it does no flow work. **A single gateway image** is used for all three profiles and all three installations (the profile is selected at runtime by `CRYPTO_PROFILE`, not by a separate image per profile) -- its digest was checked at every profile-block switch against one registered value, all 3 windows, 0 mismatches.

**Topology.** Three server installations (`sa-east-1`, `us-east-1`, `ap-northeast-1`), eight client scenarios across them (four routes from `sa-east-1` -- `L0`, co-located; `L123`, `L219`, `L325` -- and two each from `us-east-1` and `ap-northeast-1` -- `L0` and `L14`/`L30`), chosen empirically by real measured RTT rather than assumed from the literature. Each of the three crypto profiles (Classic, PQC, Hybrid) runs the identical client code against every route. **The AS-to-RS internal channel stays classical (`CurveP256`) in every profile, including PQC and Hybrid.** This is not new migration scope left undone -- this internal channel was ALREADY classical, before any PQC work on this thesis began, kept that way on purpose by a server-side SNI carve-out: `mock_mtls`'s `GetConfigForClient` always answers the internal hostname `matls-api.local` with classical-only curve preferences, regardless of `CRYPTO_PROFILE` -- the AS's own calls to the RS use that SNI and therefore never see the active profile's PQC/Hybrid group, on every one of the 720 executions (confirmed by gateway-log correlation, 0 violations).

**Collection.** Three official windows of 10 executions per profile per route (`24 cells x 10 = 240 executions per window`), run in sequential campaign mode with automatic advance between windows (zero errors and mean CPU steal below 5% required), for **720 total official executions**. **Reconciled against each window's own first/last execution timestamp:**

| Window | First execution (UTC) | Last execution (UTC) | Span |
|---|---|---|---:|
| 1 | 2026-10-30T23:12:57 | 2026-10-31T03:32:32 | 4.33h |
| 2 | 2026-10-31T04:14:29 | 2026-10-31T08:38:42 | 4.40h |
| 3 | 2026-10-31T09:19:39 | 2026-10-31T13:41:43 | 4.37h |

Each window follows a circulant Latin square (seed 0) rotating the order in which the three profiles run within each installation block -- **the same order for every installation in a given window**, so a profile's position within a window's block depends on (profile, window). Section 7 proves directly (not merely assumes) whether this makes the joint profile+route+position+window regression unidentifiable.

**Warm-up.** Before any official execution, **K=5 warm-up runs per cell are discarded and kept separately** (`warmup/w{window}_warm{01..05}.json`, never read by any statistic in this report) -- a number chosen because it covered 100% of the settling trend found in a prior **pilot's** 24 cells (10/24 showed a significant trend with fewer warm-up runs). This does not mean the official windows show zero residual drift: Section 8 finds 10/72 official cells still show a statistically significant (if small) downward trend even after K=5 -- the warm-up's own 100% figure describes the pilot it was sized from, not a claim that the official data is drift-free.

**Pre-registration.** Five quantitative predictions were derived from window 1's own data and pre-registered, before windows 2 and 3 were analyzed, as confirmatory for those two windows (`ANALYSIS_PLAN.md`, tag `v8-prereg-3`). Section 7 reports the outcome of all five, per window and combined, including the one that did not hold up.

Every number in this document is read or computed from `thesis/results/v8/global_v2/report_data_v8_combined.json` and `consolidated_combined.json`, independently recomputed from the raw per-execution files and pcaps (`thesis/scripts/audit_v8_from_raw.py`) -- same convention as v7's own `audit_v7_from_raw.py`.

### 1.2. The three profiles (unchanged from v7, with one addition spelled out)

| Profile | Signatures | TLS key exchange | AS<->RS internal channel |
|---|---|---|---|
| Classic | RSA (PS256) | ECDHE, single P-384 curve | Classical (`CurveP256`) |
| PQC | Pure ML-DSA-65 (NIST FIPS 204) throughout: tokens, subject keys, and every certificate's own issuer signature, root included | Pure ML-KEM-1024 (NIST FIPS 203) | **Classical (`CurveP256`), kept that way by the SNI carve-out described in Section 1.1 -- unchanged from Classic** |
| Hybrid | RSA and ML-DSA-65 combined: certificates with a dual signature in non-critical X.509 extensions; payload extension on client-issued JWTs; Strong Nesting on server-issued JWTs | SecP384r1MLKEM1024 (P-384 + ML-KEM-1024) | **Classical (`CurveP256`), same carve-out -- unchanged from Classic** |

Across all three profiles, `id_token` encryption (RSA-OAEP with AES-256-GCM) remains classical, by explicit, declared scope decision -- there is no post-quantum JOSE encryption standard, and the encryption key exchange was never part of this project's migration scope (`thesis/scripts/opin_flow.py:798-802`).

## 2. Profiles and the layer matrix

A live, pre-destroy audit (Decision 116) verified every cryptographic layer of a real, still-running deployment -- not a re-derivation from static files. OpenSSL version on the probing host: `OpenSSL 3.5.8 25 Aug 2026`.

**PQC's interoperability with plain OpenSSL, diagnosed properly (correcting Decision 115/116).** An earlier probe called PQC's failure to negotiate with `openssl s_client -groups MLKEM1024` a "real cross-implementation finding... not a project defect." **That framing was wrong**, found by splitting the attempt into its three independent pieces and testing each on the live fleet:

- **(a) Key exchange alone.** `-groups MLKEM1024` fails with a fatal `handshake_failure` alert. `-msg` shows OpenSSL's own ClientHello offering group `0x0202` (514) -- the **exact same codepoint** Go's `crypto/tls` registers for `MLKEM1024` (`common.go:158`, confirmed by inspecting the real `golang:1.27-rc-alpine` image this project uses). The group codepoints were never mismatched.
- **(b) TLS signature algorithms -- the actual cause.** OpenSSL's default `signature_algorithms` list does not include ML-DSA-65; the PQC server certificate has no other signature scheme to offer for `CertificateVerify`, so the handshake fails for lack of a shared signature algorithm, not a shared group. Adding `-sigalgs MLDSA65` to the exact same command **succeeds**: `Negotiated TLS1.3 group: MLKEM1024`, `Peer signature type: mldsa65`, full application data exchanged. Isolated the other way too: `-sigalgs MLDSA65` alone, without `-groups MLKEM1024`, also fails (no common group) -- both flags are independently required.
- **(c) Certificate and chain.** `openssl verify` against the real ML-DSA-65 CA chain (`root_ca_pqc.crt` + `issuer_ca_pqc.crt`) returns `mtls_pqc.crt: OK`. In the live connection (both flags set), the one remaining `Verify return code: 26 (unsuitable certificate purpose)` is the same pre-existing EKU/purpose quirk already found for Classic and Hybrid -- not new, not PQC-specific.

**Conclusion: this was a test-configuration gap in the earlier probe, not an OpenSSL limitation and not a gateway defect.** Once the ClientHello offers both `MLKEM1024` and `id-ml-dsa-65` -- exactly what the real client (`tls_kem_proxy`) already does automatically -- OpenSSL 3.5.8 and this project's Go gateway interoperate completely for PQC. Full diagnosis: `thesis/results/v8/artifacts/pqc/openssl_interop_diagnosis.md`.

| Layer | Classic | PQC | Hybrid | Verified how |
|---|---|---|---|---|
| TLS key exchange | ECDH secp384r1 | ML-KEM-1024 | SecP384r1MLKEM1024 | `openssl s_client` (all 3 profiles, live, with the correct `-groups`/`-sigalgs` for PQC) |
| TLS server certificate -- the key the LIVE HANDSHAKE actually authenticates | RSA-4096 | ML-DSA-65 (pure) | **RSA-4096 base + a non-critical ML-DSA-65 extension the TLS handshake itself never checks** | `openssl x509 -text`, live |
| TLS client certificate -- same caveat | RSA-4096 | ML-DSA-65 (pure) | **RSA-4096 + AltSignatureValue (ML-DSA-65), same caveat** | Signed-challenge verification, live |
| Certificate chain (root, issuer) | RSA | **ML-DSA-65** (both levels) | RSA (classical root reused) | `openssl x509 -text` + `openssl verify`, live |
| JWT signatures (client_assertion, request object, id_token, JARM) | PS256 | ML-DSA-65 (pure) | Strong Nesting (PS256+ML-DSA-65) or payload-extension (RS256+ML-DSA-65), by artifact | Dual-signature verification |
| JWE (`id_token` encryption) | RSA-OAEP + A256GCM | **identical to Classic** | **identical to Classic** | Declared scope limitation, not migrated |
| Internal AS->RS connection | CurveP256 (SNI carve-out, Section 1.1) | **identical to Classic** | **identical to Classic** | Gateway-log correlation, all 720 executions, 0 violations |
| Directory/PKI chain | RSA | **ML-DSA-65** (both levels) | RSA (classical root reused) | `openssl x509 -text`, live |

**Every cell that reads differently from what its profile's label suggests, enumerated (not left implicit):**

1. **JWE stays identical across all three profiles** -- `id_token` encryption was never migrated, by declared scope decision (Section 1.2).
2. **The AS<->RS internal channel stays classical under PQC and Hybrid**, by the SNI carve-out described in Section 1.1 -- not a new limitation, a pre-existing one from before this thesis's PQC work.
3. **Hybrid's JWT `alg` header reads `PS256`** even when the underlying signature is the dual Strong Nesting construction -- a reader checking only the header sees a classical algorithm where a second, real ML-DSA-65 signature also exists.
4. **Hybrid's TLS authentication, in one sentence: the live connection is secured by RSA alone.** Hybrid's TLS server and client certificates carry a real ML-DSA-65 signature (the `AltSignatureValue` X.509 extension) that the live TLS handshake itself never checks -- X.509 non-critical extensions are, by the standard's own definition, not required to be processed by a verifier that doesn't understand them, and Go's `crypto/tls` (both sides of this project's real connections) validates only the certificate's primary RSA signature during the handshake. The ML-DSA-65 signature is real and independently checkable out-of-band (confirmed live via `-verify-hybrid`'s own preTBS reconstruction), but nothing in the live connection path verifies it -- Hybrid's practical TLS-layer message authentication is exactly as strong as Classic's against an attacker who can forge an RSA signature; the added PQC signature is present but currently inert at this layer.

Full matrix, with file:line evidence for every cell: `thesis/results/v8/artifacts/item1_layer_matrix.md`.

## 3. Size results: the OPINsize equation

Same equation this thesis has used since v5 (extending Schardong et al.'s Eq. 3.1 with the PKI term):

```
OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x PKI_bytes
```

All four `N_x` counts are identical across profiles and across all 8 real routes (verified by `audit_v8_from_raw.py`); only the per-item byte size changes. **`N_JWK = 4`, read directly from the raw data's own call count, not assumed from v7's flow structure** -- the flow calls `/jwks` 4 times per execution, every one of the 4 carrying a `sig`-use JWK entry of the same size (confirmed by `audit_v8_from_raw.py`); the separate `enc`-use key used for JWE (Section 2) is fetched in the same calls but is not part of this equation's `JWK_PK_size` term.

| Term | Classic | PQC | Hybrid |
|---|---:|---:|---:|
| handshake_bytes (per connection, N_mTLS=6) | 5,179 | 22,607 | 19,017 |
| JWT_size (average, N_JWT=28) | 1,330.82 | 5,404.32 | 7,163.11 |
| JWK_PK_size (per key, N_JWK=4) | 256 | 1,952 | 2,208 |
| PKI_bytes (average, PEM body, N_PKI=4) | 2,110 | 8,007 | 9,339 |
| **OPINsize (total)** | **77,801** | **326,799** | **360,857** |

PQC is 4.20x Classic (+320.04%); Hybrid is 4.64x Classic (+363.82%) and 1.10x PQC (+10.42%). With the PQC profile's certificate chain confirmed ML-DSA-65 end-to-end in this campaign's own live deployment (Section 2), the pattern already found in v7 holds here too: most of Hybrid's premium over Classic is already paid by PQC alone.

### 4.6a: JWT size, raw and base64url-encoded

The equation above uses the JWT's raw (decoded) size. The independent review's own item 4.6a asked for a single, stated unit of measure; computed directly from the same captured tokens used throughout this report (one representative JWT per profile, the `id_token`):

| Profile | Raw/decoded (bytes) | base64url-encoded, compact serialization (bytes) |
|---|---:|---:|
| Classic | 729 | 975 |
| PQC | 3,525 | 4,703 |
| Hybrid | 5,182 | 6,912 |

This report's own OPINsize equation (and Section 3's `JWT_size` term above) uses the **compact-serialization, base64url-encoded** size throughout -- the size actually transferred over the wire in an `Authorization` header or a JSON field, not the decoded byte count, stated here explicitly as the single unit of measure 4.6a asked for.

### Bytes per participant: AS, RS, and Directory/PKI, separately (item A, one-off deterministic capture)

The official 720-execution pipeline's own `bytes_by_participant` cannot separate AS and RS traffic: every call physically reaches the same `REMOTE_GATEWAY_HOST` address, so both collapse into one "Other" bucket. Decision 10 (v7) already established that this pipeline is not where this information can be recovered -- it does not exist in any already-written file, because it is discarded in memory before ever touching disk. Following the exact same method v7 used: one real, complete flow per profile, run against the **live** fleet, with the client's own `host_header` value captured per call -- not a new statistical sample (each flow's 44 calls are already known to produce byte-for-byte identical output across all 720 official runs, Section 8's Shapiro-Wilk/spread checks), a one-time decomposition of a value already implicit in the official data. Reconciled exactly against the official "Other" totals for all three profiles.

| Participant | Classic (bytes) | PQC (bytes) | Hybrid (bytes) |
|---|---:|---:|---:|
| AS, sent by the participant (received by the client) | 68,325 | 100,009 | 102,901 |
| AS, received by the participant (sent by the client) | 16,011 | 45,836 | 63,511 |
| RS, sent by the participant (received by the client) | 27,246 | 97,026 | 128,622 |
| RS, received by the participant (sent by the client) | 5,611 | 5,611 | 5,611 |
| PKI/CRL, sent by the participant (received by the client) | 8,852 | 32,440 | 37,768 |
| PKI/CRL, received by the participant (sent by the client) | 732 | 732 | 732 |

**Perspective, stated explicitly:** "sent"/"received" above is from each PARTICIPANT's own point of view (the AS/RS/Directory sends a response, receives a request). The official per-cell `bytes_by_participant` field uses the opposite, CLIENT-centric convention (the client receives what a participant sends, and sends what a participant receives) -- the two reconcile exactly once the direction is flipped, as verified above.

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

**Definitions, stated explicitly.** Mann-Whitney's "side" here is always `pair`'s left profile vs. its right profile (e.g. for `hybrid>classic`, the test asks whether Hybrid's distribution is shifted above Classic's); **effect size** is the rank-biserial correlation `1 - 2U/(n1*n2)`, ranging from -1 (every left-profile value below every right-profile value) to +1 (every left-profile value above), with 0 meaning no detectable shift. The round-trips column divides the ms difference by that route's own measured Classic RTT; **left blank for L0 routes**, where RTT is ~0.2-0.3ms and dividing a millisecond-scale difference by it would turn ordinary measurement noise into a "round trips" figure in the hundreds, not a real round-trip count (same reason Section 6's handshake-in-trips check excludes L0).

| Pair | Installation | Scenario | Diff (ms) | Diff (%) | Diff (round trips) | Mann-Whitney p | Effect size | Holm-adjusted p |
|---|---|---|---:|---:|---:|---:|---:|---:|
| hybrid>classic | sa-east-1 | L0 | 95.44 | +5.55% | -- | 0.0000 | 0.791 | 0.0000 |
| hybrid>classic | sa-east-1 | L123 | 101.49 | +1.18% | 0.83 | 0.0000 | 0.944 | 0.0000 |
| hybrid>classic | sa-east-1 | L219 | 65.23 | +0.46% | 0.30 | 0.0000 | 0.804 | 0.0000 |
| hybrid>classic | sa-east-1 | L325 | 127.09 | +0.63% | 0.38 | 0.0444 | 0.302 | 0.3549 |
| hybrid>classic | us-east-1 | L0 | 94.43 | +5.42% | -- | 0.0000 | 0.838 | 0.0000 |
| hybrid>classic | us-east-1 | L14 | 79.26 | +3.07% | 5.46 | 0.0013 | 0.484 | 0.0127 |
| hybrid>classic | ap-northeast-1 | L0 | 91.27 | +5.21% | -- | 0.0000 | 0.842 | 0.0000 |
| hybrid>classic | ap-northeast-1 | L30 | 88.38 | +2.49% | 2.76 | 0.0000 | 0.853 | 0.0000 |
| pqc>classic | sa-east-1 | L0 | 34.42 | +2.00% | -- | 0.1433 | 0.220 | 0.8597 |
| pqc>classic | sa-east-1 | L123 | 39.38 | +0.46% | 0.32 | 0.0021 | 0.462 | 0.0189 |
| pqc>classic | sa-east-1 | L219 | 10.73 | +0.08% | 0.05 | 0.1171 | 0.236 | 0.8196 |
| pqc>classic | sa-east-1 | L325 | 113.74 | +0.56% | 0.34 | 0.3366 | 0.144 | 1.0000 |
| pqc>classic | us-east-1 | L0 | 4.67 | +0.27% | -- | 0.7227 | 0.053 | 1.0000 |
| pqc>classic | us-east-1 | L14 | 23.33 | +0.90% | 1.61 | 0.6574 | 0.067 | 1.0000 |
| pqc>classic | ap-northeast-1 | L0 | -1.65 | -0.09% | -- | 0.6048 | 0.078 | 1.0000 |
| pqc>classic | ap-northeast-1 | L30 | 36.09 | +1.02% | 1.13 | 0.0003 | 0.547 | 0.0033 |
| hybrid>pqc | sa-east-1 | L0 | 61.02 | +3.48% | -- | 0.0000 | 0.638 | 0.0003 |
| hybrid>pqc | sa-east-1 | L123 | 62.10 | +0.72% | 0.51 | 0.0000 | 0.820 | 0.0000 |
| hybrid>pqc | sa-east-1 | L219 | 54.50 | +0.39% | 0.25 | 0.0001 | 0.589 | 0.0012 |
| hybrid>pqc | sa-east-1 | L325 | 13.36 | +0.07% | 0.04 | 0.2739 | 0.164 | 1.0000 |
| hybrid>pqc | us-east-1 | L0 | 89.76 | +5.14% | -- | 0.0000 | 0.742 | 0.0000 |
| hybrid>pqc | us-east-1 | L14 | 55.94 | +2.15% | 3.87 | 0.0008 | 0.502 | 0.0092 |
| hybrid>pqc | ap-northeast-1 | L0 | 92.92 | +5.30% | -- | 0.0000 | 0.829 | 0.0000 |
| hybrid>pqc | ap-northeast-1 | L30 | 52.29 | +1.46% | 1.63 | 0.0001 | 0.600 | 0.0009 |

### Sign test across the 8 routes (exact two-tailed binomial p)

| Comparison | Routes where left > right | p < 0.05 (uncorrected) | p < 0.05 (Holm) | Sign-test p |
|---|---:|---:|---:|---:|
| Hybrid > Classic | 8/8 | 8/8 | 7/8 | 0.0078 |
| PQC > Classic | 7/8 | 2/8 | 2/8 | 0.0703 |
| Hybrid > PQC | 8/8 | 7/8 | 7/8 | 0.0078 |

Hybrid is slower than Classic in all 8 routes, significant in all 8 before correction and in 7/8 after the conservative Holm step-down, with an exact sign-test p of 0.0078 -- the one ordering this report treats as robust. PQC vs. Classic shows a weaker, less consistent pattern: 7/8 routes favor PQC>Classic, but only 2 reach significance even before correction, and the sign test itself (p=0.0703) does not reach the conventional 0.05 threshold -- reported as **not a reliably detectable, fixed ordering** at the per-route level, even though Section 7's regression (which pools all 720 executions rather than testing route by route) does detect a real, nonzero PQC effect.

### Differences against Classic (delta = a + b x RTT_measured model, pooled 30 runs/cell)

`b`'s unit is dimensionless -- seconds of delta per second of RTT, i.e. the number of extra round trips the profile's delay grows by per unit of distance. `b`=0 means the profile's extra cost over Classic is flat regardless of route; a nonzero `b` would mean the gap widens (or narrows) with distance.

| Profile | a (fixed cost) | a crosses zero? | b (extra round trips per unit RTT) | b crosses zero? |
|---|---:|---|---:|---|
| Hybrid | 87.88 ms [79.92;96.07] | does NOT cross zero | 0.0550 [-0.1483;0.1298] | crosses zero |
| PQC | 13.74 ms [-1.26;30.32] | crosses zero | 0.2094 [-0.0602;0.3520] | crosses zero |

**Hybrid's fixed cost, decomposed phase by phase (sa-east-1/L0, Hybrid minus Classic):**

| Phase | Hybrid - Classic (ms) |
|---|---:|
| HTTP calls | 48.8 |
| Signing | 28.5 |
| Verification | 3.1 |
| Residual | 13.8 |
| Setup/teardown | 0.5 |
| **Sum (this route)** | **94.6** |

This phase-level sum (94.6ms, at the single near-zero-RTT reference route) is not identical to the ~88ms `a` coefficient from the all-8-routes delta model above -- they are different fits (one route vs. all eight) -- but both locate most of Hybrid's fixed cost in the same two phases: HTTP calls (48.8ms) and signing (28.5ms). The signing component is a directly measured CPU cost (Section 6's per-operation table); the HTTP-call component is the single largest share and is **not attributed** to a more specific mechanism beyond "time spent in the flow's HTTP calls" -- located, not fully decomposed.

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
| `/jwks` | 12.22 | 6.93 | 13.78 |
| `/token` | 16.17 | 22.67 | 20.86 |
| `/open-insurance/insurance-person/v2/insurance-person` | 11.92 | 12.14 | 13.18 |
| `/auth` | 0.00 | 0.00 | 0.00 |
| `/root-ca.pem` | 16.61 | 5.20 | 16.98 |
| `/issuer-ca.pem` | 1.29 | 1.15 | 1.30 |
| `/open-insurance/consents/v3/consents` | 16.81 | 16.98 | 18.25 |
| `/request` | 6.55 | 6.88 | 9.13 |

**`/auth` = 0.00ms, explained, not just shown.** Its own raw call record has `start_utc` and `end_utc` identical to the microsecond (`2026-10-30T23:13:01.872106+00:00`) and a `303 See Other` response, with `src: "login"` -- this call belongs to the automated login/consent interaction, which (v7 Decision 12) never routes through the timed `do_call()` path at all. The 0.00ms is an artifact of that call never being timed, not a real sub-millisecond server response.

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

### Handshake in round trips (sum of the 6 connections' own SYN-to-handshake-done time, divided by measured RTT) -- pooled across all 3 windows, per route

L0 routes are excluded from the round-trips column (RTT ~0.2-0.3ms -- same reason given in Section 4); shown instead in milliseconds only, which remains meaningful at any RTT.

| Installation | Scenario | Classic | PQC | Hybrid |
|---|---|---:|---:|---:|
| sa-east-1 | L123 | 12.33 | 12.07 | 12.35 |
| sa-east-1 | L219 | 12.19 | 12.04 | 12.20 |
| sa-east-1 | L325 | 12.12 | 12.05 | 12.15 |
| us-east-1 | L14 | 14.70 | 12.55 | 14.93 |
| ap-northeast-1 | L30 | 13.23 | 12.25 | 13.38 |

**L0, handshake duration in milliseconds (round trips not meaningful at this RTT):**

| Profile | Median handshake time (ms, sa-east-1/L0) | n |
|---|---:|---:|
| Classic | 43.62 | 30 |
| PQC | 10.32 | 30 |
| Hybrid | 45.99 | 30 |

**Pooled across all 3 windows and the 5 non-L0 routes, per profile:**

| Profile | Median (round trips) | n (cells) | Min | Max |
|---|---:|---:|---:|---:|
| Classic | 12.33 | 5 | 12.12 | 14.70 |
| PQC | 12.07 | 5 | 12.04 | 12.55 |
| Hybrid | 12.35 | 5 | 12.15 | 14.93 |

All three profiles sit close to 12 round trips -- direct confirmation, now at full statistical power across all 3 windows and every non-L0 route, that larger certificates/keys (PQC/Hybrid) do not cost extra handshake round trips.

**The residual beyond the 6-connection handshake is not attributed.** A full per-connection timeline (SYN through FIN) of one real high-RTT execution found gaps of several RTTs that look more consistent with client-side sequencing (the 6 connections are not kept busy continuously or run in parallel) than with extra network round trips inside a single connection's own handshake. No specific cause could be isolated with confidence from that investigation -- recorded as **not attributed**.

## 7. Model: T_fluxo = T0 + k x RTT_measured, per profile

**Both readings of prediction 1 ('k=56+-1'), reported for every profile, not only where one of them fails.**

| Profile | T0 (fixed cost) | k | k 95% CI | CI contains 56? | k within 56+-1? |
|---|---:|---:|---:|---|---|
| Classic | 1.7425s | 56.03 | [55.91;56.78] | yes | yes |
| PQC | 1.7605s | 56.13 | [56.03;57.52] | **no** | yes |
| Hybrid | 1.8341s | 55.99 | [55.91;56.55] | yes | yes |

56 is the expected trip count: 44 application calls + 2 round trips for each of the flow's 6 mTLS connections (12, confirmed in Section 6). Classic and Hybrid pass both readings. **PQC passes the +-1 tolerance reading (point estimate 56.13) but fails the confidence-interval reading** (its 95% CI sits entirely above 56) -- `audit_v8_from_raw.py` independently reproduced the point estimate exactly and found the CI's exact upper bound sensitive to the bootstrap's own random-number stream at this sample size (8 routes feeding the slope).

### Pre-registered confirmatory check (5 predictions from window 1, tag `v8-prereg-3`), per window and combined

| Prediction | Window 1 (exploratory) | Window 2 | Window 3 | Combined (30 runs/cell) |
|---|---|---|---|---|
| 1. k within 56+-1, all 3 profiles | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=PASS, Hybrid=PASS |
| 1b. k's 95% CI contains 56, all 3 profiles | Classic=PASS, PQC=PASS, Hybrid=PASS | Classic=PASS, PQC=FAIL, Hybrid=PASS | Classic=FAIL, PQC=FAIL, Hybrid=PASS | Classic=PASS, PQC=FAIL, Hybrid=PASS |
| 2. Hybrid a>0 (does not cross zero) | PASS | PASS | PASS | PASS |
| 3. PQC a~0 (crosses zero) | PASS | FAIL | PASS | PASS |
| 4. b~0, both profiles | Hybrid=PASS, PQC=PASS | Hybrid=PASS, PQC=FAIL | Hybrid=PASS, PQC=PASS | Hybrid=PASS, PQC=PASS |
| 5. Order: Hybrid>Classic 8/8; PQC vs Classic no fixed direction | Hybrid 8/8; PQC 6/8 | Hybrid 8/8; PQC 7/8 | Hybrid 8/8; PQC 7/8 | Hybrid 8/8; PQC 7/8 |

**Prediction 1b fails for more than just PQC: Classic itself fails 1b in window 3** (its own k-CI misses 56 in that window alone, Classic=PASS everywhere else) -- stated plainly, since the pattern is not "PQC is the reason in every window." Predictions 2, 4, and 5 pass in the combined dataset; prediction 3 (PQC's fixed cost indistinguishable from zero) **failed in window 2 specifically** (`a`=+32.33ms, 95% CI [+15.26;+52.30]ms, with a negative, significant `b` too) but passed again in windows 1 and 3, and passes in the combined fit. **This cross-window difference is reported as a hypothesis, not a confirmed cause.** A heterogeneity test across the three windows' own `a` estimates (pairwise Z-test and Cochran's Q, Decision 115 item 4) found window 2 vs. window 3 significantly different (p=0.0086) and the omnibus test across all three significant too (Q=7.160, df=2, p=0.0279) -- the variation itself is statistically real, not sampling noise, but its cause (a profile-order effect, a real non-stationarity in the network or hardware, or something else) is **not attributed**.

### T_fluxo ~ profile + route + position + window, fit as ONE joint model

**Correcting this report's own earlier claim.** An earlier draft asserted this joint design was rank-deficient (position supposedly collinear with profile x window) without actually computing the rank. Checked directly now, two ways: `matrix_rank()` on the real design reports **14/14, full rank**, and the normal equations solve without error on the real, non-bootstrapped 720 rows. The reasoning behind the original (wrong) claim missed that `profile_position_in_window` depends on the (profile, window) **interaction** under this campaign's specific Latin square, not on the profile and window **main effects** alone -- and only the main effects are in this design, so the exact linear dependency the original claim assumed does not actually hold. One joint model is fit, not two reduced ones.

| Term | Coefficient (seconds) | 95% CI |
|---|---:|---:|
| intercept | 1.7386 | [1.7191;1.7571] |
| profile_pqc | 0.0236 | [0.0090;0.0381] |
| profile_hybrid | 0.0918 | [0.0759;0.1078] |
| route_sa-east-1_L123 | 6.9135 | [6.9004;6.9267] |
| route_sa-east-1_L219 | 12.3459 | [12.3316;12.3603] |
| route_sa-east-1_L325 | 18.5287 | [18.4851;18.5720] |
| route_us-east-1_L0 | 0.0112 | [-0.0031;0.0254] |
| route_us-east-1_L14 | 0.8648 | [0.8490;0.8811] |
| route_ap-northeast-1_L0 | 0.0218 | [0.0072;0.0367] |
| route_ap-northeast-1_L30 | 1.8307 | [1.8168;1.8454] |
| position_1 | -0.0065 | [-0.0212;0.0081] |
| position_2 | 0.0030 | [-0.0122;0.0180] |
| window_2 | -0.0134 | [-0.0293;0.0021] |
| window_3 | -0.0181 | [-0.0317;-0.0036] |

n=720 individual executions, 10,000 case-resampling bootstrap iterations (fixed seed, resampling individual executions with replacement and refitting, not resampling cell medians). `profile_pqc` and `profile_hybrid` both have confidence intervals that do not cross zero -- both profiles carry a real, measured cost over Classic, holding route, position, and window fixed simultaneously. `window_3`'s coefficient also does not cross zero (T_fluxo measurably lower in window 3 than window 1, holding profile and route fixed) -- a small (~18ms) but real window effect, consistent with the residual settling drift found in Section 8, not attributed to a specific cause beyond that. Both position coefficients cross zero -- no detectable ordering effect from where in a window's block a profile happens to run.

## 8. Statistical validity

**Drift (Mann-Kendall trend test), all 72 cells (24 cells x 3 windows):** 10/72 cells show a statistically significant trend (p<0.05) -- 3/24 in window 1, 4/24 in window 2, 3/24 in window 3. Every one of those significant cells trends downward (settling), **none upward**; the magnitude (Kendall's tau) of the significant cells ranges from -0.644 to -0.511 (more negative = steeper decline). This directional consistency is a **hypothesis-supporting observation, not a proven cause**: it is consistent with a residual settling effect surviving the K=5 warm-up, but this report does not claim to have confirmed that mechanism specifically. **Between windows**, Section 7's joint regression finds a small, real `window_3` effect (coefficient does not cross zero) on top of the within-window trends -- the two observations are consistent with each other but are reported as separate findings, not combined into a single unverified narrative.

**Shapiro-Wilk normality on T_fluxo specifically:** computed for all 24 pooled cells (30 executions each); **4/24 reject normality at alpha=0.05**. The same test was computed for every other distribution reported throughout this document (RTT, jitter, CPU, signing/verification/setup timings) and is available per cell in `consolidated_combined.json`; several of those reject normality too (e.g., the setup-phase `generate_callback_cert` timing, spread 752%), which is why every statistic in this report is a median with a bootstrap confidence interval, not a mean with a parametric one.

**Position and window as covariates.** Section 7 fits both simultaneously in one joint model, proven full rank -- not two separate reduced models.

**No execution was removed from any statistic in this report.** All 720 official executions across the 3 windows, 0 recorded errors, feed every table above.

## 9. Mapping to the independent review items

Against the advisor's/reviewer's parecer técnico (which evaluated an earlier, shorter version of this report, not this v8 document) and the project's own pre-registration/metrics-coverage documents. Full citations: `thesis/results/v8/artifacts/item3_promise_evidence_matrix.md`.

| Item | Status |
|---|---|
| 4.2 (latency model / round-trip count) | **Closed** -- Section 7's k-model and joint regression |
| 4.3 (PQC/Hybrid asymmetry, CA signature) | **Closed** -- Section 2, PQC's chain confirmed ML-DSA-65 end-to-end live |
| 4.4 (transport/front-channel realism) | **Partially closed** -- real network conditions now in scope; no real browser/app front-channel tested |
| 4.6a (single unit of measure for JWT/keys) | **Closed** -- Section 3, raw vs. base64url both reported, compact serialization stated as the equation's own unit |
| 4.6c (Classic profile's conformance to OPIN's live security profile) | **Not done** |
| 4.6e (hybrid certificate model vs. composite signatures) | **Declared limitation** -- mechanism documented, alternative not tested |
| Rec. 1 (add a 4th, hybrid-KEM-classical-signature profile) | **Not done** |
| Rec. 2 (symmetrize PQC/Hybrid) | **Closed** -- same as 4.3 |
| Rec. 3 (decompose client/server/handshake/wait time) | **Closed** -- Section 6 |
| Rec. 4 (explain round-trip count) | **Closed** -- Section 6/7 |
| Rec. 5 (realistic bandwidth/MTU) | **Partially closed** -- real network condition, not a deliberate parametrized sweep |
| Rec. 6 (real browser/app front-channel) | **Not done** |
| Rec. 7 (reformulate "fixed cost per flow" conclusions) | **In progress** -- this report's Sections 4, 7, and 10 are a first pass at that reformulation |
| Rec. 8 (uniform unit of measure / RSA algorithm; justify parameters) | **Declared limitation** -- parameters justified in code comments; unit/RSA not uniformized |
| Advisor: metrics at least equal to Schardong et al. (2022) | **Closed** |
| Advisor: distribution statistics, not just the median | **Closed** -- Shapiro-Wilk, bootstrap CI, Mann-Whitney, sign test, regression throughout |

## 10. Limitations

- **JWE stays classical in every profile.** `id_token` encryption (RSA-OAEP + A256GCM) was never in this migration's scope; no post-quantum JOSE encryption standard exists to migrate to.
- **The AS<->RS internal channel stays classical under PQC and Hybrid**, by a pre-existing SNI carve-out (Section 1.1) -- listed in Section 1.2's own profile table too, so it is not mistaken for new, unmigrated PQC/Hybrid scope.
- **Hybrid's practical TLS-layer message authentication relies on RSA alone**: the live handshake never checks the real ML-DSA-65 signature Hybrid's certificates also carry (Section 2) -- its authentication strength against an attacker who can forge an RSA signature is the same as Classic's.
- **Hybrid's TLS server/client authentication reuses Classic's RSA key as its base**, adding ML-DSA-65 as an extension rather than replacing the key material.
- **A single gateway image is used for all three profiles and all three installations** (Section 1.1) -- `code_hash`/image digest were checked at every profile-block switch (Decision 108) but the binary itself is shared infrastructure, not a per-profile or per-window variable.
- **ICMP is blocked by the security groups**; RTT and loss come from TCP/pcap evidence (SYN/SYN-ACK, retransmissions), never from `ping`.
- **No real browser or app front-channel was tested** -- the client is this project's own HTTP client, not a real user agent subject to URL-length or redirect-chain limits.
- **The campaign spans a little over half a day of real wall-clock time** (window boundaries reconciled in Section 1.1), not a long-term deployment -- the heterogeneity found for PQC's fixed cost across windows (Section 7) spans this scale of time, not weeks or months.
- **4.6c** (the Classic profile's documented conformance to OPIN's own live security profile) remains open, by scope, not by oversight.
- **No fourth profile** (hybrid KEM with classical-only signatures) was added.
- **Server/client instances (`m7i-flex.large`) use a baseline-and-burst performance model, not the credit-based burstable model** -- CPU steal, not credit exhaustion, was the relevant risk and was monitored throughout (mean below 5% in every window). The control instance (`t4g.micro`, ARM Graviton T-series) is credit-based burstable, but runs no measured flow work.
- **The handshake residual beyond the 6-connection round-trip cost is not attributed** (Section 6) -- investigated, no specific cause isolated with confidence.
- **PQC's k and fixed-cost estimates show real, statistically detectable variation across the 3 windows** (Section 7) -- the cause is a hypothesis, not a confirmed finding; the combined estimate across all 3 windows is this report's best single figure, not a claim that the underlying quantity is provably stable.

## 11. Reproducibility and integrity

- **Git tags:** `v8-prereg` (acceptance criteria, before any official window), `v8-prereg-3` (the 5 confirmatory predictions, before windows 2/3 were analyzed), `v8-official-data` and `v8-official-data-2` (the official 720-execution dataset and its corrected/extended consolidate).
- **Code/image integrity:** every profile block checked `CODE_HASH` against a registered value and the live gateway image digest against `sha256:0839867545f3170f6198e7e2f6f3a9a7f6803c2b4feba2bb54f181195b341901`, every block, all 3 windows -- 0 violations (Decision 108's `check_artifact_health`).
- **sha256 manifests:** every file in `janela1/`, `janela2/`, `janela3/` has a per-file sha256 manifest under `_campaign-control/sha256_manifest.txt`.
- **Data inventory: 744 = 720 + 24, confirmed by location, not assumed.** 720 official execution files + 360 discarded K=5 warm-up files (the K=5 warm-ups never capture pcap/cpu, by design -- Decision 103). Pcap/cpu artifact counts are 744 per side (client and server), not 720. **The extra 24 are NOT a per-cell warm-up** (an earlier draft of this report said so, incorrectly) -- confirmed now by their own file path: 48 client-pcap files live under `janela1/_campaign-control/validation_stage/`, the one-off 24-execution (8 scenarios x 3 profiles) **parallel validation stage** run before window 1 began (`run_validation_stage()`, `campaign_run.py`) -- never pooled into any cell's own 30-execution statistic, physically separate from the official per-cell data tree, pulled alongside window 1's own data because both live under the same `janela1/` pull.
- **Secret scanning:** every commit in this campaign's history passed the project's secret scanner (staged diff, full history, and a manual decompress-and-grep pass over every pcap) before being pushed.
- **This audit:** `thesis/scripts/audit_v8_from_raw.py` independently recomputed T_fluxo (24 cells), bytes-per-participant, RTT measured, OPINsize constancy, N_JWK, the participant decomposition, the k-model, and the 72-cell drift table directly from the raw run files, calls.jsonl, and pcaps, pooled across all 3 windows -- **0 divergences** against the published consolidate outputs (one noted finding, not a divergence: the PQC k bootstrap CI's upper tail is sensitive to the resampling stream at this sample size -- see Section 7).

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

# v7 Consolidated Report — Size and Latency of Three Cryptographic Profiles (Classic, PQC, Hybrid) in the OPIN Flow

**Status**: final v7 version. Fully replaces v5 (size and latency with only the signature migrated) and v6 (TLS key exchange measured in isolation), which now have the same historical status as versions v1–v4.

**Data origin**: all values in this report were recalculated from scratch from the raw files `runs/run01..10*.json` (378 files, including the 18 latency warm-up runs), without using the existing `median_metrics.json` files as a reference; the result of this independent audit is in Section 7. No run was redone for this report: it consolidates data collected on 12/09/2026.

**How to read the tables in this document.** Each table is preceded by a short sentence saying what it shows and how to interpret the columns — no prior knowledge of any technical term is needed to follow along. Conventions used throughout: "×" means "how many times larger" (e.g., 3.24× means "3.24 times the reference value"); percentages in parentheses are the same ratio expressed as growth (3.24× = +224%); "spread" is the variation between the smallest and largest observed value, calculated as (maximum − minimum) / minimum. Technical terms (AS, RS, mTLS, JWT, PKI, etc.) are defined in the Glossary at the end.

---

## 1. Summary of Results

- **Size is deterministic.** The 60 runs of each profile (6 latency scenarios × 10 runs) produced exactly the same bytes in every size metric: 0.00% spread across all 18 scenario/profile combinations. Injected network latency doesn't change any size metric.
- **The mTLS handshake cost grows from {{hs_classic}} bytes (Classic) to {{hs_pqc}} (PQC, {{hs_ratio_pqc_classic}}) and {{hs_hybrid}} (Hybrid, {{hs_ratio_hybrid_classic}}).** Hybrid pays {{hs_ratio_hybrid_pqc}} PQC's handshake.
- **The average JWT goes from {{jwtmean_classic}} bytes to {{jwtmean_pqc}} (PQC) and {{jwtmean_hybrid}} (Hybrid)**, i.e., {{jwt_ratio_pqc_classic}} and {{jwt_ratio_hybrid_classic}} Classic's size.
- **OPINsize**: this thesis extends the Schardong et al. (2022) equation with a fourth term, for the cost of Certificate Authority certificates that the flow downloads and that the original formulation doesn't cover. Under the extended formula, v7's OPINsize is {{opin1_classic}} bytes (Classic), {{opin1_pqc}} (PQC), and {{opin1_hybrid}} (Hybrid) (Section 3.2).
- **Latency (T_fluxo)**: the order Classic < PQC < Hybrid holds in all 6 emulated latency scenarios, by medians. Classic and PQC have fully separated distributions in every scenario; PQC and Hybrid have overlapping [min., max.] ranges in all 6 scenarios, although the medians and an exact rank test point to Hybrid being above PQC in all of them (Section 4.3).
- **The latency difference between Classic and PQC/Hybrid is nearly constant ({{lat_gap_cp_min}} to {{lat_gap_cp_max}} s for PQC), not proportional to network latency**, and should not be attributed to the algorithms alone: the test client's ML-DSA-65 signer design has its own process cost (Section 6).
- **Decomposition by participant**: AS and RS, previously collapsed into "Other" by an artifact of proxy routing, were separated with a one-off capture (one run per profile, outside the official statistical protocol) that reconciles exactly with the totals already committed; handshake bytes still lack a per-direction breakdown (Section 3.3).

---

## 2. Methodology

### 2.1. What Was Measured

A complete Open Insurance Brasil (OPIN) flow, run by a test client (`opin_flow.py`) against a prototype authorization server (AS), a resource server (RS), and an mTLS gateway: consent, authorization request (PAR), automated login, code-for-token exchange, and resource query. Each complete run has **{{n_req}} HTTP requests** across two sub-flows, **{{n_mtls}} mTLS connections** (three connection pools per sub-flow), **{{n_jwt}} JWTs** transferred, **{{n_jwk}} JWKS fetches**, and **{{n_pki}} CA certificate fetches** ({{n_root}} for the root and {{n_issuer}} for the issuer).

### 2.2. The Three Profiles

The experiment compares three cryptographic configurations of the same flow, varying two independent mechanisms: which algorithm signs the flow's artifacts (certificates, tokens) and which mechanism establishes the TLS connection's secret key. The table below summarizes both, per profile:

| Profile | Signatures | TLS Key Exchange |
|---|---|---|
| Classic | RSA (PS256 / RS256) | Classical ECDHE (curves P-521, P-384, P-256) |
| PQC | Pure ML-DSA-65 (NIST FIPS 204) | Pure MLKEM1024, no classical component |
| Hybrid | RSA and ML-DSA-65 combined (schemes described in `ARCHITECTURE.md`) | X25519MLKEM768 (X25519 + ML-KEM-768) |

Token content encryption (JWE with RSA-OAEP in the `id_token`) remains classical in all three profiles: there is currently no JOSE/COSE standard for post-quantum token encryption, which prevents migrating this layer (see `thesis/docs/Cruzamento_SAD_vs_Experimentos.md`).

### 2.3. Test Architecture

All three profiles were measured under the same TLS client architecture, eliminating confounding variables between them — full details in `TLS_KEM_Proxy_Architecture.md`.

### 2.4. Collection Protocol

- **6 latency scenarios** (0, 14, 30, 140, 225, and 320 ms) × **10 runs** × **3 profiles**, for size and then for latency, in that order (full size, review, approval; then latency).
- **Emulated latency** with `tc`/`netem` on the gateway container's `eth0` interface (delay applied to the gateway's outbound traffic).
- **Warm-up**: each latency scenario has one warm-up run (`run00_warmup.json`), always discarded. The cryptographic profile switch is only done via `switch_crypto_profile.py`, which waits for the environment to settle (5 complete runs discarded) before any measurement.
- **Monotonic clock** for T_fluxo (complete flow time), with no outlier removal of any kind; runs repeated due to known failures would count only the successful attempt's time. In v7, no run needed to be repeated.
- **File convention**: `runs/run*.json` are the primary source; `median_metrics.json` and the per-scenario `.md` reports are derived. This report and `report_data_v7.json` are derived from `runs/`.
- **Structure**: `thesis/results/v7/size/experiment{1,2,3} - {Classic,PQC,Hybrid}/<scenario>ms/` and `thesis/results/v7/latency/...`.

> **Technical note — what "size" measures.** `handshake_bytes` is the byte count at the gateway's raw connection layer (read + write, ClientHello through Finished), the median of the {{n_mtls}} connections in each run. Bytes per participant are counted at the application layer (HTTP headers + body), and don't include TLS/TCP/IP headers or the handshake. JWT size is the token's length (without HTTP headers).

---

## 3. Size Results

### 3.1. Size by Artifact

**What this table shows.** "Artifact" here is each piece of cryptographic data the flow produces or carries — a TLS handshake, a certificate, a token (JWT), a public key. For each one, the table gives the average size in bytes, side by side across the three profiles, to answer this section's central question: how much bigger does each piece get when migrating to PQC or Hybrid? The values are identical across the 6 latency scenarios tested (0.00% variation across the 60 runs of each profile) — network latency doesn't affect size, only time.

{{table:size_main}}

**How to read the ratio table below.** Each cell divides the value of a profile column (e.g., PQC) by the value of the row's reference profile (e.g., Classic), using the metric indicated in the column. A value of "3.24×" in the "Handshake" column means that profile's handshake is 3.24 times larger than the reference profile's. The "Server output" column uses the total bytes the client receives (see Section 3.3) as a proxy for the volume the servers send:

{{table:size_ratios}}

### 3.2. OPINsize (Extended Formula)

The original flow-size equation (equivalent to Eq. 3.1 of Schardong et al., 2022) sums three terms. This consolidation extends it with a fourth, for the Certificate Authority certificates the flow downloads that were already measured but never entered the sum. The full justification for the extension is in `ARCHITECTURE.md`, Section 7 (and `DECISIONS.md`, Decision 7). From here on, **OPINsize always refers to the extended formula** — the only result in this section:

```
OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes
```

with N_mTLS = {{n_mtls}}, N_JWT = {{n_jwt}}, N_JWK = {{n_jwk}}, and N_PKI = {{n_pki}}. `PKI_bytes` is the average size, in bytes, of the two CA certificates served (root and issuer), in the format they travel in (PEM). With N_PKI = 0 the equation reduces to the original, which preserves comparability with the literature.

**What the table below shows.** Each row is one of the four terms of the sum — how many times that artifact appears in the flow (column N) multiplied by its size, per profile. The bold row ("OPINsize") is the sum of all four, the equation's final result; the last row shows what fraction of that total comes just from the new term (PKI):

{{table:opin}}

**How to read the ratio table.** Same reading as Section 3.1: each value is "how many times larger" one profile's OPINsize is relative to another's, with the equivalent percentage change in parentheses.

{{table:opin_ratios}}

Reading the results:

- The PKI term is {{t_pki_classic}} bytes in Classic, {{t_pki_pqc}} in PQC, and {{t_pki_hybrid}} in Hybrid — {{share_classic}}, {{share_pqc}}, and {{share_hybrid}} of each profile's OPINsize, respectively.
- In Hybrid, the PKI term is **{{hyb_pki_over_jwk}} the JWK public-key term** and equals {{hyb_pki_over_hs}} of the handshake term. In PQC, the PKI term is {{pqc_pki_over_jwk}} the JWK term. In Classic, {{cls_pki_over_jwk}}.
- PQC has the smallest relative share of the PKI term because, in this prototype, its CA certificates have an ML-DSA-65 subject key but remain signed by an RSA CA (deliberate design of Stage 3.1); in Hybrid, the CA certificates carry both signatures.
- By OPINsize, Hybrid is {{opin1_ratio_hybrid_pqc}} PQC and {{opin1_ratio_hybrid_classic}} Classic; PQC is {{opin1_ratio_pqc_classic}} Classic.

**How the PKI term was validated without new measurement.** The CA certificate sizes come from the PEM files the gateway serves (`mock-service-os/certs/`), and were checked against the HTTP response volume already measured in the raw data ("PKI/CRL" participant). The measured volume minus the body of the {{n_pki}} certificates gives an HTTP framing of exactly {{frame_each}} bytes per response, **identical across all three profiles** — which is only possible if the body served is exactly the file used in the calculation. The table below shows this arithmetic, column by column, per profile:

{{table:pki_detail}}

**Sensitivity — does the result change if PKI_bytes is measured differently?** The table above used the PEM file size; the table below recalculates the same OPINsize using instead the actually measured HTTP response volume (body + {{frame_each}} bytes of framing per certificate) — an alternative, equally valid, way of defining the same term. The difference between the two OPINsize columns shows how much this methodological choice weighs on the final result: less than 1 percentage point.

{{table:sens}}

### 3.3. Decomposition by Participant and Direction

The raw data aggregates each run's bytes into three participants: the **Client**, one collapsed participant ("Other", AS and RS summed — the test client classifies each call by the URL address, and in v7 all calls go through the local proxy `127.0.0.1:8443`, so the real host never reaches that classification) and the **Directory/PKI-CRL**. This collision was resolved without re-running any of the 180 statistical measurements: a one-off capture, one run per profile, outside the official protocol (same category as the `artifacts/` folder), recorded the real logical destination of each of the 28 calls (the `Host` header that `opin_flow.py` already sets for each call, never rewritten by the proxy, which only shuffles the physical address) together with its bytes. This is valid for the 180 data points already collected because size has already been proven to have 0.00% spread across 60 runs per profile — the AS/RS split from one run holds for all of them. The full methodology, including a real environment issue found along the way (a wrong version of `requests` installed, producing bytes different from the official ones until fixed), is in `DECISIONS.md`, Decision 10. Each capture reconciles exactly with the "Other" and "PKI/CRL" totals already committed (AS + RS = Other, byte for byte, across all three profiles) — the breakdown below is not a new measurement, it's the same measurement, correctly separated.

**How to read the table below.** Each row combines a flow participant (Client, AS, RS, or Directory/PKI-CRL) with a direction (bytes it *sends* or bytes it *receives*), across a complete flow. This is the same byte total already used in Section 3.1, just split by who sends and who receives each byte, instead of summed into a single total:

{{table:participants}}

Since every byte sent by one participant is received by the other, the rows balance against each other: the total sent by the Client equals the total received by the servers and the Directory, and vice versa (verified in each of the 180 size runs, and the AS+RS=Other reconciliation verified across all three profiles by the one-off capture).

**Why this matters: who pays the egress bill.** Cloud providers generally charge for data that *leaves* a server (egress), not for what comes in. The table below takes only the "sent" rows for AS, RS, and Directory/PKI-CRL above and shows what fraction of the total each represents — that is, out of every 100 bytes the servers emit in a flow, how many come from each:

{{table:egress_share}}

**To project a real-world cost**, multiply each participant's "sent" value (Section 3.3, participants table) by the expected number of flows per month; the price per byte depends on the cloud provider chosen and is outside the scope of this work. The RS dominates server output in all three profiles — most of the application traffic is the insurance query responses, not the AS's authorization artifacts.

**What is still not available, even after this capture.** The table below lists, for each type of data breakdown one might want, whether it is already covered or not, and why:

| Requested breakdown | Status |
|---|---|
| Client × AS × RS × Directory/PKI-CRL, sent × received | **Available** (table above), via Decision 10's one-off capture. |
| **Handshake bytes by direction** | **Not available.** The gateway counts the bytes read and written for each connection separately, but only logs the sum. The handshake growth in the PQC and Hybrid profiles is split between the two directions (client certificate and KEM public key go from client to server; server certificate and KEM ciphertext go from server to client), but the split was not measured — not even by the one-off capture, which doesn't instrument the gateway. So the portion of the handshake that is server egress **is not included** in the tables above and cannot be estimated from the existing data; the tables underestimate real server output, by an unknown proportion. Resolving this would require adding `bytesRead`/`bytesWritten` to the gateway's log line (`mock_mtls/main.go`) and a new one-off capture, of the same category used here. |
| Bytes by specific endpoint (not just by participant) | Latency by endpoint is in the official raw data; bytes by endpoint, only in the one-off capture (`thesis/results/v7/participant_decomposition_capture_*.json`), not used for that granularity in this report. |

The handshake-by-direction gap remains a limitation, with no new collection; the AS/RS gap was closed in this round.

---

## 4. Latency Results

T_fluxo is the time of the complete flow ({{n_req}} requests), in seconds, measured with a monotonic clock. Each cell is the median of 10 runs (the warm-up run is discarded).

### 4.1. Medians by Scenario

**What this table shows.** The typical time (median of 10 runs) of the complete flow, in seconds, for each combination of cryptographic profile and simulated network latency. It's the most direct table for answering "how much extra time does using PQC or Hybrid cost, on a network with X ms of delay":

{{table:lat_matrix}}

### 4.2. Full Distribution (18 Profile × Scenario Combinations)

**What this table shows.** Detail on the previous table: for each profile/scenario combination, not just the median, but the smallest and largest time observed across the 10 runs (Min./Max.), the arithmetic mean, the standard deviation (how much the values typically deviate from the mean), and the spread (the variation between the smallest and largest, as a percentage of the smallest) — the basis for assessing whether each row's 10 runs were consistent with each other or scattered:

{{table:lat_full}}

The largest spread (difference between maximum and minimum, relative to the minimum) across the whole experiment is {{lat_max_spread}} ({{lat_max_spread_where}}), well below the 60–70% threshold set as the stopping point for investigation; the spread tends to drop as emulated latency increases (in Classic, from 25.77% at 0 ms to 0.21% at 320 ms), which is expected, because time becomes dominated by the injected delay rather than by variations in the operating system and Docker.

### 4.3. Differences Between Profiles and the T_Classic < T_PQC < T_Hybrid Hypothesis

The natural hypothesis is that flow time grows in the order Classic < PQC < Hybrid, tracking the amount of cryptography involved. The two tables below test this hypothesis against the measured data.

**First table — the differences, in absolute and relative numbers.** For each latency scenario, how much extra time (in seconds) PQC and Hybrid take relative to Classic and to each other, and the same difference expressed as a ratio ("×"):

{{table:lat_deltas}}

**Second table — does the hypothesis hold up to a statistical test?** "Holds"/"doesn't hold" says whether the order of the medians follows the hypothesis in that scenario. "Separate"/"overlap" says whether the ranges of observed values (from minimum to maximum, across the 10 runs) of two profiles ever cross, or whether one profile is always faster than the other in every run. The "exact p" columns come from a statistical test (Mann-Whitney rank-sum test) that estimates the chance the observed difference is just chance — the smaller the value, the stronger the evidence that the difference is real, not coincidence (a p below 0.05 is usually already considered strong; here the values are much smaller):

{{table:hypothesis}}

- The order **Classic < PQC < Hybrid holds in all {{order_holds_count}} latency scenarios**, by medians. (In v5, an inversion at 14 ms had been observed and kept as a finding; it does not recur in v7.)
- **Classic × PQC**: fully separated distributions in every scenario (no PQC run is faster than Classic's slowest); exact rank-test p ≤ {{p_cp_max}} in all of them.
- **PQC × Hybrid**: the [min., max.] ranges overlap in all {{hp_overlap_count}} scenarios. The one-sided exact rank test (Hybrid > PQC) gives p ≤ {{p_hp_max}} in all of them, and the median difference is {{lat_gap_hp_min}} to {{lat_gap_hp_max}} s ({{lat_hp_rel_min}} to {{lat_hp_rel_max}} over PQC). This test is descriptive only: the 10 runs of each profile were collected sequentially, in blocks, and are not independent samples; a slow environment drift between blocks could contribute to the difference.
- **Growth with latency**: from 0 to 320 ms, Classic's T_fluxo grows {{classic_growth}}, PQC's {{pqc_growth}}, and Hybrid's {{hybrid_growth}}. As a result, the relative cost of the post-quantum profiles shrinks as latency rises: PQC goes from {{lat_cp_ratio_0}} to {{lat_cp_ratio_320}} of Classic, and Hybrid from {{lat_hc_ratio_0}} to {{lat_hc_ratio_320}}.
- The absolute difference from Classic is roughly constant ({{lat_gap_cp_min}} to {{lat_gap_cp_max}} s for PQC; {{lat_gap_hc_min}} to {{lat_gap_hc_max}} s for Hybrid) and does not grow with network latency. The data therefore doesn't show an additional latency-proportional cost attributable to the larger handshake; it shows a fixed per-flow cost, whose main source is discussed in Section 6.

---

## 5. Relevant Fixes Along the Way

No result in this report came out right the first time — the table below summarizes, in order, each real issue found, what it caused, how it was fixed, and where the full investigation is recorded (the "Record" column points to the corresponding `DECISIONS.md` entry):

| Problem | Effect | Resolution | Record |
|---|---|---|---|
| The test client resolved the local proxy via `"localhost"`; the IPv6 attempt failed and fell back to IPv4 | ~2.1 s extra per new connection (6 per flow, ≈12.6 s), artificially inflating the latency of the profiles going through the proxy and contaminating the comparison | Switched to `127.0.0.1`; the entire v6 latency batch redone | v6 (Level 1), Decision 3 |
| Comparing v5's handshake (Python client) with v6's (Go client) mixed the KEM effect with the effect of switching implementations | PQC's handshake looked *smaller* than Classic's | v7 unifies all three profiles under the same Go client | v6 Decision 2; v7 Decision 1 |
| The per-profile key-exchange policy broke the internal `auth`→RS call (the Node.js client doesn't negotiate the KEM groups) | 100% failure of PQC/Hybrid runs | Deliberate SNI-based exception (`matls-api.local`) keeps that one internal connection classical; reconfirmed in v7 with a 1:1 match (35 classical handshakes, 35 exception applications) | v6 Decision 1; v7 Decision 6 |
| Cumulative Docker Desktop degradation and failure to "settle" after a profile switch | ~2 s residual in Hybrid runs; first post-switch runs slow | Profile switching only via `switch_crypto_profile.py`, with warm-up discarded | v6 Decisions 4 and 5 |
| Explicit `Host` headers, needed for routing through the proxy, are included in Classic's bytes | +376 bytes in Classic's application total relative to v5 (main cause confirmed: 520 bytes of headers; ~144-byte residual not fully closed, ≈0.2%) | Recorded, no impact on conclusions | v7 Decision 4 |
| `opin_flow.py` was presenting a client certificate on the local Python→proxy leg; this machine's OpenSSL stopped being able to load the ML-DSA-65 key | PQC reproducibility broken after an external environment change (already-collected data unaffected) | The certificate is no longer presented on that leg (the local listener never required it) for PQC and Hybrid | v7 Decision 5 |
| SAD step 8's classification (access token) attributed a "hybrid signature" to an opaque token | Inaccurate documentation (doesn't affect data) | Fixed: the real signature is on the `client_assertion`, captured and verified in all three profiles | `Cruzamento_SAD_vs_Experimentos.md`; `artifacts/*/README.md` Section 6 |
| Incorrect normative reference ("RFC 9880") in a PQC artifact | Documentation | The pure `MLKEM1024` group is defined in the Internet-Draft `draft-ietf-tls-mlkem`; fixed | v7 Decision 9; `artifacts/pqc/README.md` |
| "Other" grouping (AS + RS) due to the local proxy | Loss of resolution in the per-participant breakdown | **Fixed** with a deterministic one-off capture (1 run per profile, outside the statistical protocol); reconciled exactly with the totals already committed | v7 Decision 8 (finding) and Decision 10 (fix) |

The investigation of a v6 residual (a difference of +4 recorded connections between v5 and v6) was deliberately closed without an identified cause: v6 ceases to be an official source with this consolidation.

---

## 6. Limitations

1. **Small sample.** Each cell has 10 runs. The spread reaches {{lat_max_spread}} at low latencies; medians are reported with no outlier removal. Small differences (such as PQC × Hybrid, Section 4.3) should be read with this caution in mind.
2. **PQC and Hybrid latency includes a test-client cost, not just the algorithm's.** The client signs the ML-DSA-65 JWTs by calling an ephemeral Docker container per signature (`_run_pqc_signer()`), while Classic signs in-process (`pyjwt`). In v5, a direct breakdown of a PQC flow at 14 ms measured 8 signer invocations adding up to 6.2 to 11.3 s, while the rest of the flow stayed stable at 4.6 to 5.1 s (v5, latency, Decision 8). The roughly constant difference of {{lat_gap_cp_min}} to {{lat_gap_cp_max}} s between PQC and Classic is consistent with this fixed cost, but **it was not decomposed in v7**; so the T_fluxo values for the PQC and Hybrid profiles should not be read as the pure cost of the post-quantum algorithms, but rather as the cost of the flow with the signing architecture actually used.
3. **Lab environment.** A single computer, Docker Desktop on Windows 11, test servers (AS/RS prototype), latency emulated with `netem` on the gateway's outbound traffic, with no packet loss or delay variation (jitter). It does not represent a real WAN.
4. **Not all of the system's mTLS traffic is post-quantum.** The internal `auth`→RS connection keeps a classical key exchange by design (SNI exception, Section 5); it doesn't enter N_mTLS or any metric.
5. **The token encryption layer (JWE/RSA-OAEP) remains classical** in all three profiles, due to the absence of a post-quantum JOSE/COSE standard. The consent step is, therefore, only partially migrated.
6. **Different security levels between PQC and Hybrid.** PQC uses ML-KEM-1024 (NIST category 5) and Hybrid uses ML-KEM-768 (category 3), because Go only offers ML-KEM-1024 without a classical component; the two profiles are not equivalent on this point.
7. **The PKI term depends on the flow as implemented.** The test client downloads the CA certificates at the start of each sub-flow, with no cache (N_PKI = {{n_pki}}); a real client with caching would pay less. The formula keeps N_PKI explicit precisely to allow other values. The same applies to N_JWK = {{n_jwk}}.
8. **Application sizes do not include TLS/TCP/IP overhead**, and the handshake has no per-direction breakdown (Section 3.3); OPINsize is a model of the cryptographic artifacts' cost, not equal to total network traffic.
9. **Pre-release or experimental-version tooling**: the TLS client and the artifact verifiers use Go 1.27 (release candidate, `golang:1.27-rc-alpine`) and Node 24's WebCrypto ML-DSA-65 support is marked experimental.
10. **SAD coverage.** SSA, DCR, the hash-based audit trail (SHA-256 → SHA-384), and revocation (CRL/OCSP) were not implemented; see `Cruzamento_SAD_vs_Experimentos.md`.
11. **Cryptographic artifacts** (`artifacts/`) are single-sample captures per profile, with reproducible cryptographic verification, not statistical ones.
12. **Bibliographic reference.** Eq. 3.1 of Schardong et al. (2022) is cited as the reference for the original formula; the full bibliographic entry is to be inserted by the author in the thesis.

---

## 7. Reliability and Independent Audit

Before writing this report, all metrics were recalculated from scratch from the raw files, without consulting the existing aggregates (`thesis/scripts/audit_v7_from_raw.py`; full output in `thesis/results/v7/audit_recompute_from_raw.txt`). The table below lists each check performed and what it found — "0 discrepancies" means the number recalculated from scratch matched exactly with the number already published:

| Check | Result |
|---|---|
| Size: median, minimum, maximum, spread, and individual values of 4 scalar metrics and 6 participant readings, across the 18 scenario/profile combinations, against `median_metrics.json` and `MEDIAN_REPORT.md` | 0 discrepancies |
| Latency: median, minimum, maximum, mean, standard deviation, spread, absolute deviations, and individual values, across the 18 scenario/profile combinations, against `median_metrics.json` and `report.md` | 0 discrepancies (a single alert, a rounding issue in the sixth decimal place shown in the Hybrid/30 ms report, verified as a formatting artifact: the median of two 6-decimal values falls on the seventh decimal place) |
| Internal consistency of each of the 180 size runs | {{n_req}} requests; {{n_jwt}} JWTs; {{n_mtls}} handshakes; bytes sent by the Client = bytes received by the others; total = sent + received by the Client; client certificate with the profile's expected size |
| Internal consistency of each of the 180 latency runs | 28 calls; no repetitions; zero wasted time; raw time = measured time; monotonic timestamps |
| Consistency across latency scenarios (size) | All metrics identical across the 6 scenarios, per profile |
| v5/v6 residual | None: the 378 raw files were generated between 12/09/2026 11:38 and 18:19 (UTC), with no duplicate timestamps; the only mentions of old folders are the `MEDIAN_REPORT.md` reports' template line, which cites v5's convention |

The tables in this report were generated by `thesis/scripts/compute_v7_report_data.py` from the same raw files (output in `thesis/results/v7/report_data_v7.json`).

---

## 8. Where to Find the Data and Related Documents

- Raw data: `thesis/results/v7/size/` and `thesis/results/v7/latency/`
- Data derived from this report: `thesis/results/v7/report_data_v7.json`
- Audit: `thesis/scripts/audit_v7_from_raw.py`, `thesis/results/v7/audit_recompute_from_raw.txt`
- v7 architecture and justification for the extended formula: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- The key-exchange proxy: [`TLS_KEM_Proxy_Architecture.md`](TLS_KEM_Proxy_Architecture.md)
- Real cryptographic artifacts, with verifiable proof: [`artifacts/classic/`](artifacts/classic/README.md), [`artifacts/pqc/`](artifacts/pqc/README.md), [`artifacts/hybrid/`](artifacts/hybrid/README.md)
- Decisions and fixes: [`DECISIONS.md`](DECISIONS.md)
- SAD coverage: [`thesis/docs/Cruzamento_SAD_vs_Experimentos.md`](../../docs/Cruzamento_SAD_vs_Experimentos.md)

---

## Glossary

| Term | Meaning |
|---|---|
| **OPIN** | Open Insurance Brasil, the insurance data-sharing ecosystem. |
| **AS / RS** | Authorization server / resource server. |
| **mTLS** | TLS with mutual authentication (the client also presents a certificate). |
| **KEM** | Key encapsulation mechanism; ML-KEM is the post-quantum standard (FIPS 203). |
| **ML-DSA-65** | Post-quantum digital signature (FIPS 204). |
| **Hybrid** | Combination of a classical and a post-quantum algorithm, requiring both to be broken to compromise the result. |
| **JWT / JWS / JWE / JWKS** | Signed JSON token / its signed form / its encrypted form / published set of public keys. |
| **PKI / CRL** | Public key infrastructure / certificate revocation list; here, the CA certificates downloaded in the flow. |
| **T_fluxo** | Time of the complete flow, measured with a monotonic clock. |
| **Spread** | (maximum − minimum) / minimum, as a percentage. |
| **Egress** | Data leaving a participant (basis for cloud traffic billing). |

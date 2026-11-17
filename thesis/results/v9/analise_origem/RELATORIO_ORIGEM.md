# Degrau 1 — exploratory investigation into the origin of the latency differences

Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC. Investigation separate from the official report (`Consolidated_Metrics_Report_FINAL.md`, untouched), no AWS, based SOLELY on data already saved locally. Full pre-registration in `PLANO.md` (committed before any analysis ran). Scripts and raw analysis data in `scripts/` and `data/`.

## Summary of verdicts

| Hypothesis | Verdict |
|---|---|
| H1 (block order / temporal drift) | **REFUTED** (main claim); real unforeseen secondary finding (see below) |
| H2 (extra network round-trips / initcwnd) | **REFUTED** (decision criterion revised after audit — see below; CI actively excludes the theoretical value, not just includes zero) |
| H3 (CPU cost of the primitives) | **REFUTED** only for the Go reimplementation tested; **INCONCLUSIVE** for the real stack (Python+Go+Node.js) — the real client cost was not measured (see below) |
| H4 (heterogeneity between installations) | **SUPPORTED** (existence); **INCONCLUSIVE as to the exact cause** |

**Critical note on the measurement itself (see the "Critical verification" section below):** "T_fluxo", used in ALL the sections above and in the official report, includes the full SSH call from the control host to the client (confirmed in the code), not just the 44 client-server HTTP calls. A regression (item 5b) estimates that the excess has at least two real components, statistically distinct from zero: one scaling with the control-client RTT (~13 network round-trips, consistent with SSH overhead) and another with the actual client-server RTT (~19 network round-trips) — plus a fixed cost (~1,8s) independent of both. The metric, as defined in the pipeline, does not separate these components.

## H1 — block order / temporal drift: REFUTED

**Prediction:** block position (1st-4th) correlates with median T_fluxo, in the same direction across most of the 8 routes.

**Actual result** (`scripts/etapa1_h1_order.py`, `data/etapa1_h1_order.json`): combined Spearman correlation (32 points, position × median) = **-0,009** (essentially zero); permutation test (8 routes, positions shuffled within each route, 10.000 permutations, seed `20270101`): **p = 0,7682**. Per route, the 8 Spearman coefficients vary in both directions (from -0,8 to +0,6), none individually significant (n=4 per route). **The main prediction does not hold: block position in the route order does not explain T_fluxo.**

**Real secondary finding, not predicted by the hypothesis as formulated:** the trend **within** each block (the 10 executions of a profile/route, in actual temporal order confirmed by the `run` field) is significant (Kendall's tau, p<0,05) in **8 of the 32 cells** — more than the ~5% expected by pure chance (~1,6/32). Of the 8 significant cells, **7 have a negative tau** (decreasing trend — later executions within the block get faster, a "settling" pattern): `classico/L219` (τ=-0,556), `classico/L0-us-east-1` (τ=-0,600), `classico/L30` (τ=-0,556), `pqc/L14` (τ=-0,733), `pqc/L0-ap-northeast-1` (τ=-0,644), `hibrido-v8/L0-us-east-1` (τ=-0,733), `hibrido-and/L0-us-east-1` (τ=-0,511); 1 positive: `pqc/L325` (τ=+0,600). This is a related but **distinct** phenomenon from what H1 proposed (which was about block position between profiles, not the internal order of the 10 executions within a single block) — recorded honestly here, without forcing it to support the original hypothesis.

## H2 — extra network round-trips / initcwnd: REFUTED (decision criterion revised)

**Prediction:** the slope of Diff(ms) vs. RTT approximately equal to the number of extra round-trips that the extra byte volume would require, given the actual `cwnd`/MSS.

**Real parameters** (criterion 2, never assumed): initial `cwnd` = **10** segments, MSS = **1.448 bytes** (first window = 14.480 bytes, confirmed exactly in the actual data). Real total bytes per execution: Classic = 121.641B, PQC = 280.900B, Hybrid = 337.149B.

**Revised decision criterion (post-audit correction, stricter than the one in the original `PLANO.md`):** the original `PLANO.md` refuted H2 if the CI included zero OR was incompatible with the theoretical K — a criterion that was too permissive, because "CI includes zero" by itself does not distinguish "there is no effect" from "there is an effect, but the data lack the statistical power to confirm it". Criterion applied now: **REFUTED only if the CI actively excludes the predicted theoretical K**; if the CI includes both zero and the theoretical K at the same time (without statistical power to distinguish the two scenarios), the correct verdict is **INCONCLUSIVE**, not REFUTED.

**Grouping and number of points (explicit transparency):** the fit is done by **pooling the 8 routes**, not by installation separately — the 8 routes come from only 3 physical installations, with few distinct RTTs each: sa-east-1 contributes **4** points (L0-sa-east-1 RTT=0,129ms; L123=122,642ms; L219=220,151ms; L325=323,406ms); us-east-1 contributes **2** (L0-us-east-1=0,287ms; L14=14,759ms); ap-northeast-1 contributes **2** (L0-ap-northeast-1=0,105ms; L30=33,423ms). Two of the 3 installations have only 2 distinct RTTs — insufficient for their own regression with degrees of freedom >0 — which is why the pre-registered fit uses the 8 pooled points (n=8), already aware that this mixes RTT with the installation effect that H4 shows to be real.

**Pooled result (n=8, `scripts/etapa1_decomp_h2_h4.py`):**
- PQC−Classic: slope = **0,868** ms/ms of RTT, 95% bootstrap CI (10.000 resamples, seed `20270102`) = **[-0,322; 2,138]**. Theoretical K = **3,585**. **The CI EXCLUDES the theoretical value** (upper bound 2,14 < 3,58) — REFUTED for this pair.
- Hybrid−PQC: slope = **0,358** ms/ms, CI = **[-0,786; 0,664]**. Theoretical K = **2,288**. **The CI EXCLUDES the theoretical value** (upper bound 0,66 < 2,29) — REFUTED for this pair.

In neither pair does the CI include the theoretical K together with zero — the condition for INCONCLUSIVE does not apply: the data actively exclude the magnitude predicted by the slow-start model, not merely fail to confirm it. **Verdict maintained: REFUTED, now under the stricter criterion.**

**Supplementary transparency check** (`scripts/etapa1_verificacoes_adicionais.py`, same seed `20270102`; n=4, fragile, does NOT replace the pre-registered pooled result above): redoing the fit with only the 4 sa-east-1 points (the only installation with more than 2 distinct RTTs, avoiding mixing RTT with the installation effect): PQC−Classic gives a slope of **1,980**, CI = **[1,502; 2,713]** — here the CI **excludes zero** (there is a real, positive relationship with RTT within this isolated installation) but also excludes the theoretical K of 3,585 (right direction, smaller magnitude than predicted). Hybrid−PQC within sa-east-1: slope **0,396**, CI = **[-0,570; 1,010]** — includes zero, excludes the theoretical K of 2,288. This check reinforces the same conclusion by another route: even isolating the installation effect, neither pair reaches the magnitude of extra round-trips that the slow-start model predicts.

## H3 — CPU cost of the primitives: REFUTED for the Go reimplementation tested; INCONCLUSIVE for the real stack

**Prediction:** on the `L0-*` routes (RTT~0), the T_fluxo difference should be of the same order of magnitude (ratio between 0,5x and 2x, declared a priori) as the CPU cost difference predicted by the local microbenchmark.

**Important post-audit correction — what language/runtime the real client is made of, confirmed in the code (not assumed):** the microbenchmark measured EVERYTHING in Go. This is only directly comparable if the real client also executed these operations in Go — which is NOT the case for all of them. Reading the client's actual code (`thesis/scripts/opin_flow.py` and the processes it orchestrates):
- **KEM (ML-KEM-1024 / `SecP384r1MLKEM1024` combiner / classical P-384):** the real TLS handshake is performed by a SEPARATE Go process (`thesis/scripts/tls_kem_proxy/main.go`, `tls_kem_proxy` module, Go 1.27rc2, `golang:1.27-rc-alpine` image) — a local proxy that performs a REAL `crypto/tls` handshake (not a raw API call), with `CurvePreferences` set to `tls.MLKEM1024`/`tls.SecP384r1MLKEM1024`/`tls.CurveP384` depending on the profile (confirmed at lines ~159-197 of `main.go`). The Python client (`opin_flow.py`) only connects to this proxy via `127.0.0.1:TLS_KEM_PROXY_PORT` — it never implements KEM itself.
- **ML-DSA-65 (signing AND verification, routed through 3 profiles by design — see `start_pqc_signer_service()` in `opin_flow.py`):** performed by a separate **Node.js** process (`thesis/scripts/pqc-signer/server.mjs`/`signer_core.mjs`, `jose@6.0.0` package), which calls the runtime's native WebCrypto DIRECTLY (`node:crypto`'s `webcrypto.subtle.sign`/`.verify({name: 'ML-DSA-65'})`, confirmed at lines 85/151-152/282/289 of `signer_core.mjs`) — it is not Go, not Python, and not any third-party PQC library in JavaScript: it is native ML-DSA support in `node:crypto` itself.
- **RSA-2048/PS256 (classical signature, Classic/Hybrid profile's JWT term):** this one does indeed run in **Python**, via `pyjwt.encode(claims, signing_key, algorithm="PS256")` (confirmed at lines 1574 and 1627 of `opin_flow.py`), which in turn delegates the RSA signing to the `cryptography` library (hazmat).

**Therefore: the premise "the real client is Python" is only partially correct.** `opin_flow.py` (Python, `requests`/`urllib3`) is indeed the process that orchestrates the HTTP calls and signs the real RSA/PS256 — but KEM and ML-DSA-65 (the two central PQC primitives of this investigation) **do not run in Python**: they run in separate processes, in **Go** (KEM, via a full TLS handshake, not an isolated API call) and **Node.js** (ML-DSA-65, via native WebCrypto), respectively.

**What this means for this investigation's microbenchmark:** it measured everything in Go (`thesis/results/v9/integration/bench/main.go` + `bench_chain/`, never modified). For KEM, this is the same language/runtime as the real process (`tls_kem_proxy`, also Go/`crypto/tls`), but it measures isolated keygen/encapsulate/decapsulate operations, not the full TLS handshake (which has additional record-layer overhead, certificate parsing, and network round-trips) — a reasonable approximation, not a direct measurement of the real path. For ML-DSA-65, the microbenchmark used the **Go** implementation of the primitive — **not** the Node.js/WebCrypto implementation that the real pipeline uses; no Node.js benchmark was run in this investigation. For RSA-2048, the microbenchmark used Go's `crypto/rsa` — the real pipeline signs RSA/PS256 in **Python** via `pyjwt`+`cryptography`; also not measured here.

**Local microbenchmark** (`scripts/` via Docker, `mockopin-v9-toolchain` image — the project's same Go 1.27.3 toolchain; hardware: the operator's notebook, Intel Core 7 150U, 10 cores — see `data/microbench_hardware.txt`; full output in `data/microbench_primitives_raw.txt` and `data/microbench_chain_raw.txt`):

| Operation | ns/op |
|---|---:|
| RSA-2048 sign (PSS-SHA256) | 902.882 |
| RSA-2048 verify | 30.604 |
| ML-DSA-65 sign | 535.535 |
| ML-DSA-65 verify | 144.189 |
| ECDH P-384 keygen | 108.071 |
| ECDH P-384 compute (KEX) | 494.856 |
| ML-KEM-1024 keygen | 74.711 |
| ML-KEM-1024 encapsulate | 49.449 |
| ML-KEM-1024 decapsulate | 72.132 |
| Chain validation, Classic (RSA) | 30.621 |
| Chain validation, PQC (ML-DSA-65) | 151.844 |
| Chain validation, Control (RSA) | 27.337 |
| Chain validation, Hybrid (RSA, primary only — see limitation below) | 23.191 |

**Total predicted cost per execution** (KEX×6 connections + signature×26 non-JWE tokens + chain validation×6, actual counts already confirmed in the official report): Classic = 27,28ms; PQC = 16,01ms; Control = 42,38ms; Hybrid = 42,33ms.

**Comparison with the actual observed difference (L0 routes, actual median):**

| Pair | Predicted (ms) | L0-sa-east-1 (observed, ms) | L0-us-east-1 (observed, ms) | L0-ap-northeast-1 (observed, ms) |
|---|---:|---:|---:|---:|
| PQC vs. Classic | -11,26 | -69,0 (ratio 0,16x) | +223,4 (ratio -0,05x) | +462,4 (ratio -0,02x) |
| Hybrid vs. PQC | +26,32 | +275,7 (ratio 0,10x) | +167,7 (ratio 0,16x) | +367,7 (ratio 0,07x) |

**None of the 6 comparisons falls within the [0,5x; 2x] range declared a priori** — in 2 of the 6 cases (both in the PQC vs. Classic pair: L0-us-east-1 and L0-ap-northeast-1) the prediction even has the wrong SIGN relative to the observed value.

**Verdict, with the language/runtime correction above:** for the **Go reimplementation** tested by this microbenchmark, the hypothesis is **REFUTED** — neither the magnitude nor (in 2 of the 6 cases) the direction is explained. But this cannot be extended to the claim "the real stack's CPU cost does not explain the difference", because the real stack uses Node.js (ML-DSA-65) and Python (RSA/PS256) for the parts that matter most here, and neither was measured. **For the complete real stack, the correct verdict is INCONCLUSIVE** — not because there is evidence that the real cost would explain the difference, but because that possibility was never tested directly.

**Explicit scope limitation:** the additional verification of Hybrid's ML-DSA-65 `AltSignatureValue` (custom callback, outside the standard `x509.Verify`) was not reproduced in the chain microbenchmark — only the primary RSA chain was measured for Hybrid. This slightly underestimates Hybrid's predicted cost, but not enough to change the conclusion (the difference between predicted and observed is one to two orders of magnitude).

## H4 — heterogeneity between the 3 installations: SUPPORTED (existence); INCONCLUSIVE (exact cause)

**Prediction:** the Classic profile's T_fluxo on the 3 `L0-*` routes differs significantly from one another, even with RTT~0 on all 3.

**Actual result** (exact two-sided Mann-Whitney, n=10 each, Holm correction over the family of 3 tests): the 3 comparisons hit the **smallest p-value mathematically possible** (raw p = 1,0825×10⁻⁵, Holm p = 3,2×10⁻⁵) — `sa-east-1` (median 2.357,9ms) < `us-east-1` (3.817,0ms) < `ap-northeast-1` (5.786,2ms). **Supported, unambiguously: the 3 installations differ greatly from one another, even though it is the same profile under effectively equal RTT.**

**Real decomposition to locate the origin** (sum of the 44 actual `latency_ms` per execution vs. residual = T_fluxo − that sum):

| Installation | Sum of calls (median, ms) | T_fluxo (median, ms) | Residual (median, ms) | Residual, % of T_fluxo |
|---|---:|---:|---:|---:|
| sa-east-1 | 475,3 | 2.357,9 | 1.882,0 | 79,8% |
| us-east-1 | 486,2 | 3.817,0 | 3.352,8 | 87,8% |
| ap-northeast-1 | 399,8 | 5.786,2 | 5.395,4 | 93,2% |

**The sum of the individual HTTP calls is practically constant across the 3 installations (400-486ms) — almost all of the difference between installations (from 1.882ms to 5.395ms) resides in the RESIDUAL**, not in the individually measured application calls. This locates the difference outside what the application measures per call — but the Stage 0 finding (there is no per-phase CPU time field nor per-execution handshake duration field) prevents going beyond this with the data already available.

**Additional, real attempt that did NOT help explain it:** I measured the actual capture duration of the 32 dedicated captures (one pcap per profile/route, via `scapy`, offline, local) for Classic on the 3 L0 routes — `sa-east-1`: 293 packets, 2,313s capture duration; `us-east-1`: 291 packets, 2,153s; `ap-northeast-1`: 290 packets, 2,147s. **The dedicated-capture durations are practically EQUAL across the 3 installations** — they do not track the ~3,4-second difference observed in the 320 actual timed executions. This means the dedicated capture (a single sample, not timed the same way as the 320 official executions) **does not serve as additional evidence here** — it is cited for transparency, not hidden, but it does not resolve the question.

**Verdict, therefore:** the existence of heterogeneity between installations is **SUPPORTED** with the highest statistical confidence possible in this design (p at the test's mathematical limit). The **exact cause** (instance hardware, local network conditions at the time of collection, hypervisor scheduling, internal VPC latency, or another factor) remains **INCONCLUSIVE** — no cause attribution is made beyond what the data directly show (the residual, not the application calls, carries the difference).

## Additional verification — hardware/environment across the 3 installations

**Question:** is there any real, documented hardware/environment difference between the 3 installations (`sa-east-1`/`us-east-1`/`ap-northeast-1`, servers and clients) that helps explain H4's heterogeneity? No AWS, no touching raw data — only from what was already collected locally.

**Sources:** `thesis/results/v9/campaign_oficial_conta_nova_host_facts.md` (an already-existing read-only audit, done before any teardown decision, no new AWS calls in this verification) + the `cpu_client`/`cpu_server` field (`steal_pct`/`util_pct`) already present in each of the 320 executions of `piloto_calls.json` (data already collected by the campaign itself, no new capture — recomputed in `scripts/etapa1_verificacoes_adicionais.py`, data in `data/etapa1_verificacoes_adicionais.json`).

**What `host_facts.md` already documents, byte-for-byte identical across the 3 servers (and across the 8 clients) — WITHOUT EXCEPTION:** instance type (`m7i-flex.large`, the same SKU across the 3 regions), vCPU count (2), memory (7,6Gi), kernel version (`6.1.189-236.400.amzn2023`, x86_64), Docker version, interface/subnet pattern (same `/20`), `tc qdisc` (same `fq_codel`, same parameters), and the 6 audited `net.ipv4.tcp_*` sysctls (same `congestion_control=cubic`, same `tcp_rmem`/`tcp_wmem`, etc.). **No OS/network configuration divergence was found between the 3 installations** — the only documented difference is the expected one (AMI/IP per region, inherent to running in different AWS regions).

**What is NOT documented in that file (honest, not assumed):** exact CPU model, clock frequency, `/proc/cpuinfo` flags — `host_facts.md` only records the vCPU COUNT (2), never model/flags/frequency. A search across the entire repository confirms: **no file contains a capture of `/proc/cpuinfo`, `lscpu`, or `mpstat` from the campaign hosts** — this specific data point was never collected in any previous run, and cannot be reconstructed without reconnecting to AWS (explicitly out of scope for this verification). I do not invent this number.

**What the already-collected data show** (Classic profile, 3 L0 routes, RTT~0, n=10 each):

| Installation | `steal_pct` client (median) | `steal_pct` server (median) | `util_pct` client (median) | `util_pct` server (median) | T_fluxo (median, ms, from H4) |
|---|---:|---:|---:|---:|---:|
| sa-east-1 | 0,0% | 0,0% | 10,16% | 20,52% | 2.357,9 |
| us-east-1 | 0,0% (isolated max 0,072%) | 0,0% (isolated max 0,072%) | 8,45% | 11,55% | 3.817,0 |
| ap-northeast-1 | 0,0% (isolated max 0,04%) | 0,0% (isolated max 0,04%) | 4,73% | 8,71% | 5.786,2 |

**Two honest readings:**
1. **`steal_pct` is essentially 0 across all 3 installations, without exception** — this rules out "CPU contention from a noisy neighbor in the hypervisor" (a reasonable a priori candidate) as an explanation for the heterogeneity: there is no evidence of stolen CPU in any of the 3.
2. **`util_pct` FALLS as T_fluxo RISES between installations** — sa-east-1 (lowest T_fluxo) has the highest CPU utilization; ap-northeast-1 (highest T_fluxo) has the lowest. This relationship is the OPPOSITE of what would be expected if the slower installation were CPU-bound (doing the same CPU work, but more slowly, would have equal or higher utilization, not lower). It is, instead, consistent with the reading already made in H4: if the extra time is dominated by waiting (I/O, network, OS scheduling) rather than CPU work, the same number of CPU-seconds gets diluted over a longer wall-clock window, lowering the average percentage. **This does not prove the cause of the residual, but it is one more piece of evidence pointing toward "waiting", not "CPU", consistent with the decomposition already reported in H4 above.**

**Conclusion of this verification:** no documented hardware/OS/network divergence explains H4 — all audited variables are identical across the 3 installations. The one variable that does vary (`util_pct`) varies in the OPPOSITE direction to a "slower/more loaded CPU" explanation, and `steal_pct` is zero. **The exact cause of H4 remains INCONCLUSIVE** (no change to the verdict), but the space of candidate hypotheses is narrowed: neither CPU contention (steal), nor documented OS/kernel/network configuration, nor a simple CPU-bound scenario (per the `util_pct` reading) appear to explain the residual — this remains a real gap, not a guess, for a future "Degrau 2".

## Critical verification — what T_fluxo actually measures (the measurement artifact itself)

**Motivation (real observation from the user):** comparing Classic's median T_fluxo on L0 against the dedicated-capture duration of the SAME profile/route (H4 section above): `sa-east-1` 2,358s vs. 2,313-2,417s; `us-east-1` 3,817s vs. 3,538s; `ap-northeast-1` 5,786s vs. 3,493s. The excess appears to grow with physical distance from `sa-east-1` — raising the hypothesis that T_fluxo may include region-dependent ORCHESTRATION overhead (e.g., SSH from the control host to the client), not just the 44 client-server HTTP calls. The 5 questions below were verified directly against the code and the real data, never assumed.

### Item 1 — exactly what is inside the t0..t1 window: SUPPORTED (confirmed in the code, not a statistical inference)

Reading `thesis/results/v9/campaign/scripts/orchestrator.py` line by line (method `run_execution`, lines 1416-1522) and the two files it invokes remotely:

- **`orchestrator.py:1449`**: `t0 = datetime.now(timezone.utc)` — taken in the CONTROL process, **even before the `ssh` subprocess is launched**.
- **`orchestrator.py:1450`** → **`cli.py:133-153`** (`run_ssh`): launches a NEW `ssh` process on every call — **no `ControlMaster`/`ControlPersist`/multiplexing option anywhere** in the constructed `argv` (confirmed by reading `cli.py:147-152`). This means each of the 320 executions pays for a FRESH SSH connection (not reused): control↔client TCP handshake (1 RTT), SSH protocol version exchange, key exchange (KEX) + public-key authentication (more RTTs, same control↔client distance) — all of this BEFORE the remote command even starts running.
- **Remote command launched**: `cd ~/thesis/scripts && {env_prefix} python3 campaign_client_runner.py --label {label}` (`orchestrator.py:1430`) — on the CLIENT, this starts a **brand-new Python process** (cold start, no process reused), which imports `argparse`, `json`, `os`, `sys`, `latency_automation`, `opin_flow` (`campaign_client_runner.py:23-29`) — a real CPU/disk cost on the client, with no network involved, but inside the window.
- **`latency_automation.py:257`**: `of.load_client_signing_key(crypto_profile)` — called **before** `t_start` is marked (line 264) inside `run_once_timed()`. The code's own comment (lines 247-256) names a cost: "classic/hybrid's RSA-4096 key-object construction, ~252ms" — outside the lib's internal measurement, but INSIDE the orchestrator's SSH window. **Correction (see Item 6-7): the comment describes RSA-4096, but the actual key used by the official campaign is RSA-2048 since Decision 113 (2026-11-10, before the campaign ran) — the actual cost measured locally is ~27ms, not ~252ms.**
- **Central finding, never noticed before in this investigation**: `latency_automation.run_once_timed()` (lines 213-314) already computes, ON EVERY EXECUTION, its OWN T_fluxo, local to the client, with `time.monotonic()` (`t_start`/`t_end`, lines 264/267) wrapping ONLY `run_insurance_flow`+`run_person_flow` — plus a full `phase_accounting` (`http_calls_seconds`, `signing_seconds`, `verification_seconds`, `explicit_wait_seconds`, `setup_seconds`, and an explicit residual `residual_seconds`, documented in the code as "the TLS-KEM-proxy hop and the mTLS/KEM handshake it performs... Python interpreter overhead", by subtraction). **This rich data is returned by `campaign_client_runner.py` (via stdout JSON), but `orchestrator.py` (lines 1504-1522) DISCARDS `result["t_fluxo_seconds"]` and `result["phase_accounting"]` entirely** — it only keeps `result.get("calls", [])` (renamed `"insurance"`) and replaces the measurement with ITS OWN `t0`/`t1`, which wraps the entire SSH call. **Confirmed by direct inspection of `piloto_calls.json`: the `t_fluxo_seconds`/`phase_accounting` fields do not exist in any execution.**
- After the actual flow (44 HTTP calls + signing + verification + explicit wait, measured but discarded): `print(json.dumps(result))` on the client, captured via SSH stdout on the control host (more control↔client network time proportional to the payload) + SSH session teardown (more RTTs).
- **`orchestrator.py:1472`**: `t1 = datetime.now(timezone.utc)` — only after ALL of this (including the SSH connection teardown) finished.

**Conclusion of item 1:** SUPPORTED, with certainty (this is not statistical, it is a direct reading of the code): `start_utc`/`end_utc` (= the "T_fluxo" used throughout this entire document and in the official report) literally wraps the entire SSH call, not just the 44 HTTP calls — and the measurement library already has a better decomposition (`t_fluxo_seconds`/`phase_accounting`) that the orchestrator discards before persisting.

### Item 2 — control region and network path: SUPPORTED

Confirmed in `thesis/results/v9/campaign_oficial_conta_nova_host_facts.md`: the control host is in **`sa-east-1`** (`control | control | sa-east-1 | 172.31.25.65 | ...`). Since `cli.run_ssh()` always dials the target's PUBLIC IP (Decision 43/45, cited in `run_ssh`'s docstring), **for 7 of the 8 routes (all except `L0-sa-east-1`, whose client is co-located in `sa-east-1`), the SSH call for each of the 320 executions crosses the public network to a region different from the control host's** — exactly the path the user described.

### Item 3 — excess (T_fluxo − dedicated capture) ÷ RTT: INCONCLUSIVE (noisy indicator) — but see item 5 below, which resolves this more robustly

Recalculated for ALL available profiles/routes (not just Classic/L0 as in the original Stage 1), via `scripts/etapa1_verificacao_artefato_medicao.py` (scapy, offline, all dedicated captures in `criterio1_capturas/capturas_brutas/`, median when there is more than one attempt):

| Profile/route | Median T_fluxo (s) | Dedicated capture (median, s) | Excess (s) |
|---|---:|---:|---:|
| classico/L0-sa-east-1 | 2,358 | 2,417 (n=3) | -0,059 |
| classico/L0-us-east-1 | 3,817 | 3,538 (n=2) | +0,279 |
| classico/L0-ap-northeast-1 | 5,786 | 3,493 (n=2) | +2,293 |
| pqc/L0-sa-east-1 | 2,289 | 3,730 (n=2) | **-1,441** |
| hibrido-v8/L0-sa-east-1 | 2,472 | 4,062 (n=2) | **-1,590** |
| hibrido-and/L0-sa-east-1 | 2,565 | 4,007 (n=2) | **-1,443** |

**Honest finding, not hidden:** for Classic, the "excess grows with distance from `sa-east-1`" pattern appears weakly (near zero in `sa-east-1`, growing in the other 2 installations) — but for PQC/Hybrid/Control, the excess in `sa-east-1` is **STRONGLY NEGATIVE** (the dedicated capture took LONGER than the actual median of the 10 timed executions). This means the dedicated capture (1-3 untimed samples taken alongside the 320 official executions, already flagged as a limitation in the original Stage 1) is **too poor a comparator** — the signal is inconsistent between profiles, and it cannot reliably estimate how much of the window is specifically SSH overhead. **Verdict: INCONCLUSIVE via this route** — not because no overhead exists (item 1 already proves it does), but because this specific indicator lacks sufficient statistical power to quantify it. The question is answered much more robustly in item 5.

**Control↔client RTT used as a reference, by route (full transparency on what is real vs. approximated):**

| Route | Control↔client RTT (ms) | Source |
|---|---:|---|
| L0-sa-east-1 | 0,129 | REAL (control and client co-located in sa-east-1) |
| L123 | 122,642 | REAL (sa-east-1 server co-located with the control host) |
| L219 | 220,151 | REAL (same) |
| L325 | 323,406 | REAL (same) |
| L14 | 122,642 (derived) | DERIVED — L14's client is in the SAME region as L123 (ca-central-1); uses L123's actual RTT as a proxy |
| L0-us-east-1 | no measurement | **EXTERNAL APPROXIMATION, not measured in this campaign**: range typically publicly cited for sa-east-1↔us-east-1, ~105-120ms |
| L0-ap-northeast-1 | no measurement | **EXTERNAL APPROXIMATION**: range typically cited for sa-east-1↔ap-northeast-1, ~270-300ms |
| L30 | no measurement | **EXTERNAL APPROXIMATION**: range close to sa-east-1↔ap-northeast-1 + the actual measured RTT ap-northeast-1↔ap-northeast-2 (33,423ms) |

As explicitly stated in the table: for `L0-us-east-1`/`L0-ap-northeast-1`/`L30` **there is no actual or derivable measurement from this campaign** of control↔client RTT (the RTT measured by the campaign is always client↔server; it is only a real proxy for control↔client on the routes where the route's SERVER coincides with the control host's region, `sa-east-1`). No precise number was invented for the 3 unmeasured routes — only a range, clearly labeled as external knowledge.

### Item 4 — does the difference BETWEEN PROFILES reside in the calls or in the residual?

Recalculated with full precision (no rounding before subtracting), `scripts/etapa1_verificacao_artefato_medicao.py`:

| Route | Δ(sum of calls) PQC−Classic (ms) | Δ(residual) PQC−Classic (ms) | Δ(sum of calls) Hybrid−PQC (ms) | Δ(residual) Hybrid−PQC (ms) |
|---|---:|---:|---:|---:|
| L0-sa-east-1 | -27 | -42 | +113 | +163 |
| L0-us-east-1 | -13 | +236 | +72 | +95 |
| L0-ap-northeast-1 | +6 | +456 | +51 | +317 |
| L123 | -12 | +276 | +49 | +157 |
| L219 | -1 | +423 | +54 | +237 |
| L325 | -6 | +584 | +19 | +376 |
| L14 | +21 | +267 | +46 | +124 |
| L30 | -43 | +597 | +107 | +152 |

**Honest reading:** for **PQC−Classic**, Δ(sum of calls) always stays within ±43ms (noise) across ALL 8 routes — the real difference (up to +597ms) resides **almost entirely in the residual**. For **Hybrid−PQC**, Δ(sum of calls) is already non-trivial (19-113ms, which makes sense: Hybrid literally does more cryptographic work PER real call), but the residual still dominates (95-376ms).

**The residual is NOT approximately constant across routes** — quite the opposite: on just the 3 L0 routes (client-server RTT~0 on all 3), Δresidual(PQC−Classic) varies from -42ms to +456ms, more than 10x of variation **even with identical real RTT (~0) on all 3**. This is **inconsistent** with "fixed orchestration overhead, independent of everything" — the size of the residual (and of its difference between profiles) clearly depends on the **installation** (the same effect already identified and left inconclusive in H4), not just the profile.

### Item 5 — residual of the non-L0 routes vs. the same installation's L0, against the actual RTT: real descriptive finding, but CONFOUNDED (mixes `b` and `c`, isolates neither — see the correction below and the Item 5b regression)

For each of the 5 non-L0 routes, Classic profile (same convention as H4): `(route's residual − the residual of the SAME installation's L0)` divided by that route's **actual client-server RTT** (not control-client — this test uses only real data, with no approximation at all):

| Route | Installation | Δresidual vs. L0 (s) | Actual client-server RTT (ms) | Δresidual/RTT (ms of extra residual per ms of RTT) |
|---|---|---:|---:|---:|
| L123 | sa-east-1 | 3,828 | 122,642 | **31,2** |
| L219 | sa-east-1 | 6,955 | 220,151 | **31,6** |
| L325 | sa-east-1 | 10,571 | 323,406 | **32,7** |
| L14 | us-east-1 | 0,393 | 14,759 | **26,6** |
| L30 | ap-northeast-1 | 1,062 | 33,423 | **31,8** |

**Descriptive result:** the Δresidual/RTT ratio falls between 26,6 and 32,7 across the 5 routes — even though the routes have completely different actual RTTs (14,8ms to 323,4ms).

**Methodological correction (pointed out by the user, twofold, more precise than the previous version of this document):** the earlier claim that "the route and its own L0 share exactly the same control↔client distance" was **imprecise for all 5 pairs, not just some**:

1. **`L123`/`L219`/`L325` vs. `L0-sa-east-1`:** `L0-sa-east-1`'s client is co-located in `sa-east-1` (control↔client RTT ≈0,129ms, since the control host is also in `sa-east-1`) — but the clients for `L123`/`L219`/`L325` are in `ca-central-1`/`eu-north-1`/`ap-southeast-1` (actual control↔client RTT ≈122,6/220,2/323,4ms, via the same proxy as in item 5b — the route's server is `sa-east-1`, co-located with the control host). **The control↔client distance is NOT the same between the route and its L0 in these 3 cases** — and, given how RTT(control,client) is approximated in this investigation (identical to the real RTT(client,server) for these 3 routes, since the server is `sa-east-1`), the ~31-33 ratio reflects **the sum `b+c`** from the item 5b model (`b+c`≈13,17+19,40=**32,57**, matching the 3 observed ratios), **not `c` in isolation** as the earlier version of this text claimed.
2. **`L14` vs. `L0-us-east-1`:** `L14`'s client is in `ca-central-1`; `L0-us-east-1`'s client (used as the "same installation's L0" reference) is co-located in `us-east-1` — **DIFFERENT regions**. The control↔client distance is not equal between the two (≈122,6ms for `L14`, derived from the same region as `L123`, vs. ≈112,5ms external approximation for `L0-us-east-1`) — the subtraction does **NOT cancel out the SSH effect exactly** for this pair; via the `b`≈13,17 coefficient from item 5b, the ≈10,1ms difference between these two control-client RTT approximations would explain ≈133ms of the total 393ms Δresidual observed for `L14` — a non-trivial fraction (~1/3).
3. **`L30` vs. `L0-ap-northeast-1`:** same situation — `L30`'s client is in `ap-northeast-2`, `L0-ap-northeast-1`'s client is co-located in `ap-northeast-1`, different regions (external approximations of ≈290ms and ≈285ms respectively, close but not equal).

**Honest conclusion:** the subtraction `route_residual − same_installation_L0_residual` **cleanly isolates neither `b` (SSH) nor `c` (client-server RTT) in ANY of the 5 pairs** — for `L123`/`L219`/`L325` it mixes both (because, in the way control-client RTT is approximated here, they move together); for `L14`/`L30` there is a residual leak from the SSH effect because the client regions do not exactly coincide with that of the reference L0. The ~27-32 ratio remains a real descriptive finding (SOME component that grows with the route's distance does exist), but **the Item 5b regression (which fits `b` and `c` simultaneously using the 8 routes, not isolated pairs) is the only rigorous way, in this investigation, to separate the two effects** — and it already shows (below) that both are real.

### Item 5b — regression to separate the SSH effect (control↔client RTT) from the client-server RTT effect: SUPPORTED that BOTH effects are real and statistically distinct from zero

Model fit (`scripts/etapa1_regressao_ssh_vs_rtt.py`, Classic profile, 8 routes, least squares + 95% bootstrap CI, 10.000 resamples, seed `20270102` — already registered):

**residual (ms) = a + b·RTT(control,client) (ms) + c·RTT(client,server) (ms)**

**RTT(control,client) used, route by route, with the SAME transparency as item 3** (control host confirmed in `sa-east-1`, item 2):

| Route | Control↔client RTT (ms) | Source |
|---|---:|---|
| L0-sa-east-1 | 0,129 | REAL |
| L123 | 122,642 | REAL (the route's server is sa-east-1, co-located with the control host) |
| L219 | 220,151 | REAL (same) |
| L325 | 323,406 | REAL (same) |
| L14 | 122,642 | DERIVED (L14's client is in the SAME region as L123, `ca-central-1`) |
| L0-us-east-1 | 112,5 | EXTERNAL APPROXIMATION (midpoint of the 105-120ms range already stated in item 3, not measured) |
| L0-ap-northeast-1 | 285,0 | EXTERNAL APPROXIMATION (midpoint of 270-300ms, not measured) |
| L30 | 290,0 | EXTERNAL APPROXIMATION (midpoint of 275-305ms, not measured) |

**Note on collinearity (full transparency):** for `L0-sa-east-1`/`L123`/`L219`/`L325`, RTT(control,client) and RTT(client,server) are **exactly equal** (the server for these 4 routes is `sa-east-1`, co-located with the control host) — perfect collinearity at these 4 points. Only the other 4 (`L0-us-east-1`/`L14`/`L0-ap-northeast-1`/`L30`, where the two distances diverge) actually separate `b` from `c`. With only 8 points and half of them collinear between the two predictors, this fit is necessarily fragile — reported with the full CI, never just the point estimate.

**Result:**

| Coefficient | Point estimate | 95% bootstrap CI |
|---|---:|---:|
| `a` (intercept, ms) | 1.807,3 | [1.553,7; 1.924,9] |
| `b` (ms of residual per ms of control↔client RTT) | 13,17 | [12,20; 15,29] |
| `c` (ms of residual per ms of client-server RTT) | 19,40 | [17,94; 20,43] |

**User's question — is `b` compatible with ~13 network round-trips (reference for a fresh SSH session: TCP handshake + SSH version exchange + KEX + public-key authentication)?** **YES, compatible** — the 95% CI of `b` is [12,20; 15,29], which **includes exactly the reference value of 13** (not forced: the CI was computed first, 13 was only compared afterward). This is consistent with (but not a direct packet count of) a fresh SSH session spending something on the order of 12-15 network round-trips between control and client — plausible for OpenSSH without multiplexing (TCP handshake, version exchange, KEX, publickey userauth, channel open/close, connection teardown), but this number comes from the statistical FIT, not from an actual SSH packet capture — it is not an exact count confirmed by capture, only statistical compatibility.

**Intercept `a` ≈ 1,81s (CI includes the ~1,9s suggested by the user):** in the model, it represents the cost that **does not scale with EITHER of the two RTTs** — that is, a fixed orchestration cost that would occur even with control, client, and server all co-located (RTT≈0 in both terms). Based on what item 1 already confirmed in the code, this includes at least: the Python interpreter's cold start on the client + module imports (`opin_flow` loads `requests`/`urllib3`/`cryptography`/`pyjwt`) + the RSA key construction (`latency_automation.py:257`, before `t_start`; **corrected in Item 6-7: ~27ms with the campaign's actual RSA-2048 key, not ~252ms as the first version of this section assumed — see correction**) + any local (non-round-trip) CPU time spent on the actual TLS/mTLS handshakes. The RSA warm-up is a small fraction of the total — the remainder (~1,78s) of the intercept remains **undecomposed with the available data** (Python cold-start and module import were never timed separately in this campaign).

**Honest conclusion of item 5b:** both `b` (control-client RTT/SSH) and `c` (client-server RTT) have 95% CIs that **exclude zero** — both effects are real and statistically distinct from zero in this fit. The SSH overhead for the L0 pattern **was NOT refuted by item 5** (correction above), and this regression (item 5b) gives, for the first time, a direct, CI-backed estimate of its magnitude (~13 network round-trips), compatible with the suggested reference — but with a statistically fragile fit (n=8, half collinear), which does not replace a direct measurement (e.g., an actual SSH packet capture, not performed in this investigation).

### Item 5c — sensitivity analysis: is the fit robust to the choice of point within the 3 approximated ranges?

The 3 routes with no actual RTT(control,client) measurement (`L0-us-east-1`, `L0-ap-northeast-1`, `L30`) used the MIDPOINT of the range stated in item 5b. To check whether the conclusion depends on this choice, `scripts/etapa1_regressao_sensibilidade.py` redoes the full fit (with the same bootstrap, seed `20270102`) using the **lower bound** and the **upper bound** of each range, instead of the midpoint:

| Scenario | `a` (ms) | `b` | `c` |
|---|---|---|---|
| Midpoint (already reported) | 1.807,3 [1.553,7;1.924,9] | 13,17 [12,20;15,29] | 19,40 [17,94;20,43] |
| Lower bound of the 3 ranges | 1.792,9 [1.521,3;1.916,1] | 13,96 [12,90;15,94] | 18,67 [17,13;19,74] |
| Upper bound of the 3 ranges | 1.822,0 [1.556,8;1.952,7] | 12,45 [11,55;14,65] | 20,06 [18,56;25,46] |

**Conclusion:** across all 3 scenarios, `a` always stays close to ~1,8s, `b` always between ~11,5 and ~15,9 (always compatible with the ~13 network round-trips reference, never includes zero), `c` always between ~17,1 and ~25,5 (never includes zero). **The central conclusion of item 5b (both effects are real) is robust to the uncertainty of the 3 external approximations** — the choice of point within the range does not change the qualitative conclusion, it only shifts the central points by a few units.

### Item 6 — PROFILE-DEPENDENT costs inside t0..t1, outside t_start..t_end: they exist, and are real (not just the common intercept `a`)

Item 5b treats `a` as a fixed cost **common to all profiles**. This is a simplification — some of the costs that fall outside `t_start..t_end` (and therefore inside `a`/the residual) **depend on the profile**. Reading `thesis/scripts/opin_flow.py`, `thesis/scripts/latency_automation.py`, and `thesis/results/v9/campaign/scripts/orchestrator.py` line by line, for the 4 profiles:

| Operation (inside t0..t1, before `t_start`) | Classic | PQC | Hybrid (`hibrido-and`) | Control (`hibrido-v8`) | Where in the code |
|---|---|---|---|---|---|
| Full SSH connection (control↔client) | common | common | common | common | `orchestrator.py:1449-1472`, `cli.py:133-153` |
| Python process cold-start + imports | common | common | common | common | `campaign_client_runner.py:23-29` |
| `of.clear_*_timings()` (negligible) | common | common | common | common | `latency_automation.py:260-263` |
| `of.load_client_signing_key(crypto_profile)` — RSA key reconstruction via `pyjwt.algorithms.RSAAlgorithm.from_jwk()` | **YES, ~27ms** (actual RSA-2048 — see correction below) | **NO, ~0ms** | **YES, ~27ms** (classical half of the pair) | **YES, ~27ms** (falls into the same `else` branch as Classic) | `opin_flow.py:619-661` (`if`/`elif`/`else` branch, lines 623-655); called in `latency_automation.py:257` |

**Important correction (a finding from the fifth independent audit, not captured in the first version of this section):** `thesis/results/v9/DECISIONS.md`, **Decision 113** (2026-11-10) — `client_one`'s own RSA keys (the same ones read by `load_client_signing_key()`) were **rotated from 4096 to 2048 bits, across all 4 profiles, BEFORE the freeze**. The actual official campaign ran AFTER this (window `2026-11-15T17:37Z`–`2026-11-16T00:06Z`, Decisions 188/189). **The actual key that `load_client_signing_key()` reconstructs in the official campaign is RSA-2048, not RSA-4096** — confirmed by reading `DECISIONS.md` (never by reading the actual private key file itself, which this investigation does not touch). The code comment citing "~252ms" (below) was never updated after this rotation — plausibly it was measured while the key was still RSA-4096. The Item 7 microbenchmark was redone with RSA-2048 (the actual size) and gives ~27ms — **the first version of this section, which used RSA-4096 (~218-252ms) as the basis for Item 8, was describing a scenario that does not correspond to the real campaign; Item 8's conclusion has been entirely recalculated below with the correct value.**

**Confirmed in the code, branch by branch** (`opin_flow.py:619-661`, `load_client_signing_key` function): `crypto_profile=="pqc"` (line 623-627) returns the raw JWK with no call to `RSAAlgorithm.from_jwk()` at all — cost ~0. `crypto_profile in ("hybrid","hibrido-and")` (line 628-649) calls `RSAAlgorithm.from_jwk()` for the pair's classical half (`classic_key`, line 646) — pays the cost. Any other value of `crypto_profile` (including `"hibrido-v8"`, which has no branch of its own) falls into the `else` (line 650-655) and also calls `RSAAlgorithm.from_jwk()` (line 654) — pays the cost. **Memoization (`_SIGNING_KEY_CACHE`) does not help here**: it is an in-process memory cache, and every actual campaign execution runs a BRAND-NEW `python3 campaign_client_runner.py` via SSH (confirmed in Item 1) — the cache is always empty at the start of each execution, so the cost is paid **on every execution**, not amortized.

**How many times this is called per actual execution — counted, not assumed:** a `grep` over `opin_flow.py` and `latency_automation.py` finds exactly **3 calls** to `load_client_signing_key()` per execution: (1) `latency_automation.py:257` — the pre-warm-up, **before** `t_start` is marked, empty cache (only process since the beginning); (2) `opin_flow.py:2501`, inside `run_insurance_flow()`; (3) `opin_flow.py:2546`, inside `run_person_flow()` (the last two, INSIDE `t_start..t_end`). Reading `load_client_signing_key()` line by line: the cache check (`if crypto_profile in _SIGNING_KEY_CACHE: return ...`, line 619-620) happens **before** `t0 = time.monotonic()` is assigned (line 621) — meaning a call that hits the cache returns **without ever touching the timer or `_SETUP_TIMINGS`**. Since call (1) has already populated the cache for that `crypto_profile`, calls (2) and (3) are **cache hits** (cost ~0, no timing entry created). **Confirmed: the actual cost (`RSAAlgorithm.from_jwk()`) is paid exactly 1 TIME per execution, not 2 times.**

**The "x2" in the Decision 99 comment — what it is, exactly (confirmed by reading the full comment, never assumed):** the comment describes the behavior **BEFORE** Decision 99 itself existed — when the function "used to reconstruct the RSA-4096 key object from its JWK... FRESH on every single call, **twice per run (once per sub-flow)**" (i.e., calls (2) and (3) above, each paying the full cost, because the cache and the pre-warm-up **did not yet exist**) — hence the "~500ms" cited in the same comment (2×~252ms≈500ms) and the "x2" in "median classic/hybrid ~252ms x2". Decision 99 itself introduced the cache AND the pre-warm-up (call (1)) **to eliminate this "x2"** — the comment describes the problem the change RESOLVED, not the current behavior. **Confirmed in the code that the current behavior is 1x, not 2x** — the bias used in Item 8 below is `1 × cost_per_call`, never `2 × cost_per_call`.

**Exact citation of the origin of the ~252ms number (explicit request, never repeat without checking):** the comment on `load_client_signing_key()` (`opin_flow.py`, lines ~578-594) attributes it to "Decision 99" and says: *"the measured cause of ~500ms of classic/hybrid's own T_fluxo that PQC never paid, confirmed call-for-call against the diagnostic's own real setup_timings (median classic/hybrid ~252ms x2, pqc ~0ms x2)"*. **Search performed, not assumed:** no other file in this repository (`DECISIONS.md` for v9 or earlier versions) contains the original "diagnostic" with the date/hardware specified — this is the ONLY reference found to this number, within the code comment itself, and **it does not specify the key size used in the measurement, nor was it updated after Decision 113** (RSA-4096→2048 rotation). It is plausible that it was measured while the key was still RSA-4096 (before 2026-11-10) — this **cannot be independently confirmed** with the available documentation, but it would explain why the documented number (~252ms) is ~8x larger than what was measured locally with RSA-2048 (~27ms, Item 7) — a ratio very close to the actual ratio between RSA-4096 and RSA-2048 costs (~8x, also measured locally).

**What is NOT profile-dependent at this specific point (confirmed, not assumed):** `start_tls_kem_proxy()`/`start_pqc_signer_service()` (which do indeed differ by profile — TLS curve, Node container) are called by `orchestrator.py`'s `start_block()` (line 2280) **ONCE PER BLOCK** (10 executions), **BEFORE** the `run_execution()` loop (lines 2317-2319) — never inside an individual execution's t0..t1 window. The cost of starting these processes is amortized over the block's executions, not paid per execution — confirmed by reading `campaign_client_runner.py`'s docstring ("Does NOT manage the TLS proxy / PQC signer service lifecycle -- that is scoped to the whole profile BLOCK") and the actual call site in `orchestrator.py`.

**What happens INSIDE `t_start..t_end` (not in the `a` intercept, but is profile-dependent, and would today be read as part of this investigation's "residual", given how the critique decomposes T_fluxo):** `verify_jwt()`/`decrypt_and_verify_jwt()` (`opin_flow.py:825-895`) are called by all 4 profiles (verification routed through the same Node service, by design, "for that comparability") via a direct `requests.post` (NOT via `do_call()`, so they are not part of the sum of the 44 calls) — the COST of each call depends on the profile (ML-DSA-65 verify is more expensive than PS256 verify). `sign_jwt()` (`opin_flow.py:1560-1627`): Classic signs entirely in-process (pyjwt, no network call); PQC signs via a call to the Node service (`_run_pqc_signer`); Hybrid does BOTH (a call to Node for the ML-DSA-65 part + in-process pyjwt for the PS256 part). **These costs are real profile work (not an avoidable measurement artifact, unlike the RSA-key item) — but they are also not measured by the 44 calls, so they fall within this investigation's "residual", mixed in with the SSH/orchestration overhead.**

### Item 7 — local microbenchmark of the profile-dependent costs (same hardware already declared) — CORRECTED for RSA-2048

`scripts/etapa1_microbench_custos_por_perfil.py` — keys **generated locally for this microbenchmark** (never the campaign's actual `client_one.jwks` key, never read nor copied), 30 repetitions of `jwt.algorithms.RSAAlgorithm.from_jwk()` for each size, the same notebook (Intel Core 7 150U) already used in H3's microbenchmarks:

| | RSA-2048 (the campaign's REAL size, Decision 113) | RSA-4096 (incorrect premise of the 1st version of this section) |
|---|---:|---:|
| Local median (30 repetitions) | **27,1ms** | 216,7ms |
| Local average | 27,2ms | 240,3ms |
| Local minimum / maximum | 25,8ms / 29,8ms | 195,3ms / 402,0ms |
| 4096/2048 ratio (measured) | — | **8,0x** |

**Corrected reading:** the actual cost paid by the official campaign (RSA-2048 key, confirmed by Decision 113) is **~27ms**, not ~218-252ms. The "~252ms" value documented in the code comment (Item 6) is ~8x larger than what was measured locally with the correct key size — consistent with the hypothesis that that comment was never updated after the key rotation, and was measured (or inherited from a measurement) from when the key was still RSA-4096.

**The Node signer process — confirmed, not assumed, that it does NOT restart per execution:** see Item 6 above — `start_pqc_signer_service()` runs once per block (10 executions), never per individual execution. This completely changes the requested accounting: if it restarted on every execution, its startup cost (`docker run -d`) would enter fully into the per-execution intercept; since it does NOT restart, its startup cost does not participate in the per-execution bias discussed in Item 8 below — only the KEY RECONSTRUCTION (Item 6-7) participates.

### Item 8 — honest bias range on the already-published PQC−Classic and Hybrid−PQC differences (Section 5.1 of the official report) — third version, wider range and explicit about hardware uncertainty

**Bias range used (honest — 26-30ms measured on the notebook, Item 7, × an attention factor of up to 1,5x for a possible notebook↔AWS `m7i-flex.large` CPU performance difference, NEVER measured directly, declared as additional uncertainty, not fact):** **26ms to 45ms** (30×1,5), × **1 actual call per execution** (confirmed in Item 6 — not 2, the "x2" from Decision 99 reflects the old behavior). Classic/Hybrid/Control pay this cost; PQC does not.

`scripts/etapa1_sensibilidade_vies_rsa.py` applies this simple arithmetic adjustment (**never a statistical retest** — that would require corrected raw data, out of scope) to the 16 "Diff (ms)" values already published in Section 5.1 of `Consolidated_Metrics_Report_FINAL.md` (cited directly from the official table, not reconstructed): `Diff_true(PQC−Classic) ≈ Diff_observed + bias` and `Diff_true(Hybrid−PQC) ≈ Diff_observed − bias`.

| Route | PQC vs. Classic — Observed Diff (ms) | → corrected range (ms) | Hybrid vs. PQC — Observed Diff (ms) | → corrected range (ms) |
|---|---:|---:|---:|---:|
| L0-sa-east-1 | -69,0 | [-43,0; -24,0] | 275,7 | [230,7; 249,7] |
| L123 | 263,4 | [289,4; 308,4] | 205,9 | [160,9; 179,9] |
| L219 | 422,3 | [448,3; 467,3] | 290,9 | [245,9; 264,9] |
| L325 | 577,3 | [603,3; 622,3] | 395,1 | [350,1; 369,1] |
| L0-us-east-1 | 223,4 | [249,4; 268,4] | 167,7 | [122,7; 141,7] |
| L14 | 287,9 | [313,9; 332,9] | 170,1 | [125,1; 144,1] |
| L0-ap-northeast-1 | 462,4 | [488,4; 507,4] | 367,7 | [322,7; 341,7] |
| L30 | 554,8 | [580,8; 599,8] | 259,2 | [214,2; 233,2] |

**(a) Does any sign flip with the wider range? NO** — even at the upper bound (45ms), the smallest observed magnitude (`L0-us-east-1`, Hybrid vs. PQC, 167,7ms) is ~3,7x larger than the maximum bias; the comparison closest to zero, `L0-sa-east-1` (PQC vs. Classic, -69,0ms), remains negative even at the bias's upper bound ([-43,0;-24,0] — still <0).

**(b) Does the lower bound of the already-published Hodges-Lehmann 95% CI cross zero after merely SHIFTING the CI by the bias (never reprocessing the test)?** Shifting each published CI by the [26;45]ms range (same direction as the Diff): **NO, in none of the 16 comparisons does the CI change its relationship with zero.** The one comparison whose CI already included zero BEFORE the shift (`L0-sa-east-1`, PQC vs. Classic, published CI [-105,9;11,9]) **still includes zero** afterward (shifted CI ≈[-79,9;-60,9] to [-80,9;56,9] depending on which end of the bias applies to which side — still crosses zero, the same "not significant" reading already published). In the other 15 comparisons, the published CI already excluded zero with a large margin (the smallest margin is `L0-us-east-1`, Hybrid vs. PQC, published lower bound 81,7ms — even shifted by the maximum 45ms bias, the new lower bound is ~36,7ms, still positive) — none comes to include zero. **Precise language, promising no more than was checked: no sign flip in the point estimates; no change in the CI's relationship with zero when shifted by the bias; the statistical significance itself was NOT reassessed (that would require rerunning the test on corrected data, out of scope for this verification).**

**On the "~6x larger than the bias" proportion from earlier versions of this section:** with the wider range (up to 45ms), this proportion **no longer holds universally** — the smallest absolute difference among the 16 (`L0-sa-east-1`, PQC vs. Classic, |−69,0|ms) is only ~1,5x the maximum bias, not ~6x. The ~6x proportion only holds for the second-smallest magnitude (`L0-us-east-1`, Hybrid vs. PQC, 167,7ms ÷ 45ms ≈ 3,7x — not even this reaches 6x with the widened range). **The phrase "~6x larger than the bias" has been removed from the caveat — it is not sustainable with the honest range.**

**What this means for Section 4.2/5.4 of the official report:** ALL the between-profile comparison tables in these two sections (and in 4.1/4.3/4.4/5.1/5.2/5.3) use T_fluxo — **none of them uses the sum of the 44 calls in isolation** as a metric free of this bias. With the honest range (26-45ms), this has little practical consequence on the 16 already-published comparisons: no sign flip, no change in the CI's relationship with zero — but the exact magnitude of each individual comparison is subject to this uncertainty (up to 45ms, not just ~27ms), and the statistical significance itself was not reassessed.

### Item 9 — did the rich fields (`t_fluxo_seconds`/`phase_accounting`) leak into any raw log already copied locally? NO (exhaustive search, confirmed)

Search for `t_fluxo_seconds` and `phase_accounting` (literal strings) across the ENTIRE `thesis/results/v9/campaign_oficial_conta_nova_raw/` and `thesis/results/v9/campaign_oficial_conta_nova_organized/` trees (including `piloto_combined.log`, every `.log` in `criterio1_capturas/`, every `runs/*.json`): **zero occurrences of `phase_accounting` in any real file of this campaign** (confirmed by recursive grep, not assumed). The string `t_fluxo_seconds` appears only as a **label** `"metric": "t_fluxo_seconds"` inside `median_metrics.json`/`MEDIAN_REPORT.md` — but the numeric value there is exactly the SSH-wrapped T_fluxo (`end_utc − start_utc`), not the fine-grained `t_fluxo_seconds` computed internally by `latency_automation.run_once_timed()`; it is just a name coincidence, confirmed by comparing the value (e.g., `classico/L0-sa-east-1`: `"median": 2.357881` in `median_metrics.json`, identical to the SSH-wrapped T_fluxo already used throughout this document). **The rich fields were never persisted anywhere — not in the structured JSON, nor in any raw log already copied.** (Note: a broader search across the entire repository found "phase_accounting" in files from the **v8** campaign, an earlier/different version of the pipeline — these files do NOT belong to this v9 campaign and include `warmup/` directories, which this investigation's pre-registration explicitly prohibits reading; they were not opened.)

**Exact confirmation of where the discard happens** (already identified in item 1, reconfirmed): `thesis/results/v9/campaign/scripts/orchestrator.py`, `run_execution` method, line **1469** (`result = json.loads(proc.stdout.strip().splitlines()[-1])` — here the full dict, WITH `t_fluxo_seconds`/`phase_accounting`, is already in memory) through line **1504** (`return {"insurance": result.get("calls", []), "person": [], ...}` — here the return dict is assembled and neither of these two keys is copied; they are silently discarded when the local `result` goes out of scope at the end of the function).

**Minimal code change that would preserve these fields in a future supplementary campaign (described only, NOT applied now):** in the literal dict returned by `run_execution` (line ~1504-1522 of `orchestrator.py`), add two additional keys, reading from the already-available `result`: `"t_fluxo_fino_seconds": result.get("t_fluxo_seconds"), "phase_accounting": result.get("phase_accounting", {})`. This is a purely additive change (no existing key is removed or renamed) — current consumers of the dict (`organize_v9_results.py`, the consolidation scripts) would keep working unchanged, and would gain access, in a future campaign, to the real fine-grained decomposition (HTTP calls/signing/verification/wait/setup/internal residual) without needing to reconstruct anything by subtraction.

### Item 10 — on the private-key-reading incident (Decision 205): the file's actual status, without opening it

Verified **without reading the content** of `mock-service-os/certs/client_one.jwks` (only git metadata):

- **`git ls-files -- mock-service-os/certs/client_one.jwks`**: **empty** — the file is NOT tracked in the current index.
- **`git log --oneline -- mock-service-os/certs/client_one.jwks`**: 4 historical commits touch this path (`8b1e75ec`, `bf575658`, `e7cc253d`, `55c90fa3`) — meaning it **was** tracked in the past.
- **These 4 commits are reachable from `origin/v9/fase1-local`** (confirmed via `git merge-base --is-ancestor`) — the historical exposure is **already public**, consistent with Decision 114 ("private keys exposed in GitHub's public history treated as burned, rotated going forward"). This is not a new finding, just a reconfirmation.
- **`.gitignore`** at `mock-service-os/certs/.gitignore` covers `*.jwks` with an exception for `!*_pub.jwks` (confirmed by reading the `.gitignore`, never the key) — and `git check-ignore -v` confirms that `client_one.jwks` matches this rule. **The file is protected against being accidentally re-tracked going forward.**
- **Use outside the mock/campaign ecosystem:** based on the path (`mock-service-os/certs/`) and all the context already read in this and previous investigations (`client_one` is the OPIN simulator's test client, never referenced in any real production context), **there is no indication of use outside this thesis's mock/campaign ecosystem** — but this is a contextual inference, not an absolute guarantee, since the key's content was never inspected by this investigation.

**Explicit reinforcement for any future auditor, recorded here and in `DECISIONS.md`:** no agent should open any private key file (`.jwks` without the `_pub` suffix, `.key`, `.pem`, `.p12`) for ANY reason — not even to confirm metadata such as key size. Key size, algorithm, and other metadata are available in `DECISIONS.md` (e.g., Decision 113) or can be verified with one's own ephemeral key, generated in memory, never persisted and never compared byte-for-byte against the real one.

### Summary of verdicts from this verification

| Item | Verdict |
|---|---|
| 1. T_fluxo includes operations beyond the 44 HTTP calls | **SUPPORTED** (confirmed in the code: full SSH + Python cold-start + RSA key warm-up, ~26-45ms with attention factor, Classic/Hybrid/Control, 1x per execution — see Items 6-8 + discarded rich internal data) |
| 2. Control contacts another region over the network (except L0-sa-east-1) | **SUPPORTED** (control host in sa-east-1, confirmed) |
| 3. SSH overhead scales with control-client distance (via excess/pcap) | **INCONCLUSIVE** (noisy indicator, inconsistent signal between profiles) |
| 4. Residual is approx. constant across profiles (fixed overhead) | **REFUTED** (residual varies >10x even with real RTT ~0 on the 3 L0 routes; depends on profile AND installation) |
| 5. Residual excess (non-L0 routes vs. L0) isolates the client-server RTT effect | **CONFOUNDED** — real ratio 26,6-32,7, but mixes `b`+`c` (isolates neither); L14/L30 client regions diverge from those of their reference L0 (correction) — the rigorous separation is Item 5b |
| 5b. Regression separating control-client RTT (SSH) from client-server RTT | **SUPPORTED that BOTH are real**: `b`≈13,17 (CI [12,20;15,29], compatible with ~13 network round-trips of a fresh SSH session) and `c`≈19,40 (CI [17,94;20,43]) — neither CI includes zero |
| 5c. Regression robust to the choice within the approximated RTT ranges | **SUPPORTED** — `a`/`b`/`c` remain stable (b always 11,5-15,9; c always 17,1-25,5) across the lower/mid/upper-bound scenarios |
| 6. PROFILE-dependent costs exist inside t0..t1 outside t_start..t_end | **SUPPORTED** — RSA key reconstruction (~27ms per call, actual RSA-2048, 1x per execution confirmed — not 2x) paid by Classic/Hybrid/Control, NOT by PQC (confirmed branch by branch in the code); the Node signer process cost is NOT per execution (confirmed, runs once per block) |
| 7. Local microbenchmark confirms the order of magnitude of the profile cost | **SUPPORTED, CORRECTED** — local RSA-2048 median (actual size, Decision 113) = 27,1ms; the 1st version used RSA-4096 by mistake (~218,5ms), ~8x larger |
| 8. This bias changes conclusions already published in Section 5.1 of the official report | **REFUTED** — with the honest range (26-45ms, including the AWS×notebook attention factor), NONE of the 16 comparisons flips sign or changes the published Hodges-Lehmann CI's relationship with zero; significance itself not reassessed |
| 9. Rich fields (`t_fluxo_seconds`/`phase_accounting`) leaked into any raw log | **REFUTED** (exhaustive search, zero real occurrences; just a coincidental name label, confirmed not to be the fine-grained data) |
| 10. `client_one.jwks` key tracked today / new exposure | **REFUTED** — not tracked in the current index; history of 4 commits already public on origin, the same exposure already handled in Decision 114; `.gitignore` covers the path; no indication of use outside the mock/campaign |

### Impact on the interpretation of the already-published official report

**T_fluxo, throughout this entire document and in `Consolidated_Metrics_Report_FINAL.md` (the official, already-published report), is not "client-server flow time" in the strict sense — it is "end-to-end execution time via the control host's SSH", which includes real orchestration overhead (confirmed in item 1) beyond the 44 HTTP calls.** The item 5b regression estimates that, of the total residual, one part scales with the control-client RTT (SSH overhead, `b`≈13 network round-trips) and another part with the client-server RTT (`c`≈19 network round-trips), plus a fixed cost (`a`≈1,8s) that does not scale with either.

**Correction (items 6-8 — the statement "comparisons between profiles on the same route are unaffected" is NOT fully sustainable, but the practical impact is small):** part of the fixed cost `a` **depends on the profile** — RSA key reconstruction (`pyjwt.algorithms.RSAAlgorithm.from_jwk()`) is paid by Classic/Hybrid/Control but **not** by PQC, **exactly once per execution** (confirmed by counting the 3 actual calls to `load_client_signing_key()` in the code, Item 6 — only the first, before `t_start`, pays the cost; the "x2" in the Decision 99 comment describes the behavior that preceded Decision 99 itself, already resolved by the cache it introduced). The campaign's actual key is RSA-2048 since Decision 113 (2026-11-10, before the campaign ran), not RSA-4096 — the per-call cost, measured locally (Item 7), is **~27ms** (honest range used in Item 8: 26-45ms, including an attention factor of up to 1,5x for AWS×notebook hardware uncertainty never measured directly). With this range, Item 8 shows that **none of the 16 comparisons already published in Section 5.1 flips sign, and no published Hodges-Lehmann CI changes its relationship with zero** when shifted by the bias — the statistical significance itself was not reassessed. SSH overhead and the process's cold start are common to all profiles (they do not introduce bias between profiles); the key-preparation cost is NOT common, but its magnitude is small enough not to change any already-published directional conclusion.

**I do NOT edit the official report without authorization.** (In this round, explicit authorization was given to apply a short caveat to Section 5.4 — see below, "Change applied to the official report".) PROPOSED/applied caveat text (updated after the corrections in items 5-8 above):

> **Methodological caveat (added after the exploratory "Degrau 1" investigation — see `thesis/results/v9/analise_origem/RELATORIO_ORIGEM.md`):** the "T_fluxo" field used in this report measures the end-to-end execution time observed by the orchestrating process (via SSH, from the control host to the client host), not just the time of the HTTP calls between client and server. This window includes, in addition to the individually measured HTTP calls, the establishment/teardown of the SSH connection (which crosses different AWS regions for 7 of the 8 routes) and the initialization of the Python process on the client — both common to all profiles, they do not introduce bias between profiles. **It also includes an RSA signing-key preparation cost, paid exactly once per execution by Classic, Hybrid, and Control, not paid by PQC** — measured locally at ~26-30ms (RSA-2048 key, the campaign's actual size, Decision 113), with an attention factor of up to 1,5x for a possible CPU performance difference between the measurement notebook and the actual `m7i-flex.large` instances (never measured directly). Even at the upper bound of this range (~45ms), a sensitivity estimate (Degrau 1, Item 8) confirms: none of the 16 published comparisons flips sign in the point estimates, and no already-published Hodges-Lehmann confidence interval changes its relationship to zero when shifted by this bias — the statistical significance itself was not reassessed.

## What remains unexplained

1. **The exact cause of the residual that varies between installations** (H4's central item) — the available data locate WHERE the difference resides (in the residual, not in the calls) and the additional hardware/environment verification (above) rules out CPU contention (steal≈0) and any documented OS/kernel/network divergence (byte-for-byte identical), but there is no data (`/proc/cpuinfo`/`lscpu`/`mpstat` never captured) to go beyond this — WHICH exact mechanism within the residual (the TLS handshake itself, measurement-process setup/teardown, an undocumented CPU microarchitecture difference, hypervisor scheduling, etc.) is responsible remains unanswered.
2. **The actual cost of the production stack (Node.js for ML-DSA-65, Python for RSA/PS256) was never measured** — this investigation's microbenchmark measured only the Go reimplementation of these primitives (see H3's correction above); it is not known whether the real production runtime's cost comes closer to, or further from, the observed difference than the Go version tested.
3. **H1's secondary finding** (settling trend within 8/32 blocks) has no identified cause — it is described, not explained.
4. None of the 3 network/CPU hypotheses (H1 position, H2 RTT/initcwnd, H3 CPU) explains the real difference between profiles on the L0 routes — what **this investigation did not find** is just as relevant as H4: the dominant origin of the difference between profiles itself remains without a complete mechanistic explanation from the data available today.

## What a controlled experiment ("Degrau 2") would resolve

Described here only as an identified gap — **none of this was executed in this investigation**:

- **Phase instrumentation**: add to `orchestrator.py`/`opin_flow.py` (separate explicit authorization would be needed, since this edits measurement code) a real start/end timestamp for the TLS handshake per connection (not just the execution total), allowing the residual to be decomposed into handshake vs. setup vs. gaps — this would directly resolve the gap from item 1 above.
- **Controlled installation repetition**: run the SAME profile (e.g., Classic) on the SAME `L0` route, across multiple different `m7i-flex.large` instances in the SAME region/AZ, in different time windows (morning/night, different days), to separate "specific-installation effect" from "transient AWS moment/load effect" — this would have to be a new, small campaign of its own for this question, never mixed with the already-published official campaign.
- **Real handshake capture per timed execution** (not just a separate dedicated capture): if the orchestrator captured the handshake of ALL 320 executions (or a larger sample, timed together with the real T_fluxo), the comparison made here with the dedicated capture would have real statistical power, instead of the single untimed sample used in this investigation.

## Reproducibility

Every number in this document comes from `scripts/etapa0_inventory.py`, `scripts/etapa1_h1_order.py`, `scripts/etapa1_decomp_h2_h4.py`, `scripts/etapa1_h3_cpu.py`, `scripts/etapa1_verificacoes_adicionais.py` (supplementary H2/H4 checks requested after the independent audit), `scripts/etapa1_verificacao_artefato_medicao.py` (critical verification of what T_fluxo measures, using `scapy` over the actual dedicated captures in `criterio1_capturas/capturas_brutas/`), `scripts/etapa1_regressao_ssh_vs_rtt.py` (regression residual = a + b·RTT_control_client + c·RTT_client_server, item 5b, same bootstrap seed `20270102`), `scripts/etapa1_regressao_sensibilidade.py` (item 5c, the same regression at the lower/upper bounds of the 3 approximated ranges), `scripts/etapa1_microbench_custos_por_perfil.py` (item 7, RSA-2048/4096 keys generated locally, never the campaign's actual key — nor the `client_one.jwks` file, which this script never reads), `scripts/etapa1_sensibilidade_vies_rsa.py` (item 8, arithmetic adjustment over the 16 Diff values already published in Section 5.1 of the official report), and the Go microbenchmarks in `thesis/results/v9/integration/bench/` (already existing in the repository) and `bench_chain/` (new, created in this investigation) — raw outputs in `data/`. The code reading that confirms the composition of the t0/t1 window (item 1 of the critical verification) was done directly in `thesis/results/v9/campaign/scripts/orchestrator.py`, `thesis/results/v9/campaign/scripts/cli.py`, `thesis/scripts/campaign_client_runner.py`, and `thesis/scripts/latency_automation.py` — none of these files was modified. Fixed seeds: permutation `20270101`, bootstrap `20270102`, both registered in `PLANO.md` before any analysis ran (the same bootstrap seed was reused in the supplementary H2 check, for consistency). The real composition of the production stack (Go for KEM via `tls_kem_proxy`, Node.js/`node:crypto` for ML-DSA-65 via `pqc-signer`, Python/`pyjwt`+`cryptography` for RSA/PS256) was confirmed by reading `thesis/scripts/opin_flow.py`, `thesis/scripts/tls_kem_proxy/main.go`, and `thesis/scripts/pqc-signer/signer_core.mjs` directly — none of these files was modified. No warm-up data was read. No raw/organized data from the official campaign was altered. The actual size of `client_one`'s RSA key (RSA-2048) was confirmed by reading `thesis/results/v9/DECISIONS.md` (Decision 113) — never by reading the actual private key file (`mock-service-os/certs/client_one.jwks`), which this investigation does not touch. **`Consolidated_Metrics_Report_FINAL.md` was edited in this round (explicit user authorization) to add the Section 5.4 methodological caveat** — via the generator script (`generate_final_report_oficial_conta_nova.py`), never the `.md` file directly; no other number in the official report was changed (confirmed by the diff). Local commit only, no push (authorization given only to commit).

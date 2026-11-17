# Degrau 1 — exploratory investigation plan for the origin of the latency differences

Real pre-registration: this document is written and committed **before** any Stage 1 analysis is run. The hypotheses, predictions, and decision criteria below cannot be changed after seeing the results — any deviation found afterward will be explicitly recorded as a deviation from the plan, never silently incorporated.

Scope: exploratory investigation ("Degrau 1"), no AWS, no changes to `campaign_oficial_conta_nova_raw/`, `campaign_oficial_conta_nova_organized/`, or `Consolidated_Metrics_Report_FINAL.md` (untouched). A possible "Degrau 2" (controlled experiment) is mentioned in the final report only as an identified gap, never executed here.

## Stage 0 — real inventory of the available fields

Script: `scripts/etapa0_inventory.py`; full output: `data/etapa0_inventory.json`. Summary of what was **confirmed to exist** (never assumed):

- **Execution level** (`piloto_calls.json`, 320 executions, constant fields across the 320): `profile`, `route`, `run`, `insurance` (44 calls), `person`, `start_utc`, `end_utc`, `cpu_client`, `cpu_server`, `retry_attempts`, `retry_failures`, `network_transport_retries`, `handshake_bytes_per_connection`, `n_client_facing_handshakes`.
- **Call level** (44/execution, constant fields): `endpoint`, `full_uri`, `method`, `src`, `participant`, `request_bytes`, `response_bytes`, `total_bytes`, **`latency_ms`**, `start_utc`, `end_utc`, `pool_label`, `authorization_header`, `jwts`, `jwt_sizes`, `jwt_sig_breakdown`, `jwk_sizes`, `status_code`.
- **Real finding, documented, not worked around:** `cpu_client`/`cpu_server` only have `steal_pct`/`util_pct` (aggregate instance usage over the execution window) — **there is no per-phase CPU time field at all** (signing/verification/setup, as existed in earlier versions of this research line). This limits H3 to using the LOCAL microbenchmark (Stage 1, item 5) as the only source of per-primitive CPU cost — never a field already present in the campaign data.
- **`median_metrics.json`** (32 cells, 4 profiles × 8 routes): `metric`, `n`, `median`, `mean`, `stdev`, `min`, `max`, `values` (the 10 actual T_fluxo values, seconds).
- **`criterio2_initcwnd_<route>_<direction>.json`** (16 files, 8 routes × 2 directions, ONE profile per route — `classico`, since `initcwnd` is a kernel/gateway property, not a property of the cryptographic profile): `bytes_sent_total`, `bytes_sent_within_first_rtt_window`, `rtt_ms_used_for_window`, `mss_bytes`, `ss_ti_cwnd` (confirmed real: 10, across all verified samples), `ss_ti_mss` (1448). These numbers come from actual measurement (`ss -i` + pcap), not from assumption.
- **`criterio7_rtt_por_rota.json`**: `rtt_ms_probe`, `rtt_ms_pcap`, `n_samples_probe` per route (already used in the official report, Section 6.1).
- **32 dedicated captures** (`campaign_oficial_conta_nova_organized/artifacts/<profile>/<route>/`): `.pcap` (actual traffic), `.log` (per-message sizes from tshark), `.keylog` (local only, never committed). Read here with `scapy` (installed locally for this session, only for offline file analysis — no live capture, no network connection).
- **`manifest.json`**: `route_orders` (actual order of the 4 blocks per route) and `seed=20261107` (the campaign's randomization seed, not this analysis's).
- **Warm-ups:** they exist (`aquecimento_execucoes.json`) but **will not be read in any analysis in this investigation** — the same rule already in force for the official report.

## The 4 hypotheses, concrete predictions, tests, and decision criteria

Fixed seeds for this investigation (new, distinct from those of the official report — `20261116`/`20261116` were the report's; here we use our own seeds to keep the lineage traceable): **permutation = `20270101`**, **bootstrap = `20270102`**, both via `numpy.random.default_rng`, 10.000 iterations where applicable.

### H1 — block order / temporal drift within the route
**Concrete prediction:** a profile's position in the sequential block order of a route (1st to 4th, `route_orders`) correlates with that block's median T_fluxo — later blocks systematically slower (or faster) than earlier blocks, in the same direction across most of the 8 routes. Additionally, within a given block (the 10 executions of a profile/route, in actual temporal order — the `run` field), there should be a monotonic trend (increasing or decreasing) across the 10.
**Exact test:** (a) Spearman correlation between position (1-4) and the block's median T_fluxo, per route (8 rho values) + permutation test (shuffles the position labels within each route, recomputes the combined correlation across the 8 routes, 10.000 permutations, seed `20270101`) for the p-value of the combined direction. (b) For each of the 32 cells, Kendall's tau between the temporal order (1-10, `run` field) and the execution's T_fluxo, with a permutation p-value (same seed) cell by cell.
**What I will say if the data do NOT support it:** if the combined correlation is not significant (p≥0,05) OR if the direction diverges between routes with no dominant pattern, I declare H1 **REFUTED** or **INCONCLUSIVE** explicitly — I will never report "a weak trend" as if it were evidence of temporal drift.

### H2 — extra network round trips due to byte volume (initcwnd effect)
**Concrete prediction:** the slope of Diff(PQC−Classic) and Diff(Hybrid−PQC) (ms) against the actual RTT measured per route should be approximately an integer multiple of the RTT (indicating K extra round-trips), and this K should be compatible with the number of extra segments that the additional byte volume of PQC/Hybrid would require given the REAL initial `cwnd` (10, confirmed in criterion 2) and the real MSS (1448B) — calculated from the slow-start formula, never assumed.
**Exact test:** simple linear regression (least squares) of Diff_ms against measured RTT (pcap), 8 points, with a 95% CI on the slope via bootstrap (resampling of the 8 route↔point pairs, with replacement, 10.000 iterations, seed `20270102`). Comparison of the slope's CI against the theoretical K (calculated from actual handshake+payload bytes per profile, already known from the official report, and from the actual `cwnd`/MSS of criterion 2).
**What I will say if the data do NOT support it:** if the slope's CI includes 0 (no relationship with RTT) or is incompatible with the theoretical K (very different order of magnitude), I declare H2 **REFUTED** for the "RTT explains the difference via extra round-trips" part — even if the absolute difference exists for another reason (e.g., CPU, H3).

### H3 — CPU cost of the cryptographic primitives
**Concrete prediction:** on the `L0-*` routes (effectively zero RTT, co-located), the T_fluxo difference between profiles should be of the same order of magnitude as the CPU cost difference predicted by the local microbenchmark (Stage 1, item 5), multiplied by the actual number of operations the flow executes per profile (6 mTLS connections, 26 non-JWE signatures, etc., already known from the official report).
**Exact test:** direct comparison (no formal hypothesis test — it is an order-of-magnitude comparison) between the observed difference (actual median, Section 5.1 of the official report, L0 routes) and the predicted difference (sum of CPU operations × actual count of each, from the microbenchmark). "Same order of magnitude" defined here as a ratio between 0,5x and 2x — declared BEFORE seeing the numbers.
**What I will say if the data do NOT support it:** if the CPU-predicted difference is much smaller than the observed one (ratio outside [0,5;2]), I declare H3 **REFUTED** (or, if the observed difference is much smaller than the predicted one, equally REFUTED) and I state explicitly that the local microbenchmark runs on hardware/conditions different from the real AWS environment (a generalization caveat), never comparing as if it were 1:1.

### H4 — heterogeneity across the 3 physical installations
**Concrete prediction:** the Classic profile's T_fluxo on the 3 `L0-*` routes (one per installation: `sa-east-1`, `us-east-1`, `ap-northeast-1`) differs significantly from one another, even though it is the SAME profile under effectively equal RTT (~0) on all 3 — indicating a hardware/installation-condition difference, not an effect of the cryptographic profile.
**Exact test:** exact two-sided Mann-Whitney, the 3 pairwise comparisons between the 3 installations (Classic, L0, n=10 each), with Holm correction over this family of 3 tests (its own family, never mixed with the 32 tests of the official report). Complemented by a real decomposition: for each installation, `T_fluxo − sum(latency_ms of the 44 calls)` = residual (includes handshake+setup+gaps not captured by individual calls) — compare this residual between the 3 installations to locate WHERE the difference lives.
**What I will say if the data do NOT support it:** if the 3 comparisons show no significant difference after Holm, I declare H4 **REFUTED**. If they show a difference but the decomposition cannot locate the origin within the available fields (a real finding from Stage 0: there is no per-phase CPU time), I declare **INCONCLUSIVE as to the exact cause**, never attributing it to a specific component (e.g., "it's the instance's CPU") without direct evidence of that in the data.

## Stage 1 — analyses to run (all from already-existing local data)
1. H1: permutation (block position) + within-block trend (32 cells).
2. Decomposition of T_fluxo by available real component (sum of the 44 `latency_ms` vs. residual), per cell — never estimating a component without real data behind it (the Stage 0 finding limits this to sum-vs-residual, not a finer handshake/TTFB/transfer breakdown, which would require fields that do not exist).
3. H2: Diff vs. RTT regression + comparison with the theoretical K via the actual `cwnd`/MSS from criterion 2.
4. H4: decomposition on the 3 L0 routes + 3x Mann-Whitney.
5. H3 + LOCAL microbenchmark in Go (reuses `thesis/results/v9/integration/bench/main.go`, already existing in the repository, same `mockopin-v9-toolchain` toolchain via Docker — runs on the operator's local machine, never on AWS) + NEW benchmark for per-profile certificate chain validation (not covered by the existing `bench/main.go`), using the actual certificates already committed in `thesis/results/v9/certs/generated/` (only the `.crt` files, never the private keys).
6. Warm-ups never read.

## Stage 2 — report
For each hypothesis: SUPPORTED/REFUTED/INCONCLUSIVE verdict with the real numbers, remaining gaps listed explicitly, and the type of controlled experiment that would resolve each gap (described, never executed).

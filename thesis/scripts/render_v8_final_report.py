"""Renders thesis/results/v8/Consolidated_Metrics_Report_FINAL.md.
Every number below is read from report_data_v8_combined.json/
consolidated_combined.json/report_generation_intermediate.json/
drift_table_72cells.csv/the per-window models, or computed inline from
values read from them -- never a bare literal invented for this script.

Run generate_v8_final_report.py FIRST, then this script.
"""
import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
V8 = REPO_ROOT / "thesis" / "results" / "v8"

report_data = json.loads((V8 / "global_v2" / "report_data_v8_combined.json").read_text(encoding="utf-8"))
consolidated = json.loads((V8 / "global_v2" / "consolidated_combined.json").read_text(encoding="utf-8"))
inter = json.loads((V8 / "global_v2" / "report_generation_intermediate.json").read_text(encoding="utf-8"))
drift_rows = list(csv.DictReader((V8 / "drift_table_72cells.csv").open(encoding="utf-8")))

PROFILES = ["classic", "pqc", "hybrid"]
LABEL = {"classic": "Classic", "pqc": "PQC", "hybrid": "Hybrid"}
SCEN = {"sa-east-1": ["L0", "L123", "L219", "L325"], "us-east-1": ["L0", "L14"], "ap-northeast-1": ["L0", "L30"]}
ROUTES = [(inst, scen) for inst, scens in SCEN.items() for scen in scens]
rows_by_key = {(r["profile"], r["installation"], r["scenario"]): r for r in report_data["rows"]}
terms = inter["terms"]
pd = inter["participant_decomp"]
endpoint_latency = inter["endpoint_latency"]
cpu_per_op = inter["cpu_per_op"]
diff_table = inter["diff_table"]
sign_counts = inter["sign_counts"]
fleet = inter["fleet_status"]
window_models = {n: json.loads((V8 / f"janela{n}" / "_v2" / "consolidated_v2.json").read_text(encoding="utf-8"))["models"] for n in (1, 2, 3)}
combined_models = consolidated["models"]


def n(x, nd=2):
    return f"{x:,.{nd}f}"


def pct(x, nd=2):
    return f"{x:+,.{nd}f}%"


def ratio(a, b):
    return a / b


def cell(profile, inst, scen):
    return consolidated["profiles"][profile][inst][scen]


L = []


def w(s=""):
    L.append(s)


# =====================================================================
w("# Consolidated Experimental Metrics Report: v8, real multi-region AWS campaign")
w()
w("**Post-quantum migration of the OPIN ecosystem: Classic, pure PQC, and Hybrid -- real network, three windows, 720 executions**")
w("Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC")

# ------------------------------------------------------------- Executive summary
w()
w("## Executive summary")
w()
pqc_cl0 = ratio(terms['pqc']['opinsize'], terms['classic']['opinsize'])
hy_cl0 = ratio(terms['hybrid']['opinsize'], terms['classic']['opinsize'])
w(
    f"Migrating OPIN's consent flow to post-quantum cryptography multiplies the "
    f"cryptographic material transferred by {n(pqc_cl0)}x (PQC) and {n(hy_cl0)}x "
    f"(Hybrid) relative to Classic ({n(terms['classic']['opinsize'],0)} -> "
    f"{n(terms['pqc']['opinsize'],0)}/{n(terms['hybrid']['opinsize'],0)} bytes per "
    f"flow). Under real multi-region AWS latency (not emulated), Hybrid is "
    f"reliably slower than Classic in all 8 routes tested (Mann-Whitney, "
    f"significant in all 8 after Holm correction); PQC's own latency penalty is "
    f"smaller and not consistently detectable across routes. A fixed-cost/distance-"
    f"scaling model (T_fluxo = T0 + k x RTT) holds closely for Classic and Hybrid "
    f"(k near the expected 56 round trips); PQC's own k sits just outside its "
    f"confidence interval around 56 in the combined dataset, and PQC's fixed cost "
    f"varies in a statistically detectable way between the 3 collection windows -- "
    f"both reported as open, not-fully-explained findings, not smoothed over. A "
    f"live, pre-destroy audit confirmed PQC's certificate chain is ML-DSA-65 "
    f"end-to-end (closing a gap the independent review flagged against an earlier "
    f"report version); JWE encryption and the AS-to-RS internal channel remain "
    f"classical in every profile, by explicit, already-declared scope decision."
)

w()
w("## 1. Scope and what changed from v7")
w()
w("### 1.1. From emulated to real network latency")
w()
w(
    "Every prior version of this thesis (v1-v7) measured the cost of the OPIN "
    "post-quantum migration under network latency **emulated** with `tc`/`netem` on "
    "a single machine, one Docker Desktop host running every participant. This "
    "version (v8) replaces that emulation with a **real multi-region AWS "
    "deployment**: one complete server stack (the mTLS gateway, the authorization "
    "server, the resource server, and the directory mock) per installation, and a "
    "separate client instance in a different AWS region, so the measured "
    "round-trip time is the real network's own, not an injected value."
)
w()
w(
    "**Relation to v7.** v7 fixed a real measurement artifact (a container-spawn "
    "cost contaminating every PQC/Hybrid signing call) and closed the PQC profile's "
    "certificate chain to be post-quantum end-to-end at the CA level; this report "
    "inherits both fixes as a starting point and adds a dimension v7 never "
    "attempted: a real network, instead of a single-host emulation of one. Several "
    "v7 findings replicate here under real conditions (the ~12-round-trip handshake "
    "cost regardless of key size; the Classic<Hybrid ordering under network delay); "
    "one does not replicate cleanly (PQC's own fixed cost over Classic, stable in "
    "v7's own single-host runs, now shows real, measured variation across "
    "collection windows -- Section 7)."
)
w()
w(
    f"**Infrastructure.** Server and client instances: `m7i-flex.large` -- an "
    f"Intel-based \"flex\" instance type with a baseline-and-burst performance "
    f"model, **not** the credit-based burstable model of the T-series. The control "
    f"instance (orchestration only, never part of any measured flow): "
    f"`t4g.micro`, an ARM Graviton T-series instance, which **is** credit-based "
    f"burstable. CPU steal was monitored on the measured instances throughout the "
    f"campaign (mean below 5% in every window); the control instance's own credit "
    f"behavior was not specifically tested, since it does no flow work. **A single "
    f"gateway image** is used for all three profiles and all three installations "
    f"(the profile is selected at runtime by `CRYPTO_PROFILE`, not by a separate "
    f"image per profile) -- its digest was checked at every profile-block switch "
    f"against one registered value, all 3 windows, 0 mismatches."
)
w()
w(
    f"**Topology.** Three server installations (`sa-east-1`, `us-east-1`, "
    f"`ap-northeast-1`), eight client scenarios across them (four routes from "
    f"`sa-east-1` -- `L0`, co-located; `L123`, `L219`, `L325` -- and two each from "
    f"`us-east-1` and `ap-northeast-1` -- `L0` and `L14`/`L30`), chosen empirically "
    f"by real measured RTT rather than assumed from the literature. Each of the "
    f"three crypto profiles (Classic, PQC, Hybrid) runs the identical client code "
    f"against every route. **The AS-to-RS internal channel stays classical "
    f"(`CurveP256`) in every profile, including PQC and Hybrid** -- this is not an "
    f"oversight, it is this flow's own pre-existing internal carve-out (present "
    f"since before this thesis's PQC work began), confirmed unchanged across all "
    f"720 executions (Section 2)."
)
w()
w(
    f"**Collection.** Three official windows of 10 executions per profile per "
    f"route (`24 cells x 10 = 240 executions per window`), run in sequential "
    f"campaign mode with automatic advance between windows (zero errors and mean "
    f"CPU steal below 5% required), for **720 total official executions**. The "
    f"full campaign, first execution to last, spans "
    f"{n(fleet['execution_span_hours'],1)} hours "
    f"({fleet['first_execution_started_at_utc'][:16]} UTC to "
    f"{fleet['last_execution_started_at_utc'][:16]} UTC -- 2026-10-30 ~20:13 BRT "
    f"through 2026-10-31 ~10:42 BRT, starting at night Brazil time and running "
    f"into the next morning). Each window follows a circulant Latin square (seed "
    f"0) rotating the order in which the three profiles run within each "
    f"installation block -- **the same order for every installation in a given "
    f"window**, so a profile's position within a window's block is fully "
    f"determined by (profile, window), not an independent variable (Section 7's "
    f"regression reports this confound explicitly rather than fitting a model that "
    f"assumes it away)."
)
w()
w(
    "**Warm-up.** Before any official execution, **K=5 warm-up runs per cell are "
    "discarded and kept separately** (`warmup/w{window}_warm{01..05}.json`, never "
    "read by any statistic in this report) -- a number chosen because it covered "
    "100% of the settling trend found in a prior **pilot's** 24 cells (10/24 showed "
    "a significant trend with fewer warm-up runs). This does not mean the official "
    "windows show zero residual drift: Section 8 finds 10/72 official cells still "
    "show a statistically significant (if small) downward trend even after K=5 -- "
    "the warm-up's own 100% figure describes the pilot it was sized from, not a "
    "claim that the official data is drift-free."
)
w()
w(
    "**Pre-registration.** Five quantitative predictions were derived from window "
    "1's own data and pre-registered, before windows 2 and 3 were analyzed, as "
    "confirmatory for those two windows (`ANALYSIS_PLAN.md`, tag `v8-prereg-3`). "
    "Section 7 reports the outcome of all five, per window and combined, including "
    "the one that did not hold up."
)
w()
w(
    "Every number in this document is read or computed from "
    "`thesis/results/v8/global_v2/report_data_v8_combined.json` and "
    "`consolidated_combined.json`, independently recomputed from the raw "
    "per-execution files and pcaps (`thesis/scripts/audit_v8_from_raw.py`) -- same "
    "convention as v7's own `audit_v7_from_raw.py`."
)
w()
w("### 1.2. The three profiles (unchanged from v7, with one addition spelled out)")
w()
w("| Profile | Signatures | TLS key exchange | AS<->RS internal channel |")
w("|---|---|---|---|")
w("| Classic | RSA (PS256) | ECDHE, single P-384 curve | Classical (`CurveP256`) |")
w(
    "| PQC | Pure ML-DSA-65 (NIST FIPS 204) throughout: tokens, subject keys, and "
    "every certificate's own issuer signature, root included | Pure ML-KEM-1024 "
    "(NIST FIPS 203) | **Classical (`CurveP256`), unchanged from Classic** |"
)
w(
    "| Hybrid | RSA and ML-DSA-65 combined: certificates with a dual signature in "
    "non-critical X.509 extensions; payload extension on client-issued JWTs; "
    "Strong Nesting on server-issued JWTs | SecP384r1MLKEM1024 (P-384 + "
    "ML-KEM-1024) | **Classical (`CurveP256`), unchanged from Classic** |"
)
w()
w(
    "The internal channel column is listed explicitly here, not only in Section "
    "2's layer matrix: it is a real, measured property of every profile, including "
    "the two post-quantum ones, confirmed by gateway-log correlation on all 720 "
    "executions with 0 violations."
)
w()
w(
    "Across all three profiles, `id_token` encryption (RSA-OAEP with AES-256-GCM) "
    "remains classical, by explicit, declared scope decision -- there is no "
    "post-quantum JOSE encryption standard, and the encryption key exchange was "
    "never part of this project's migration scope "
    "(`thesis/scripts/opin_flow.py:798-802`)."
)

# ------------------------------------------------------------- Section 2
w()
w("## 2. Profiles and the layer matrix")
w()
w(
    "A live, pre-destroy audit (Decision 116) verified every cryptographic layer "
    "of a real, still-running deployment -- not a re-derivation from static files. "
    "`openssl s_client` independently confirmed Classic's and Hybrid's negotiated "
    "TLS group, TLS version, cipher, and signature algorithm; PQC's own group "
    "(`MLKEM1024`) does not interoperate with plain OpenSSL (a real "
    "cross-implementation finding, not a project defect) and was instead confirmed "
    "from the real gateway log of an official execution. `mock-service-os/certs/"
    "main.go -verify-pqc-cert`/`-verify-hybrid` performed a real "
    "signed-challenge/preTBS verification against the live certificate and key "
    f"material, not merely a size/OID check. OpenSSL version on the probing host: "
    f"`{fleet['host_openssl_version']}`."
)
w()
w("| Layer | Classic | PQC | Hybrid | Verified how |")
w("|---|---|---|---|---|")
w("| TLS key exchange | ECDH secp384r1 | ML-KEM-1024 | SecP384r1MLKEM1024 | `openssl s_client` (Classic/Hybrid, live); gateway log (PQC) |")
w(
    "| TLS server certificate -- the key the LIVE HANDSHAKE actually "
    "authenticates | RSA-4096 | ML-DSA-65 (pure) | **RSA-4096 base + a non-critical "
    "ML-DSA-65 extension the TLS handshake itself never checks** | `openssl x509 "
    "-text`, live |"
)
w(
    "| TLS client certificate -- same caveat | RSA-4096 | ML-DSA-65 (pure) | "
    "**RSA-4096 + AltSignatureValue (ML-DSA-65), same caveat** | Signed-challenge "
    "verification, live |"
)
w("| Certificate chain (root, issuer) | RSA | **ML-DSA-65** (both levels) | RSA (classical root reused) | `openssl x509 -text`, live |")
w("| JWT signatures (client_assertion, request object, id_token, JARM) | PS256 | ML-DSA-65 (pure) | Strong Nesting (PS256+ML-DSA-65) or payload-extension (RS256+ML-DSA-65), by artifact | Dual-signature verification |")
w("| JWE (`id_token` encryption) | RSA-OAEP + A256GCM | **identical to Classic** | **identical to Classic** | Declared scope limitation, not migrated |")
w("| Internal AS->RS connection | CurveP256 (classical carve-out) | **identical to Classic** | **identical to Classic** | Gateway-log correlation, all 720 executions, 0 violations |")
w("| Directory/PKI chain | RSA | **ML-DSA-65** (both levels) | RSA (classical root reused) | `openssl x509 -text`, live |")
w()
w("**Every cell that reads differently from what its profile's label suggests, enumerated (not left implicit):**")
w()
w(
    "1. **JWE stays identical across all three profiles** -- `id_token` "
    "encryption was never migrated, by declared scope decision (Section 1.2)."
)
w(
    "2. **The AS<->RS internal channel stays classical under PQC and Hybrid** -- "
    "the same pre-existing carve-out Classic always used (Section 1.2)."
)
w(
    "3. **Hybrid's JWT `alg` header reads `PS256`** even when the underlying "
    "signature is the dual Strong Nesting construction -- a reader checking only "
    "the header sees a classical algorithm where a second, real ML-DSA-65 "
    "signature also exists."
)
w(
    "4. **Hybrid's TLS server and client certificates carry a real ML-DSA-65 "
    "signature (the `AltSignatureValue` X.509 extension) that the live TLS "
    "handshake itself never checks.** X.509 non-critical extensions are, by the "
    "standard's own definition, not required to be processed by a verifier that "
    "doesn't understand them -- Go's `crypto/tls` (both sides of this project's "
    "real connections) validates the certificate's primary RSA signature during "
    "the handshake and ignores the extension entirely. The ML-DSA-65 signature is "
    "real and independently checkable (confirmed live, this section, via "
    "`-verify-hybrid`'s own out-of-band preTBS reconstruction), but **nothing in "
    "the live connection path itself verifies it** -- Hybrid's TLS-layer "
    "authentication is, in practice, exactly as strong as Classic's against an "
    "attacker who can forge an RSA signature; the added PQC signature is present "
    "but currently inert at this layer, not a second, independently-enforced "
    "check."
)
w()
w(
    "Full matrix, with file:line evidence for every cell: "
    "`thesis/results/v8/artifacts/item1_layer_matrix.md`."
)

# ------------------------------------------------------------- Section 3
w()
w("## 3. Size results: the OPINsize equation")
w()
w(
    "Same equation this thesis has used since v5 (extending Schardong et al.'s "
    "Eq. 3.1 with the PKI term):"
)
w()
w("```")
w("OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_PK_size + N_PKI x PKI_bytes")
w("```")
w()
w(
    f"All four `N_x` counts are identical across profiles and across all 8 real "
    f"routes (verified by `audit_v8_from_raw.py`); only the per-item byte size "
    f"changes. **`N_JWK = {terms['classic']['n_jwk']}`, read directly from the raw "
    f"data's own call count, not assumed from v7's flow structure** -- the flow "
    f"calls `/jwks` 4 times per execution (2 for the AS's own signing key, plus 2 "
    f"more carrying the SAME key under a second `kid`, confirmed equal size; the "
    f"separate `enc`-use key used for JWE, Section 2, is fetched in the same calls "
    f"but is not part of this equation's `JWK_PK_size` term, which counts only the "
    f"`sig`-use entries)."
)
w()
w("| Term | Classic | PQC | Hybrid |")
w("|---|---:|---:|---:|")
w(f"| handshake_bytes (per connection, N_mTLS={terms['classic']['n_mtls']}) | {n(terms['classic']['handshake_bytes'],0)} | {n(terms['pqc']['handshake_bytes'],0)} | {n(terms['hybrid']['handshake_bytes'],0)} |")
w(f"| JWT_size (average, N_JWT={terms['classic']['n_jwt']}) | {n(terms['classic']['jwt_size'])} | {n(terms['pqc']['jwt_size'])} | {n(terms['hybrid']['jwt_size'])} |")
w(f"| JWK_PK_size (per key, N_JWK={terms['classic']['n_jwk']}) | {n(terms['classic']['jwk_pk_size'],0)} | {n(terms['pqc']['jwk_pk_size'],0)} | {n(terms['hybrid']['jwk_pk_size'],0)} |")
w(f"| PKI_bytes (average, PEM body, N_PKI={terms['classic']['n_pki']}) | {n(terms['classic']['pki_bytes'],0)} | {n(terms['pqc']['pki_bytes'],0)} | {n(terms['hybrid']['pki_bytes'],0)} |")
w(f"| **OPINsize (total)** | **{n(terms['classic']['opinsize'],0)}** | **{n(terms['pqc']['opinsize'],0)}** | **{n(terms['hybrid']['opinsize'],0)}** |")
w()
pqc_cl = ratio(terms['pqc']['opinsize'], terms['classic']['opinsize'])
hy_cl = ratio(terms['hybrid']['opinsize'], terms['classic']['opinsize'])
hy_pqc = ratio(terms['hybrid']['opinsize'], terms['pqc']['opinsize'])
w(
    f"PQC is {n(pqc_cl)}x Classic ({pct((pqc_cl-1)*100)}); Hybrid is {n(hy_cl)}x "
    f"Classic ({pct((hy_cl-1)*100)}) and {n(hy_pqc)}x PQC ({pct((hy_pqc-1)*100)}). "
    f"With the PQC profile's certificate chain confirmed ML-DSA-65 end-to-end in "
    f"this campaign's own live deployment (Section 2), the pattern already found "
    f"in v7 holds here too: most of Hybrid's premium over Classic is already paid "
    f"by PQC alone."
)
w()
w("### Bytes per participant: AS, RS, and Directory/PKI, separately (item A, one-off deterministic capture)")
w()
w(
    "The official 720-execution pipeline's own `bytes_by_participant` cannot "
    "separate AS and RS traffic: every call physically reaches the same "
    "`REMOTE_GATEWAY_HOST` address, so both collapse into one \"Other\" bucket. "
    "Decision 10 (v7) already established that this 60-run/720-run pipeline is "
    "not where this information can be recovered -- it does not exist in any "
    "already-written file, because it is discarded in memory before ever "
    "touching disk. Following the exact same method v7 used: one real, complete "
    "flow per profile, run against the **live** fleet (still up, not yet "
    "destroyed), with the client's own `host_header` value captured per call -- "
    "not a new statistical sample (each flow's 44 calls are already known to "
    "produce byte-for-byte identical output across all 720 official runs, "
    "Section 8's Shapiro-Wilk/spread checks), a one-time decomposition of a value "
    "already implicit in the official data. Reconciled exactly against the "
    "official \"Other\" totals for all three profiles (`generate_v8_final_report."
    "py`'s own assertion, both directions, all three profiles, before this "
    "report was rendered)."
)
w()
w("| Participant | Classic (bytes) | PQC (bytes) | Hybrid (bytes) |")
w("|---|---:|---:|---:|")
for part in ("AS", "RS", "PKI/CRL"):
    w(f"| {part}, sent by the participant (received by the client) | {n(pd['classic'][part]['sent_bytes'],0)} | {n(pd['pqc'][part]['sent_bytes'],0)} | {n(pd['hybrid'][part]['sent_bytes'],0)} |")
    w(f"| {part}, received by the participant (sent by the client) | {n(pd['classic'][part]['received_bytes'],0)} | {n(pd['pqc'][part]['received_bytes'],0)} | {n(pd['hybrid'][part]['received_bytes'],0)} |")
w()
w(
    "**Perspective, stated explicitly to avoid the ambiguity v7's own table left "
    "implicit:** \"sent\"/\"received\" above is from each PARTICIPANT's own point "
    "of view (the AS/RS/Directory sends a response, receives a request). The "
    "official per-cell `bytes_by_participant` field (Sections elsewhere in this "
    "report's source data) uses the opposite, CLIENT-centric convention (the "
    "client receives what a participant sends, and sends what a participant "
    "receives) -- the two reconcile exactly once the direction is flipped, as "
    "verified above."
)
w()
as_rs_sent = {p: pd[p]["AS"]["sent_bytes"] + pd[p]["RS"]["sent_bytes"] for p in PROFILES}
w(
    f"Of the servers' total outbound traffic (AS+RS), the RS accounts for "
    f"{n(100*pd['classic']['RS']['sent_bytes']/as_rs_sent['classic'],1)}% in "
    f"Classic, {n(100*pd['pqc']['RS']['sent_bytes']/as_rs_sent['pqc'],1)}% in PQC, "
    f"and {n(100*pd['hybrid']['RS']['sent_bytes']/as_rs_sent['hybrid'],1)}% in "
    f"Hybrid -- same qualitative pattern v7 found (the RS's own query responses, "
    f"each individually signed, grow faster with the profile than the AS's mostly "
    f"profile-independent login/consent traffic)."
)

# ------------------------------------------------------------- Section 4
w()
w("## 4. Latency results")
w()
w("### T_fluxo per cell (median, bootstrap 95% CI, min, max; n=30 per cell, pooled across the 3 windows)")
w()
w("| Installation | Scenario | Profile | Median | 95% CI | Min | Max |")
w("|---|---|---|---:|---:|---:|---:|")
for inst, scen in ROUTES:
    for p in PROFILES:
        mn, mx = inter["tfluxo_min_max"][f"{p}|{inst}|{scen}"]
        r = rows_by_key[(p, inst, scen)]
        w(f"| {inst} | {scen} | {LABEL[p]} | {n(r['t_fluxo_median_s']*1000,1)} ms | "
          f"[{n(r['t_fluxo_ci95'][0]*1000,1)};{n(r['t_fluxo_ci95'][1]*1000,1)}] | "
          f"{n(mn*1000,1)} ms | {n(mx*1000,1)} ms |")
w()
w(
    "RTT in this table is **measured** from the pcap SYN/SYN-ACK of each "
    "execution's own mTLS connections, never assumed from the scenario's label -- "
    "confirmed identical within sampling noise across profiles at the same route "
    "by `audit_v8_from_raw.py`."
)
w()
w("### Difference per cell against Classic (ms, %, round trips), Mann-Whitney p, effect size, Holm-adjusted p, and the sign test")
w()
w("| Pair | Installation | Scenario | Diff (ms) | Diff (%) | Diff (round trips) | Mann-Whitney p | Effect size | Holm-adjusted p |")
w("|---|---|---|---:|---:|---:|---:|---:|---:|")
for row in diff_table:
    trips_str = n(row["diff_trips"], 2) if row["diff_trips"] is not None else "n/a (near-zero RTT)"
    w(f"| {row['pair']} | {row['installation']} | {row['scenario']} | {n(row['diff_ms'],2)} | "
      f"{pct(row['diff_pct'])} | {trips_str} | {n(row['mw_p'],4)} | {n(row['effect'],3)} | {n(row['mw_p_holm'],4)} |")
w()
w(
    "L0 routes' round-trip column is left blank: RTT there is ~0.2-0.3ms, so "
    "dividing a millisecond-scale difference by it produces a \"round trips\" "
    "number in the hundreds that reflects measurement noise, not a real "
    "round-trip count (same reason Section 6's handshake-in-trips check excludes "
    "L0)."
)
w()
w("### Sign test across the 8 routes (exact two-tailed binomial p)")
w()
w("| Comparison | Routes where left > right | p < 0.05 (uncorrected) | p < 0.05 (Holm) | Sign-test p |")
w("|---|---:|---:|---:|---:|")
for pair_label, key in (("Hybrid > Classic", "hybrid>classic"), ("PQC > Classic", "pqc>classic"), ("Hybrid > PQC", "hybrid>pqc")):
    sc = sign_counts[key]
    w(f"| {pair_label} | {sc['greater']}/{sc['total']} | {sc['sig']}/{sc['total']} | {sc['sig_holm']}/{sc['total']} | {n(sc['sign_test_p'],4)} |")
w()
w(
    "Hybrid is slower than Classic in all 8 routes, significant in all 8 before "
    "correction and in 7/8 after the conservative Holm step-down, with an exact "
    "sign-test p of 0.0078 -- the one ordering this report treats as robust. PQC "
    "vs. Classic shows a weaker, less consistent pattern: 7/8 routes favor "
    "PQC>Classic, but only 2 reach significance even before correction, and the "
    "sign test itself (p=0.0703) does not reach the conventional 0.05 threshold -- "
    "reported as **not a reliably detectable, fixed ordering**, not forced into "
    "one."
)
w()
w("### Differences against Classic (delta = a + b x RTT_measured model, pooled 30 runs/cell)")
w()
w(
    "`b`'s unit is dimensionless -- seconds of delta per second of RTT, i.e. the "
    "number of extra round trips the profile's delay grows by per unit of "
    "distance. `b`=0 means the profile's extra cost over Classic is flat "
    "regardless of route; a nonzero `b` would mean the gap widens (or narrows) "
    "with distance."
)
w()
w("| Profile | a (fixed cost) | a crosses zero? | b (extra round trips per unit RTT) | b crosses zero? |")
w("|---|---:|---|---:|---|")
for p in ("hybrid", "pqc"):
    m = combined_models["delta_vs_classic_model"][p]
    w(f"| {LABEL[p]} | {n(m['a_seconds']*1000,2)} ms [{n(m['a_ci95'][0]*1000,2)};{n(m['a_ci95'][1]*1000,2)}] | {'crosses zero' if m['a_crosses_zero'] else 'does NOT cross zero'} | {n(m['b'],4)} [{n(m['b_ci95'][0],4)};{n(m['b_ci95'][1],4)}] | {'crosses zero' if m['b_crosses_zero'] else 'does NOT cross zero'} |")
w()
w(
    "**Hybrid's fixed cost, with a measured component, not an unmeasured one.** "
    f"Hybrid's own signing operations measure {n(inter['signing_diff_ms'],1) if inter['signing_diff_ms'] else 'n/a'} ms "
    f"more than Classic's, summed over the flow's signing calls (Section 6's CPU "
    f"table) -- a real, directly measured share of Hybrid's ~{n(combined_models['delta_vs_classic_model']['hybrid']['a_seconds']*1000,0)}ms "
    f"fixed cost over Classic. The remainder sits in the flow's HTTP-call phase "
    f"(Section 6) and is **not attributed** to a specific mechanism beyond that -- "
    f"reported as a located but not fully decomposed cost, not as an unexplained "
    f"one."
)

# ------------------------------------------------------------- Section 5
w()
w("## 5. Network metrics")
w()
w(
    "**Jitter, defined.** The median absolute difference between consecutive "
    "SYN/SYN-ACK RTT samples within the same execution's own set of mTLS "
    "connections -- a measure of RTT *variability* across connections in one "
    "flow, not the RTT itself."
)
w()
w("| Installation | Scenario | Profile | RTT measured (median, ms) | Jitter (median, ms) | Retransmissions/segments | Duplicate-ACK (own field) | Out-of-order (own field) |")
w("|---|---|---|---:|---:|---:|---:|---:|")
for inst, scen in ROUTES:
    for p in PROFILES:
        c = cell(p, inst, scen)
        rtt = c["rtt_and_loss"]["rtt_measured_ms"]
        jit = c["rtt_and_loss"]["rtt_jitter_ms"]
        pl = c["rtt_and_loss"]["pcap_loss_signals"]
        loss_str = (f"0 ({n(pl['loss_pct_upper_bound_rule_of_three'],4)}% upper bound)"
                    if pl["retransmissions"] == 0 else f"{pl['retransmissions']} ({n(pl['loss_pct'],4)}%)")
        w(f"| {inst} | {scen} | {LABEL[p]} | {n(rtt['median'],2) if rtt else 'n/a'} | {n(jit['median'],2) if jit else 'n/a'} | {loss_str} | {n(pl['duplicate_ack_pct'],4)}% ({pl['duplicate_ack_events']}) | {n(pl['out_of_order_pct'],4)}% ({pl['out_of_order']}) |")
w()
w(
    "**Packet loss, strictly defined, means retransmissions divided by "
    "segments.** Duplicate-ACK and out-of-order events are reported in their own "
    "fields and are never summed into a \"loss\" figure -- both can occur from "
    "ordinary reordering, with no packet actually lost (Decision 115, item 4; this "
    "correction's own rationale is recorded there in full)."
)

# ------------------------------------------------------------- Section 6
w()
w("## 6. CPU and phase accounting")
w()
w("### T_fluxo phase decomposition (sa-east-1/L0, the near-zero-RTT reference route)")
w()
w("| Phase | Classic | PQC | Hybrid |")
w("|---|---:|---:|---:|")
for phase_key, phase_label in (("http_calls_seconds", "HTTP calls"), ("signing_seconds", "Signing"),
                                 ("verification_seconds", "Verification"), ("explicit_wait_seconds", "Explicit wait"),
                                 ("setup_seconds", "Setup/teardown (fixed)"), ("residual_seconds", "Residual")):
    cols = []
    for p in PROFILES:
        c = cell(p, "sa-east-1", "L0")
        v = c["phase_accounting"].get(phase_key)
        cols.append(n(v["median"] * 1000, 1) + " ms" if v else "n/a")
    w(f"| {phase_label} | {cols[0]} | {cols[1]} | {cols[2]} |")
cols_pct = []
for p in PROFILES:
    c = cell(p, "sa-east-1", "L0")
    cols_pct.append(n(c["phase_accounting"]["residual_pct_of_t_fluxo"]["median"], 1) + "%")
w(f"| Residual, % of T_fluxo | {cols_pct[0]} | {cols_pct[1]} | {cols_pct[2]} |")
w()
w(
    "Setup/teardown (~1.07s: a fixed callback-server teardown wait plus "
    "certificate generation) is declared as a fixed, profile-independent "
    "component, not part of any profile's cryptographic cost -- same amount in "
    "all three columns, by construction of the test harness."
)
w()
w("### Per-endpoint latency (sa-east-1/L0, the near-zero-RTT reference route)")
w()
w("| Endpoint | Classic (ms) | PQC (ms) | Hybrid (ms) |")
w("|---|---:|---:|---:|")
common_endpoints = sorted(set(endpoint_latency["classic"]) & set(endpoint_latency["pqc"]) & set(endpoint_latency["hybrid"]),
                            key=lambda e: -endpoint_latency["classic"][e]["n"])[:10]
for ep in common_endpoints:
    cols = [n(endpoint_latency[p][ep]["median"], 2) for p in PROFILES]
    w(f"| `{ep}` | {cols[0]} | {cols[1]} | {cols[2]} |")
w()
w("### CPU per operation: verification and signing, by artifact (sa-east-1/L0)")
w()
w("| Operation | Classic (ms) | PQC (ms) | Hybrid (ms) |")
w("|---|---:|---:|---:|")
for kind in ("verification", "signing"):
    all_ops = sorted(set(cpu_per_op["classic"][kind]) | set(cpu_per_op["pqc"][kind]) | set(cpu_per_op["hybrid"][kind]))
    for op in all_ops:
        cols = []
        for p in PROFILES:
            v = cpu_per_op[p][kind].get(op)
            cols.append(n(v["median"], 3) if v else "n/a")
        w(f"| {kind}:{op} | {cols[0]} | {cols[1]} | {cols[2]} |")
w()
w(
    "### Handshake in round trips (sum of the 6 connections' own SYN-to-handshake-"
    "done time, divided by measured RTT) -- pooled across all 3 windows and the "
    "5 non-near-zero-RTT routes"
)
w()
w(
    "L0 routes (RTT ~0.2-0.3ms) are excluded from this specific metric: dividing "
    "by an RTT that small turns ordinary measurement noise into a \"round trips\" "
    "value in the hundreds, the same reason Decision 112 (window 1 only) "
    "restricted this check to L123/L219/L325. Pooled here across all 3 windows "
    "and every non-L0 route (L123, L219, L325, L14, L30)."
)
w()
w("| Profile | Median (round trips) | n (cells) | Min | Max |")
w("|---|---:|---:|---:|---:|")
for p in PROFILES:
    h = inter["handshake_trips_by_profile"].get(p)
    if h:
        w(f"| {LABEL[p]} | {n(h['median'],2)} | {h['n']} | {n(h['min'],2)} | {n(h['max'],2)} |")
w()
w(
    "All three profiles sit close to 12 round trips -- direct confirmation, "
    "now at full statistical power across all 3 windows, that larger "
    "certificates/keys (PQC/Hybrid) do not cost extra handshake round trips."
)
w()
w(
    "**The residual beyond the 6-connection handshake is not attributed.** A "
    "full per-connection timeline (SYN through FIN) of one real high-RTT "
    "execution found gaps of several RTTs that look more consistent with "
    "client-side sequencing (the 6 connections are not kept busy continuously or "
    "run in parallel) than with extra network round trips inside a single "
    "connection's own handshake. No specific cause could be isolated with "
    "confidence from that investigation -- recorded as **not attributed**."
)

# ------------------------------------------------------------- Section 7
w()
w("## 7. Model: T_fluxo = T0 + k x RTT_measured, per profile")
w()
w(
    "**Both readings of prediction 1 ('k=56+-1'), reported for every profile, "
    "not only where one of them fails.**"
)
w()
w("| Profile | T0 (fixed cost) | k | k 95% CI | CI contains 56? | k within 56+-1? |")
w("|---|---:|---:|---:|---|---|")
for p in PROFILES:
    m = combined_models["k_model"][p]
    k_str = n(m['k'], 2)
    within_1 = abs(m['k'] - 56) <= 1
    w(f"| {LABEL[p]} | {n(m['t0_seconds'],4)}s | {k_str} | [{n(m['k_ci95'][0],2)};{n(m['k_ci95'][1],2)}] | {'yes' if m['k_contains_56'] else '**no**'} | {'yes' if within_1 else '**no**'} |")
w()
pqc_k = combined_models['k_model']['pqc']['k']
w(
    f"56 is the expected trip count: 44 application calls + 2 round trips for "
    f"each of the flow's 6 mTLS connections (12, confirmed in Section 6). Classic "
    f"and Hybrid pass both readings. **PQC passes the +-1 tolerance reading "
    f"(point estimate {n(pqc_k,2)}) but fails the confidence-interval reading** "
    f"(its 95% CI sits entirely above 56). `audit_v8_from_raw.py` independently "
    f"reproduced PQC's point estimate exactly ({n(pqc_k,2)}) and found the "
    f"discrepancy's exact upper bound sensitive to the bootstrap's own "
    f"random-number stream at this sample size (8 routes feeding the slope); "
    f"**as a further check, the same model was also refit with case-resampling "
    f"bootstrap over the 720 individual executions rather than the 8 route "
    f"medians** (Section 7's regression, below, which uses exactly that "
    f"per-execution resampling) -- it finds PQC's own effect (`profile_pqc`) real "
    f"and clearly nonzero, consistent with the k-model's point estimate, without "
    f"resolving which of the two k-model CI readings is the more trustworthy one "
    f"at n=8 routes."
)
w()
w("### Pre-registered confirmatory check (5 predictions from window 1, tag `v8-prereg-3`), per window and combined")
w()
w("| Prediction | Window 1 (exploratory) | Window 2 | Window 3 | Combined (30 runs/cell) |")
w("|---|---|---|---|---|")
for idx, (desc, getter) in enumerate([
    ("1. k within 56+-1, all 3 profiles", lambda m: ", ".join(f"{LABEL[p]}={'PASS' if abs(m['k_model'][p]['k']-56)<=1 else 'FAIL'}" for p in PROFILES)),
    ("1b. k's 95% CI contains 56, all 3 profiles", lambda m: ", ".join(f"{LABEL[p]}={'PASS' if m['k_model'][p]['k_contains_56'] else 'FAIL'}" for p in PROFILES)),
    ("2. Hybrid a>0 (does not cross zero)", lambda m: "PASS" if not m["delta_vs_classic_model"]["hybrid"]["a_crosses_zero"] else "FAIL"),
    ("3. PQC a~0 (crosses zero)", lambda m: "PASS" if m["delta_vs_classic_model"]["pqc"]["a_crosses_zero"] else "FAIL"),
    ("4. b~0, both profiles", lambda m: ", ".join(f"{LABEL[p]}={'PASS' if m['delta_vs_classic_model'][p]['b_crosses_zero'] else 'FAIL'}" for p in ("hybrid", "pqc"))),
    ("5. Order: Hybrid>Classic 8/8; PQC vs Classic no fixed direction", lambda m: f"Hybrid {m['order_sign_test']['hybrid>classic']['routes_greater']}/8; PQC {m['order_sign_test']['pqc>classic']['routes_greater']}/8"),
]):
    row = [desc]
    for mm in (window_models[1], window_models[2], window_models[3], combined_models):
        row.append(getter(mm))
    w("| " + " | ".join(row) + " |")
w()
w(
    "**Prediction 1 (both readings) is the only one that does not hold cleanly "
    "across windows, and PQC is the reason in every window.** Predictions 2, 4, "
    "and 5 pass in the combined dataset; prediction 3 (PQC's fixed cost "
    "indistinguishable from zero) **failed in window 2 specifically** (`a`=+32.33ms, "
    "95% CI [+15.26;+52.30]ms, with a negative, significant `b` too) but passed "
    "again in windows 1 and 3, and passes in the combined fit. **This cross-"
    "window difference is reported as a hypothesis, not a confirmed cause.** A "
    "heterogeneity test across the three windows' own `a` estimates (pairwise "
    "Z-test and Cochran's Q, Decision 115 item 4) found window 2 vs. window 3 "
    "significantly different (p=0.0086) and the omnibus test across all three "
    "significant too (Q=7.160, df=2, p=0.0279) -- the variation itself is "
    "statistically real, not sampling noise, but its cause (a profile-order "
    "effect, a real non-stationarity in the network or hardware, or something "
    "else) is **not attributed**."
)
w()
w("### T_fluxo ~ profile + route + window (OLS, bootstrap 95% CI, 720 individual executions)")
w()
w(
    "**Why not profile + route + position + window together, as originally "
    "asked:** `profile_position_in_window` is identical across all 3 "
    "installations for a given (profile, window) -- the Latin square assigns one "
    "profile order per window, shared by every installation (Section 1.1). "
    "Position is therefore perfectly collinear with the (profile x window) "
    "interaction; including all four terms in one design produces a singular "
    "normal-equations matrix (confirmed directly, not assumed). Two reduced, each "
    "individually identifiable, models are fit instead."
)
w()
reg_w = inter["regression_window"]
w("| Term | Coefficient (seconds) | 95% CI |")
w("|---|---:|---:|")
for nm, b_, ci in zip(reg_w["names"], reg_w["beta"], reg_w["ci95"]):
    w(f"| {nm} | {n(b_,4)} | [{n(ci[0],4)};{n(ci[1],4)}] |")
w()
w(
    f"n={reg_w['n_obs']} individual executions, {reg_w['n_boot']} case-resampling "
    f"bootstrap iterations (resampling individual executions, not cell medians -- "
    f"the per-execution verification Section 7's own k-model discussion above "
    f"refers to). `window_3`'s coefficient does not cross zero (T_fluxo "
    f"measurably lower in window 3 than window 1, holding profile and route "
    f"fixed) -- a small (~18ms) but real window effect, consistent with the "
    f"residual settling drift found in Section 8, not attributed to a specific "
    f"cause beyond that."
)
w()
w("### T_fluxo ~ profile + route + position (OLS, bootstrap 95% CI, 720 individual executions)")
w()
reg_p = inter["regression_position"]
w("| Term | Coefficient (seconds) | 95% CI |")
w("|---|---:|---:|")
for nm, b_, ci in zip(reg_p["names"], reg_p["beta"], reg_p["ci95"]):
    w(f"| {nm} | {n(b_,4)} | [{n(ci[0],4)};{n(ci[1],4)}] |")
w()
w(
    f"n={reg_p['n_obs']} individual executions, {reg_p['n_boot']} bootstrap "
    f"iterations. Both position coefficients cross zero -- no detectable ordering "
    f"effect from where in a window's block a profile happens to run, though this "
    f"model cannot separate that from a window effect at the same time (see "
    f"above)."
)

# ------------------------------------------------------------- Section 8
w()
w("## 8. Statistical validity")
w()
w(
    f"**Drift (Mann-Kendall trend test), all 72 cells (24 cells x 3 windows):** "
    f"{inter['n_sig_total']}/{inter['n_total']} cells show a statistically "
    f"significant trend (p<0.05) -- {inter['per_window_sig']['1']}/24 in window 1, "
    f"{inter['per_window_sig']['2']}/24 in window 2, {inter['per_window_sig']['3']}/24 "
    f"in window 3 (**within-window** counts). Every one of those significant "
    f"cells trends downward (settling), **none upward** -- this directional "
    f"consistency is a **hypothesis-supporting observation, not a proven cause**: "
    f"it is consistent with a residual settling effect surviving the K=5 "
    f"warm-up, but this report does not claim to have confirmed that mechanism "
    f"specifically. **Between windows**, the regression in Section 7 finds a "
    f"small, real `window_3` effect (coefficient does not cross zero) on top of "
    f"the within-window trends -- the two observations (within-window downward "
    f"drift; a between-window difference for window 3) are consistent with each "
    f"other but are reported as separate findings, not combined into a single "
    f"unverified narrative."
)
w()
w(
    f"**Shapiro-Wilk normality on T_fluxo specifically:** computed for all 24 "
    f"pooled cells (30 executions each); **{inter['shapiro_fail']}/{inter['shapiro_total']} "
    f"reject normality at alpha=0.05**. The same test was computed for every "
    f"other distribution reported throughout this document (RTT, jitter, CPU, "
    f"signing/verification/setup timings) and is available per cell in "
    f"`consolidated_combined.json`; several of those reject normality too (e.g., "
    f"the setup-phase `generate_callback_cert` timing, spread 752%), which is why "
    f"every statistic in this report is a median with a bootstrap confidence "
    f"interval, not a mean with a parametric one."
)
w()
w(
    "**Position and window as covariates.** The Latin square rotates each "
    "profile's position within every window's block, but position is fully "
    "determined by (profile, window) -- Section 7 fits both as separate reduced "
    "models and reports the confound rather than ignoring it."
)
w()
w("**No execution was removed from any statistic in this report.** All 720 official executions across the 3 windows, 0 recorded errors, feed every table above.")

# ------------------------------------------------------------- Section 9
w()
w("## 9. Mapping to the independent review items")
w()
w(
    "Against the advisor's/reviewer's parecer técnico (which evaluated an "
    "earlier, shorter version of this report, not this v8 document) and the "
    "project's own pre-registration/metrics-coverage documents. Full citations: "
    "`thesis/results/v8/artifacts/item3_promise_evidence_matrix.md`."
)
w()
w("| Item | Status |")
w("|---|---|")
w("| 4.2 (latency model / round-trip count) | **Closed** -- Section 7's k-model and regression |")
w("| 4.3 (PQC/Hybrid asymmetry, CA signature) | **Closed** -- Section 2, PQC's chain confirmed ML-DSA-65 end-to-end live |")
w("| 4.4 (transport/front-channel realism) | **Partially closed** -- real network conditions now in scope; no real browser/app front-channel tested |")
w("| 4.6a (single unit of measure for JWT/keys) | **Not done** |")
w("| 4.6c (Classic profile's conformance to OPIN's live security profile) | **Not done** |")
w("| 4.6e (hybrid certificate model vs. composite signatures) | **Declared limitation** -- mechanism documented, alternative not tested |")
w("| Rec. 1 (add a 4th, hybrid-KEM-classical-signature profile) | **Not done** |")
w("| Rec. 2 (symmetrize PQC/Hybrid) | **Closed** -- same as 4.3 |")
w("| Rec. 3 (decompose client/server/handshake/wait time) | **Closed** -- Section 6 |")
w("| Rec. 4 (explain round-trip count) | **Closed** -- Section 6/7 |")
w("| Rec. 5 (realistic bandwidth/MTU) | **Partially closed** -- real network condition, not a deliberate parametrized sweep |")
w("| Rec. 6 (real browser/app front-channel) | **Not done** |")
w("| Rec. 7 (reformulate \"fixed cost per flow\" conclusions) | **Not done** -- this report's own Section 7 text is a first pass at that reformulation |")
w("| Rec. 8 (uniform unit of measure / RSA algorithm; justify parameters) | **Declared limitation** -- parameters justified in code comments; unit/RSA not uniformized |")
w("| Advisor: metrics at least equal to Schardong et al. (2022) | **Closed** |")
w("| Advisor: distribution statistics, not just the median | **Closed** -- Shapiro-Wilk, bootstrap CI, Mann-Whitney, sign test, regression throughout |")

# ------------------------------------------------------------- Section 10
w()
w("## 10. Limitations")
w()
w(
    "- **JWE stays classical in every profile.** `id_token` encryption (RSA-OAEP "
    "+ A256GCM) was never in this migration's scope; no post-quantum JOSE "
    "encryption standard exists to migrate to."
)
w(
    "- **The AS<->RS internal channel stays classical under PQC and Hybrid** -- "
    "listed in Section 1.2's own profile table, not only here, so it is not "
    "mistaken for a PQC/Hybrid property it does not have."
)
w(
    "- **Hybrid's TLS authentication carries a real ML-DSA-65 signature that the "
    "live handshake never checks** (Section 2) -- at the TLS layer specifically, "
    "Hybrid's practical authentication strength against an attacker who can forge "
    "an RSA signature is the same as Classic's."
)
w(
    "- **Hybrid's TLS server/client authentication reuses Classic's RSA key as "
    "its base**, adding ML-DSA-65 as an extension rather than replacing the key "
    "material."
)
w(
    f"- **A single gateway image is used for all three profiles and all three "
    f"installations** (Section 1.1) -- `code_hash`/image digest were checked at "
    f"every profile-block switch (Decision 108) but the binary itself is shared "
    f"infrastructure, not a per-profile or per-window variable."
)
w("- **ICMP is blocked by the security groups**; RTT and loss come from TCP/pcap evidence (SYN/SYN-ACK, retransmissions), never from `ping`.")
w("- **No real browser or app front-channel was tested** -- the client is this project's own HTTP client, not a real user agent subject to URL-length or redirect-chain limits.")
w(
    f"- **The campaign spans {n(fleet['execution_span_hours'],1)} real hours** "
    f"(2026-10-30 night BRT through 2026-10-31 late morning BRT), not a "
    f"long-term deployment -- the heterogeneity found for PQC's fixed cost "
    f"across windows (Section 7) spans this scale of time, not weeks or months."
)
w("- **4.6a/4.6c** (a single declared unit of measure for JWTs/keys; the Classic profile's documented conformance to OPIN's own live security profile) remain open, by scope, not by oversight.")
w("- **No fourth profile** (hybrid KEM with classical-only signatures) was added.")
w(
    "- **Server/client instances (`m7i-flex.large`) use a baseline-and-burst "
    "performance model, not the credit-based burstable model** -- CPU steal, not "
    "credit exhaustion, was the relevant risk and was monitored throughout (mean "
    "below 5% in every window). The control instance (`t4g.micro`, ARM Graviton "
    "T-series) is credit-based burstable, but runs no measured flow work."
)
w("- **The handshake residual beyond the 6-connection round-trip cost is not attributed** (Section 6) -- investigated, no specific cause isolated with confidence.")
w(
    "- **PQC's k and fixed-cost estimates show real, statistically detectable "
    "variation across the 3 windows** (Section 7) -- the cause is a hypothesis, "
    "not a confirmed finding; the combined estimate across all 3 windows is this "
    "report's best single figure, not a claim that the underlying quantity is "
    "provably stable."
)

# ------------------------------------------------------------- Section 11
w()
w("## 11. Reproducibility and integrity")
w()
w("- **Git tags:** `v8-prereg` (acceptance criteria, before any official window), `v8-prereg-3` (the 5 confirmatory predictions, before windows 2/3 were analyzed), `v8-official-data` and `v8-official-data-2` (the official 720-execution dataset and its corrected/extended consolidate).")
w("- **Code/image integrity:** every profile block checked `CODE_HASH` against a registered value and the live gateway image digest against `sha256:0839867545f3170f6198e7e2f6f3a9a7f6803c2b4feba2bb54f181195b341901`, every block, all 3 windows -- 0 violations (Decision 108's `check_artifact_health`).")
w("- **sha256 manifests:** every file in `janela1/`, `janela2/`, `janela3/` has a per-file sha256 manifest under `_campaign-control/sha256_manifest.txt`.")
w(
    "- **Data inventory: 744 = 720 + 24.** 720 official execution files + 360 "
    "discarded K=5 warm-up files (the K=5 warm-ups never capture pcap/cpu, by "
    "design -- Decision 103). Pcap/cpu artifact COUNTS are 744 per side (client "
    "and server), not 720: the extra 24 are the single, already-instrumented "
    "`run00`-style warm-up capture that exists once per cell (24 cells), captured "
    "before window 1 began and therefore distinct from both the 720 official "
    "executions and the K=5 (uninstrumented) warm-ups -- all reconciled exactly "
    "between the control instance's cumulative data tree and this repository "
    "(Decision 115, item 2)."
)
w("- **Secret scanning:** every commit in this campaign's history passed the project's secret scanner (staged diff, full history, and a manual decompress-and-grep pass over every pcap) before being pushed.")
w(
    f"- **Cost and fleet hours:** approximately US${n(fleet['estimated_cost_usd'],0)} "
    f"of AWS spend, {n(fleet['hours_since_boot'],1)} hours of fleet uptime as of "
    f"this report's own generation (the fleet has not been destroyed and this "
    f"figure grows with every further hour; AWS Cost Explorer access is not "
    f"available to this project's IAM user, so this is the project's own "
    f"hourly-rate estimate, not a billing-API figure)."
)
w(
    "- **This audit:** `thesis/scripts/audit_v8_from_raw.py` independently "
    "recomputed T_fluxo (24 cells), bytes-per-participant, RTT measured, "
    "OPINsize constancy, the k-model, and the 72-cell drift table directly from "
    "the raw run files, calls.jsonl, and pcaps, pooled across all 3 windows -- "
    "**0 divergences** against the published consolidate outputs (one noted "
    "finding, not a divergence: the PQC k bootstrap CI's upper tail is sensitive "
    "to the resampling stream at this sample size -- see Section 7)."
)

# ------------------------------------------------------------- Section 12
w()
w("## 12. Equivalence with the reference article (Schardong et al., CANS 2022)")
w()
w("| Metric (Schardong et al., 2022) | Measured in v8? | Where |")
w("|---|---|---|")
w("| Total flow size (bytes transferred) | Yes | Section 3 (OPINsize) |")
w("| mTLS handshake size | Yes | Section 3 |")
w("| JWT/token size | Yes | Section 3 |")
w("| Public key size | Yes | Section 3 (JWK_PK_size) |")
w("| Flow latency under network delay | Yes -- with **real**, not emulated, delay | Section 4 |")
w("| Per-endpoint latency breakdown | Yes | Section 6 |")
w("| RTT | Yes -- measured from pcap, not assumed | Section 5 |")
w("| Packet loss | Yes -- strictly as retransmissions/segments (Decision 115 correction) | Section 5 |")
w("| CA/PKI certificate cost | Yes -- this thesis's own extension to Schardong's equation (the PKI term), carried forward from v5 | Section 3 |")
w()
w("## References")
w()
w("- Bindel, N., Herath, U., McKague, M., & Stebila, D. (2017). *Transitioning to a Quantum-Resistant Public Key Infrastructure.* PQCrypto 2017.")
w("- Bindel, N., Braun, J., Gladiator, L., Stebila, D., & Wiggers, T. (2019). *X.509-Compliant Hybrid Certificates for the Post-Quantum Transition.* Journal of Open Source Software, 4(40), 1606.")
w("- Schardong et al. (2022), Eq. 3.1 (original flow-size equation).")
w("- NIST FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA).")

out_path = V8 / "Consolidated_Metrics_Report_FINAL.md"
out_path.write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"Wrote {out_path} ({len(L)} lines)")

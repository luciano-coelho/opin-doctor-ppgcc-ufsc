# v9 — Second real-AWS campaign (new account), Control profile, Degrau 1/Degrau 2

A second, independent real-AWS cross-region latency campaign, run on a
**new** AWS account from v8's, with a generalized orchestrator (N servers,
N routes instead of v8's fixed topology), a fourth diagnostic-only
**Control** profile, and a corrected OPINsize formula for the encrypted
`id_token`'s internal signature. See `DECISIONS.md` for the complete,
numbered engineering/statistical decision trail (217 decisions as of the
official campaign + Degrau 1/Degrau 2).

## Official campaign: complete, fleet stopped (not yet destroyed)

- **Tag:** `v9-campanha-oficial-final`
- **Commit:** `c05dcb364192bc193e99704dea2aae5a33b8ae21`
- **Any reproducibility / byte-for-byte integrity check of the frozen
  artifacts below must diff against this commit, never against the
  current branch tip** — later commits add separate, additive work
  (Degrau 1, Degrau 2, the `id_token` OPINsize correction) that does not
  change a single byte of the already-collected official data, but does
  touch some of the same tooling scripts (purely additively).

**Parameters (see `Consolidated_Metrics_Report_FINAL.md`, Section 1):**

- **4 profiles** (Classic, PQC, Hybrid, Control) x **8 real routes**, across
  **3 server installations** (`sa-east-1`, `us-east-1`, `ap-northeast-1`),
  **12 AWS hosts** total (3 servers + 8 clients + 1 control host, never a
  client or server itself) across **7 AWS regions**.
- **10 official executions + 5 discarded warm-ups per cell.**
- **Total: 320/320 official executions, 160 warm-ups, 32/32 dedicated
  captures — 0 failures.**
- **Single window:** 2026-11-15T17:37:59Z → 2026-11-16T00:06:40Z.
- **Randomization seed:** `20261107` (per-route profile order recorded in
  the manifest's own `route_orders`).

**Frozen artifacts (never to be edited, moved, or regenerated in place —
see the root README's
["frozen" verification note](../../../README.md#the-official-v9-campaign-tag-commit-and-re-verification)):**

- `campaign/PINS.json` — sha256/rootfs-layer/binary pins for the 7 Docker
  images the campaign actually ran (gateway, proxy, measure, pqc-signer,
  auth, mongo_seed, mockapi).
- `campaign_oficial_conta_nova_raw/manifest.sha256` — sha256 of the 720
  raw capture/log/data files produced by the official campaign (496 JSON,
  88 pcap, 78 keylog, 57 log, 1 jsonl). Most of these 720 files live only
  on the operator's local disk (`.gitignore`d, mainly the `.pcap`/`.keylog`
  captures) — only the manifest itself plus 3 derived summary JSONs
  (`manifest.json`, `opinsize_oficial_conta_nova.json`,
  `evaluate_criteria_oficial_resultado.json`) are committed to git.
- `campaign/scripts/*.py` and `campaign/tests/*.py` — the orchestration
  code that actually ran the official campaign. Specific file hashes are
  cited throughout `DECISIONS.md` as proof of what ran; see each
  Decision's own "Emenda" entry before assuming a script's current hash
  still matches what produced the official data.

**Fleet status:** as of the most recent decision in this campaign's log,
the 12-host fleet is **`stopped`** (via its own dead-man's-switch
mechanism), **not terminated** — the 12 Elastic IPs remain associated with
the AWS account. This is different from v8, whose fleet was fully
destroyed and verified via the real AWS API after its campaign closed (see
`results/v8/README.md`). Anyone picking this project back up should check
the fleet's current state directly against AWS before assuming it still
matches this description.

## Two aborted attempts before the official run

The official window above is the **third** launch attempt. The first two
crashed mid-run (process-level crashes, never an invalid measurement or a
data-integrity issue) and are archived, untouched, under
`thesis/results/v9_aborted_attempt_1/` and
`thesis/results/v9_aborted_attempt_2/` — see each folder's own `README.md`
and `DECISIONS.md` Decisions 138-139 for the root cause of each crash (a
per-route dead-man's-switch renewal gap, then a missing SSH-transport
retry). Neither folder's data is used in any analysis under this
directory.

## Supplementary investigations after the official campaign: "Degrau 1" and "Degrau 2"

Two pre-registered, supplementary investigations were run *after* the
official campaign above had already closed — both kept strictly separate
from the official campaign's frozen raw data (different subfolders, never
merged into `campaign_oficial_conta_nova_raw/`):

- **Degrau 1** (`analise_origem/`) — an exploratory, pre-registered
  investigation into the origin of a residual latency gap between
  profiles not fully explained by cryptographic cost alone (four
  hypotheses, H1-H4; see `analise_origem/PLANO.md` and
  `analise_origem/RELATORIO_ORIGEM.md`). Purely analytical — no new AWS
  infrastructure, no new measurement campaign.
- **Degrau 2** (`degrau2/`) — a follow-up **measurement** campaign (real
  AWS executions) adding finer-grained phase-level timing
  (`t_fluxo_fino_seconds`/`phase_accounting`) to the same orchestrator, to
  test the hypotheses Degrau 1 raised. Pre-registered in
  `degrau2/PLANO_DEGRAU2.md` (plus its Emenda 1); results in
  `degrau2/ESTADO_FINAL.md` and `degrau2/RELATORIO_ETAPA2_D1_D5.md`. A
  real serialization bug (new fields silently discarded before being
  written to disk) was found and fixed mid-investigation — the first two
  rounds, collected before the fix, are archived under
  `degrau2/campaign_data/.../` as `tentativa1_sem_campo_fino/` ("attempt 1,
  without the fine-grained field") and excluded from the final analysis;
  the corrected Round 3 (480/480 verified records) is what Degrau 2's
  conclusions are based on.

## OPINsize correction: the `id_token`'s internal signature (Decisions 216-217)

The official campaign's first-published OPINsize numbers (and v8's,
inherited from the same formula) counted the encrypted `id_token`'s JWE
structure but not the signature bytes *inside* it. This was corrected,
after a live local measurement (never against the AWS fleet) confirmed
the real per-profile values, and the consolidated report was regenerated
by script from the **same already-collected raw data** — nothing in
`campaign_oficial_conta_nova_raw/` or `PINS.json` changed; only two
analysis/report-generation scripts and the two already-regenerable report
files were updated. Current official OPINsize values (see
`Consolidated_Metrics_Report_FINAL.md`, Section 2.1): Classic 34,584.00
bytes (1.00x), PQC 263,048 bytes (7.61x), Hybrid 293,332.00 bytes (8.48x);
Control (diagnostic, reported separately, never mixed into the
Classic/PQC/Hybrid comparison) 249,138 bytes (7.20x).

## Directory map

| Path | What it is |
|---|---|
| `DECISIONS.md` | The full, numbered decision/incident/audit log for this campaign (217+ entries) |
| `Consolidated_Metrics_Report_FINAL.md` | The official results report, regenerated by script from the raw data |
| `campaign/` | Orchestration code, tests, and `PINS.json` that ran the official campaign |
| `campaign_oficial_conta_nova_raw/` | The official campaign's frozen manifest + 3 derived summary JSONs (raw captures live locally, `.gitignore`d) |
| `campaign_oficial_conta_nova_host_facts.md` | Read-only pre-teardown audit of all 12 hosts (AMI, kernel, Docker, TCP sysctls, clock sync) |
| `terraform/`, `terraform_campanha_oficial/` | Infrastructure-as-code for the campaign's AWS fleet |
| `integration/` | The Go/Node source (gateway, proxy, measure harness, pqc-signer, interop/negative tests) built into the pinned Docker images |
| `v9_aborted_attempt_1/`, `v9_aborted_attempt_2/` *(siblings of this folder, under `thesis/results/`)* | The two crashed launch attempts before the official run |
| `analise_origem/` | Degrau 1 (exploratory, analysis-only) |
| `degrau2/` | Degrau 2 (follow-up measurement campaign) |
| `opinsize_correction_id_token/` | The local measurement behind the Decisions 216-217 OPINsize correction |

## Tags (local; check `git ls-remote --tags origin` before assuming any tag is published)

`v9-prereg`, `v9-ferramentas-congeladas`,
`v9-campanha-conta-nova-piloto-assimetrico` (`-v2`..`-v4`),
`v9-campanha-oficial-congelada` (`-v2`..`-v9`), **`v9-campanha-oficial-final`**
(the official campaign, see above), `v9-relatorio-consolidado-final`
(`-rev2`, `-rev3`), `v9-degrau2-pre`, `v9-degrau2-final`.

# PILOT_RUNBOOK.md — Phase B, real pilot (60 executions, 4 profiles × 3 routes × N=5)

## Official campaign, new account (Decision 176) — real inventory and open gap

**This block describes the AWS account/infrastructure of the current
official campaign (12 instances, 7 regions, apply completed in
Decisions 174/175) — the Step 0-15 script below, including the "60
executions/5 instances/3 regions" numbers in the title, describes the
SMALLER infrastructure of an earlier pilot round and remains as a
historical reference for procedure, not as this account's topology.**

This account's real topology (source: `campaign_topology.py`,
confirmed against a filtered `terraform output` — never `-json`
unscoped, see Decision 176 on the key-exposure incident):

| Host (Terraform address) | Role | Region | Route(s) served |
|---|---|---|---|
| `module.control` | control | sa-east-1 | — |
| `module.server_sa_east_1` | server | sa-east-1 | L0-sa-east-1, L123, L219, L325 |
| `module.client_l0_sa_east_1` | client | sa-east-1 (co-located) | L0-sa-east-1 |
| `module.client_ca_central_1_a` | client | ca-central-1 | L123 |
| `module.client_eu_north_1` | client | eu-north-1 | L219 |
| `module.client_ap_southeast_1` | client | ap-southeast-1 | L325 |
| `module.server_us_east_1` | server | us-east-1 | L0-us-east-1, **L14** |
| `module.client_l0_us_east_1` | client | us-east-1 (co-located) | L0-us-east-1 |
| `module.client_ca_central_1_b` | client | ca-central-1 | **L14** |
| `module.server_ap_northeast_1` | server | ap-northeast-1 | L0-ap-northeast-1, L30 |
| `module.client_l0_ap_northeast_1` | client | ap-northeast-1 (co-located) | L0-ap-northeast-1 |
| `module.client_ap_northeast_2` | client | ap-northeast-2 | L30 |

12 hosts, 7 regions, 8 routes (`campaign_topology.CAMPAIGN_ROUTES`) —
confirmed identical to this account's actual `main.tf`. `L0-sa-east-1`
and `L14` (the two used by the pilot requested in this round) are
served by `server_sa_east_1`+`client_l0_sa_east_1` and by
`server_us_east_1`+`client_ca_central_1_b`, respectively — an
unambiguous mapping, confirmed in `main.tf`'s own comments
(`client_ca_central_1_a`/`_b` are distinct instances, never the same
machine).

**Real gap found (blocks automatic execution of the 18-execution
pilot requested — reported, not fixed, per this round's explicit
instruction):** `orchestrator.py` only has TWO route-selection modes
via the CLI:
1. Without `--campaign`: uses the global `PROFILES`/`ROUTES`
   (`orchestrator.py:220-221`), hardcoded for a 3-route pilot from an
   EARLIER campaign (`["L0", "L219", "L325"]`) — names that don't even
   exist in this account (here the L0 route is `L0-sa-east-1`/
   `L0-us-east-1`/`L0-ap-northeast-1`, one per server, never just
   `"L0"`).
2. With `--campaign`: uses `campaign_topology.CAMPAIGN_ROUTES` (this
   account's 8 real routes, confirmed in the table above) — but runs
   ALL 8 routes × ALL 4 profiles (`campaign_profiles =
   list(PROFILES)`, `orchestrator.py:2709`), never a subset. This is
   the FULL CAMPAIGN, explicitly out of this round's authorized scope
   ("do NOT start the full campaign").

There is today no CLI path to run exactly "4 profiles on
L0-sa-east-1 + classico/hibrido-and on L14, 3 executions each" (18
executions, asymmetric per route) without: (a) editing
`orchestrator.py` (out of authorized scope — "do NOT change
measurement, criteria, orchestration, or delivery scripts"), or (b)
actually running `--campaign` (the full campaign, 8 routes × 4
profiles, also out of scope). **This is why this round stops before
delivery/pilot — see Decision 176.**

---

# PILOT_RUNBOOK.md — Phase B, real pilot (60 executions, 4 profiles × 3 routes × N=5)

**[Historical procedure below, Decision 79 — describes the SMALLER
infrastructure (5 instances, 3 regions) of a pilot round that
preceded this new account. Kept as a reference for level of
detail/script convention, not as a valid procedure for this
campaign's 12 hosts.]**

Luciano's decision, item 4 (DECISIONS.md, Decision 79): "write
Phase B's PILOT_RUNBOOK.md... at the same level of detail as
INFRA_REHEARSAL.md, and follow it." The same machine/command
convention as that script — repeated here, never redefined:

| Convention | Meaning |
|---|---|
| **[OPERATOR]** | Runs on Luciano's laptop. Only reaches CONTROL directly (`ssh_ingress_cidrs = {"operator": var.operator_ip_cidr}`) — never the server/clients directly. |
| **[CONTROL]** | Runs FROM INSIDE the `control` instance (via `ssh $CONTROL_IP "<command>"` triggered by the operator). Only the control host reaches the server/clients (their `ssh_ingress_cidrs` only lists `{"control": "${module.control.public_ip}/32"}`). |

**`self_terminate_hours=4`** (vs. 1h for the infrastructure rehearsal)
— the real pilot has 60 executions + 12 dedicated captures + 3
delivery steps, a larger window than the pure infrastructure
rehearsal.

**The operator-IP pre-check (Decision 77, `check_operator_ip.py`)
runs BEFORE ANY phase of this script that depends on SSH working** —
never just once in Step 0. Repeat Step 1's command before each block
marked 🔁 below.

**Gap closed (Decision 85):** criteria 2 (initcwnd), 3 (zero errors
on the most distant route), and 7 (latency sanity) now actually run
against the real pilot — `dedicated_criteria.py` (new, delivered to
the control host) wires the 3 producers (`thesis/results/v9/
integration/producers/{criterio2_probe,criterio3_collector,
criterio7_rtt}.py`) into the pipeline: a NEW ingress port (9876,
Decision 85, same scope as `gateway_ingress_cidrs`) for criterion 2;
an adapter that reuses `evaluate_criteria.criterion_4_counts` (never
reimplemented) for criterion 3; both producers fixed to run `tshark`
via `docker run ... mockopin-v9-measure` (the real server never has
`tshark` on the host's PATH) for criterion 7. **This script now
actually closes all 7 criteria — no "no evidence" expected by
design.**

---

## Step 0 — prerequisites **[OPERATOR]**

```
export TF_VAR_operator_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
cd thesis/results/v9/terraform
terraform init
```
**Expected output:** `Terraform has been successfully initialized!`
**Abort criterion:** any init/provider error.

---

## Step 1 — operator-IP pre-check (Decision 77) **[OPERATOR]** 🔁

```
python ../campaign/scripts/check_operator_ip.py --tf-dir .
```
**Expected output (fleet does not exist yet, 1st time):** `{"ok": false, "error": "... recurso ... nao encontrado no state ..."}` — **expected and harmless** before the first apply (Step 2); the rule only exists after it. After Step 2, repeat this command — from then on the expected output is `{"ok": true, "changed": false, ...}` (or `"changed": true` with the new IP, if it changed).
**Abort criterion:** after Step 2 exists, any `"ok": false` with a `terraform apply` failure message — never proceed to any step with SSH without resolving this first (see the Decision 72/77 infrastructure note — a real 8-minute lockout already cost an entire fleet).

---

## Step 2 — `terraform plan`, then `terraform apply` (`self_terminate_hours=4`) **[OPERATOR]**

Same infrastructure as the infrastructure rehearsal, PLUS 3 new rules
(Decision 85 — the criterion-2 producer's dedicated port):

| Resource | Quantity |
|---|---|
| `tls_private_key.campaign` | 1 |
| `aws_key_pair` | 4 |
| `aws_security_group.this` | 5 |
| `aws_vpc_security_group_ingress_rule.ssh` | 5 |
| `aws_vpc_security_group_ingress_rule.gateway` | 3 |
| `aws_vpc_security_group_ingress_rule.criterio2_probe` | 3 |
| `aws_instance.this` | 5 |
| `aws_eip.this` | 5 |
| **Total** | **31** |

```
export TF_VAR_operator_ip_cidr="$(curl -s https://checkip.amazonaws.com)/32"
terraform plan -var="self_terminate_hours=4"
```
**Expected output:** `Plan: 31 to add, 0 to change, 0 to destroy.` — if it diverges, **stop and reconcile before applying**.

```
terraform apply -var="self_terminate_hours=4" -auto-approve
```
**Expected output:** `Apply complete! Resources: 31 added, 0 changed, 0 destroyed.`
**Abort criterion:** any apply error, or N ≠ 31 without explanation — run `terraform destroy -auto-approve` immediately.

Repeat Step 1 now (the ingress rule already exists).

---

## Step 3 — confirm instances + generate `/tmp/inventory.json` **[OPERATOR]**

```
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 \
  --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" \
  --query "Reservations[].Instances[].State.Name"
```
(repeat for `eu-north-1`/`ap-southeast-1`)
**Expected output:** `"running"` across the 3 regions (5 instances total).
**Abort criterion:** any instance outside `running`/`pending` for more than 2 minutes.

Generate `/tmp/inventory.json` (`terraform output -json inventory`), check the actual format against what `deliver_source.py`/`pki_relay.py`/`orchestrator.py` read (same procedure as Step 2 of `INFRA_REHEARSAL.md`).

---

## Step 4 — deliver the campaign's SSH key to the control host **[OPERATOR → CONTROL]**

```
terraform -chdir=../../terraform output -raw campaign_private_key | \
  python pki_relay.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --deliver-campaign-key --inventory-json /tmp/inventory.json
```
**Expected output:** JSON with `"campaign_key_remote_path": "/home/ec2-user/.ssh/campaign_key"`.
**Abort criterion:** any `RuntimeError`.
**Never printed:** the key's content.

---

## Step 5 — Docker ready across the 5 instances **[CONTROL/OPERATOR]**

Same fail-closed loop as Step 4 of `INFRA_REHEARSAL.md` (direct SSH from the control host to each host, relayed via the campaign key, `FAILED=""`/`exit 1` if one never becomes ready).
**Expected output:** `"Docker pronto: <IP>"` for the 5 instances.
**Abort criterion:** exit code ≠ 0 — the message already states which host failed.

---

## Step 6 — `deliver_source.py`: source code and certificates **[OPERATOR → CONTROL → server/clients]** 🔁

```
python deliver_source.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --inventory-json /tmp/inventory.json
```
**Expected output:** a report per destination (`server`, `L0`, `L219`, `L325`) — `files` lists `COMMON_FILES` (all) + `certs/generated` (clients only) + `"requirements_installed": true"` (clients only, Decision 71).
**Abort criterion:** any `RuntimeError`.

---

## Step 7 — `deliver_source.py --to-control`: `orchestrator.py` and dependencies **[OPERATOR → CONTROL]**

**What is now copied to the control host** (`CONTROL_FILES`, Decisions 76/85 add the last items in this list):
- `campaign/scripts/{orchestrator,cli,preflight}.py`, `rehearsal_handshake.sh`
- `campaign/scripts/{dedicated_criteria,deliver_images}.py` (Decision 85 — `orchestrator.py` now imports `deliver_images` for `BACKEND_IMAGE_KEYS`; `dedicated_criteria.py` runs from the control host, same convention)
- `campaign/PINS.json`, `integration/evaluate_criteria.py`
- `v8/campaign/scripts/redact_aws_errors.py`
- **`thesis/results/v9/certs/generated`** (Decision 76 — the smoke gate's bytes diagnostic, Step 10, reads this from the control host; without this, before this Decision, it broke with `FileNotFoundError` — now, even if missing, it would only pause the diagnostic, never the official gate)
- `inventory.json` (copied separately)

```
python deliver_source.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --to-control --inventory-json /tmp/inventory.json
```
**Expected output:** `{"target": "control", "ip": "...", "files": [...]}` including `thesis/results/v9/certs/generated`.
**Abort criterion:** any `RuntimeError`. Never talks to the server/client.

---

## Step 8 — `deliver_images.py`: the 4 pinned images (gateway/proxy/pqc-signer/measure) **[OPERATOR → CONTROL]**

```
python deliver_images.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador>
```
**Expected output:** JSON with `disk_check`, `images` (4 entries, `sha256_ok: true`), `gateway_binary_info_delivered: true`.
**Abort criterion:** any `RuntimeError`.

**Not delivered here, on purpose (Decision 57):** `mockopin-v9-negtest` — not used by the real pilot (only by the `rehearsal_handshake.sh` rehearsal), never needed in this script.

## Step 8b — `deliver_images.py --images`: the 3 business-backend images (Decision 83) **[OPERATOR → CONTROL]**

**Real finding (Decision 91, while running this script again):** the
default for `--images` in `deliver_images.py` is `ALL_IMAGE_KEYS`
(gateway/proxy/pqc-signer/measure — a misleading name, it never
included the backend), never `BACKEND_IMAGE_KEYS` (auth/mongo_seed/
mockapi, Decision 83/87) — Step 8 alone NEVER delivers the backend.
Without this step, `start_block` (already called in Step 10) breaks
with `RuntimeError: _deliver_image(auth, ...): .../auth.tar nao
encontrado no controle`.

```
python deliver_images.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --images auth mongo_seed mockapi
```
**Expected output:** JSON with `disk_check`, `images` (3 entries — auth/mongo_seed/mockapi, `sha256_ok: true`).
**Abort criterion:** any `RuntimeError`.

---

## Step 9 — check `python3`/the real pipeline's dependencies on the control host **[CONTROL]**

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 --version
python3 orchestrator.py --help >/dev/null && echo "OK: orchestrator.py importa e roda"
python3 launch_persistent.py --help >/dev/null && echo "OK: launch_persistent.py importa e roda"
REMOTE
```
**Expected output:** the Python 3 version, then `OK: orchestrator.py importa e roda`, then `OK: launch_persistent.py importa e roda`.
**Note (Decision 76):** `evaluate_criteria.py` no longer depends on `cryptography` for the bytes diagnostic (replaced by `ssl.PEM_cert_to_DER_cert`, stdlib) — no third-party package is needed for this step.
**Abort criterion:** any import traceback, or `python3` missing.

---

## Step 10 — smoke gate: capture preflight + 12 executions (Decision 48/53/55/76) **[CONTROL]** 🔁

**Decision 172 (Luciano's request, item 4b of Decision 171): this
step NEVER AGAIN runs `orchestrator.py` directly in a blocking SSH
session** — an operator internet outage during the window used to
kill the real execution midway. From this Decision on, every
`orchestrator.py` launch (smoke or pilot) goes through
`launch_persistent.py` (delivered to the control host in Step 7,
the same `CONTROL_FILES` as `deliver_source.py`): `start` decouples
the process from the SSH session (`setsid`/new session group +
exclusive lock + PID + file log) and returns within seconds — the SSH
session can drop afterward without affecting the window in progress.

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
mkdir -p ~/campaign-data/v9/smoke
python3 launch_persistent.py --name smoke start -- \
  --mode ssh --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --images-staging-dir ~/images --smoke --out ~/campaign-data/v9/smoke
REMOTE
```
**Expected output of this command (immediate, never the end of the window):**
`{"started": true, "pid": <N>, "log": "..."}`. If `"started": false`
(`"already_running"`/`"lock_busy"`), a window with the same `--name`
is already running — never a second instance in parallel.

**Monitoring (repeat as many times as you like, including from a
BRAND-NEW SSH session — it never needs to be the one that launched
it):**
```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" \
  "cd ~/thesis/results/v9/campaign/scripts && python3 launch_persistent.py --name smoke status"
```
`"alive": false` + `"progress": {"source": "manifest.json", "complete": true, ...}` = actually finished. `"alive": true` + `"progress": {"source": "manifest_partial.json", ...}` = still running, real progress (never fabricated) read from the same incremental file that `orchestrator.py` already writes per cell (Decision 133). `python3 launch_persistent.py --name smoke tail -n 50` shows the real log's last lines.

**What runs, in order, automatically, within ONE call**
(`run_smoke_gate`, never separate steps): (1) `capture_ready_
check()` — aborts BEFORE any execution if tcpdump/sudo/image/
interface is missing; (2) 12 executions (1 per profile × route,
never counting toward the 60 official ones); (3) 4 mechanism-proof
captures (`smoke_capture_proof/`, never confused with the 12
official criterion-1 ones); (4) per-profile bytes diagnostic
(Decision 76 — it NEVER breaks the gate anymore; any deviation or
exception only flags `bytes_diagnostic_needs_decision`, pauses, never
brings down `smoke_ok`).

**Expected output (inside `manifest.json`, via `status`):** JSON with
`"smoke_ok": true`, `"capture_preflight": {"go": true, ...}`,
`"capture_proof_ok": true`, `"total_execucoes": 12`.
`"bytes_diagnostic_needs_decision"` may come back `true` or `false`
— **never**, on its own, a reason to abort (it is a diagnostic,
never the official gate).
**Abort criterion:** `"smoke_ok": false` inside the manifest (the
process always exits on its own, never destroying anything
automatically, Decision 49/Amendment 12). Luciano's decision: fix and
repeat within the 4h window, or order a destroy (Step 14). If the
reason is a pre-registered criterion failing with code already
verified correct — rule 7(a) of this authorization, STOP.

---

## Step 11 — real pilot: 60 executions + 12 dedicated captures **[CONTROL]** 🔁

**Same change as Step 10 (Decision 172) — a launcher, never a direct
blocking SSH session:**

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
mkdir -p ~/campaign-data/v9/piloto
python3 launch_persistent.py --name piloto start -- \
  --mode ssh --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --images-staging-dir ~/images --out ~/campaign-data/v9/piloto
REMOTE
```
**Monitoring:** `python3 launch_persistent.py --name piloto status`/`tail -n 50`, from any SSH session, at any time — see Step 10. **NEW criterion (n), real persistence test (Decision 172):** with the pilot in progress, the operator deliberately drops their own SSH session ONCE (e.g., closes the terminal/loses the connection mid-window); the pilot MUST continue and finish on its own — confirm with `status` from a BRAND-NEW SSH session that the window kept progressing and finished complete. The campaign report records that this test was performed and its result.

**Expected output (via `status`, after `"alive": false`):** JSON with `"total_execucoes": 60`, `"expected_total": 60`, `"total_capturas": 12`, `"smoke": false` — `manifest.json`/`piloto_combined.log`/`piloto_calls.json`/`criterio6_execucoes.json`/`criterio1_capturas/*.log` (12 files) written to `~/campaign-data/v9/piloto/` (FLAT output, Decision 75/78 — never split by profile). **Capture-robustness amendment (item 0+3, Luciano's request):** `criterio1_capturas/capturas_brutas/` gains the RAW pcap+keylog from EVERY attempt of each of the 12 dedicated captures (success or failure, up to 3 attempts each — retry only when the failure mode is incomplete decryption, never a size mismatch); the winning attempt of each capture also lands in `criterio1_capturas/{perfil}_{rota}.pcap`/`.keylog` (no attempt suffix).
**Abort criterion:** any exception/`RuntimeError` (start_block, run_execution, dedicated_capture), visible in the log (`tail`) and reflected in `"alive": false` with no complete `manifest.json` (only `manifest_partial.json`, `"complete": false`) — including "incomplete decryption after 3 attempts" (the 3 attempts remain preserved in `capturas_brutas/` regardless, never lost) — no code fix mid-window without recording a numbered Decision; if the fix changes what is measured, rule 7(e), STOP. **Never relaunch with `--resume` assuming the partial data counts** — the fail-closed policy already present in `orchestrator.py` (never altered by this launcher) always redoes the entire window from scratch when `manifest.json` does not exist; it only skips re-execution if `manifest.json` already exists COMPLETE and identical.

**End of campaign (only on the user's explicit order, AFTER the
results have been copied out of the control host — Step 12/13):
remove the campaign's private key from the control host with
`python3 cleanup_campaign_key.py --key-path ~/.ssh/campaign_key`
(Decision 172) — confirms the file is gone, never runs automatically
at any other point in this script.**

---

## Step 11.5 — dedicated producers for criteria 2/3/7 (Decision 85) **[CONTROL]**

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 dedicated_criteria.py --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --dir ~/campaign-data/v9/piloto
REMOTE
```
**What runs, in order:** criterion 3 (local, reuses
`evaluate_criteria.criterion_4_counts` already written by Step 11,
filters L325) → criterion 2 (starts `criterio2_probe.py` on the
server, triggers 1 test connection from the L219 client via
`/dev/tcp`, port 9876 — effective-MSS amendment, item 2: `mss_bytes`
only exists when `ss -ti` and the actual largest pcap payload agree,
never the MSS announced in the SYN-ACK) → criterion 7 (per route:
`probe` from the client against 443, `pcap` on the server reusing
the dedicated pcaps that Step 11 already wrote to `/tmp` — RTT-pcap
amendment, item 1: measures SYN-ACK going out → ACK closing the
handshake coming back, never SYN arriving → SYN-ACK going out) →
`collect_full_logs` (item 0, new fail-closed rule: FULL log, with no
time window, of the server's 4 containers — gateway/auth/mongo_seed/
mockapi — + a light diagnostic of each instance). Writes
`criterio2_initcwnd.json`/`criterio2_probe.pcap`/
`criterio3_l325_execucoes.json`/`criterio7_rtt_por_rota.json`/
`full_container_logs/` into the SAME `~/campaign-data/v9/
piloto/` directory — a single pull in Step 12 brings everything
together.
**Expected output:** JSON with the 4 keys (`criterio2`/`criterio3`/
`criterio7`/`full_logs`), none empty.
**Abort criterion:** any `RuntimeError` — never proceed to Step 12
with one of the 3 files missing (the consolidation would silently
report "no evidence", without saying the cause was this step
failing).

---

## Step 12 — collection with verified manifest (Decision 78) **[OPERATOR → CONTROL]**

```
python collect_artifacts.py --control-ip "$CONTROL_IP" --key <chave-do-operador> \
  --remote-dir ~/campaign-data/v9/piloto --local-dir /tmp/v9_piloto_coletado
```
**Expected output:** JSON with `"files_verified": N` (N = every file in the directory — now including, in addition to what already existed, the RAW pcaps/keylogs from every capture attempt in `criterio1_capturas/capturas_brutas/` + the winners in `criterio1_capturas/*.pcap`/`*.keylog`, `criterio2_probe.pcap`, and `full_container_logs/*.log` — item 0, new fail-closed rule), `.pull-verified` written to `/tmp/v9_piloto_coletado/`. **This `.pull-verified` is the marker that Step 14 now REQUIRES** (`--pull-verified-marker`) before any teardown — never again `--force` as the main path.
**Abort criterion:** any `RuntimeError` ("nao bate"/"ausente") — never trust a partial/corrupted copy.

---

## Step 13 — final consolidation (Decision 79) **[OPERATOR]**

```
python consolidate_v9_pilot.py \
  --collected-dir /tmp/v9_piloto_coletado \
  --out-dir ../../piloto/dados_oficiais/piloto-real-aws-<data-utc> \
  --run-label piloto-real-aws-<data-utc>
```
**Expected output:** `RELATORIO_PILOTO.md` + `criteria_evaluation.json` + `raw/` written to `thesis/results/v9/piloto/dados_oficiais/piloto-real-aws-<date>/`. **Expected, by design, in this round (Decision 85 closed the gap):** all 7 criteria actually evaluated against REAL AWS data for the first time in this package's history (a real PASS or FAIL per criterion, never assumed, never "no evidence"). `"all_criteria_pass"` reflects the real result — `true` is not always expected (a criterion may genuinely fail), but none should fail due to a MISSING FILE.
**Abort criterion:** none — it is read-only/consolidation, it never touches the fleet. If any of the 7 fails due to "file not found" (instead of a real FAIL with data), go back to Step 11.5 — something did not run.

---

## Step 14 — teardown **[OPERATOR]**

**Fail-closed amendment (item 0, Luciano's request):** until this
round, the main command used `--force`, which NEVER actually
exercised the gate that already existed in code (`.pull-verified`) —
a real finding, fixed here. Sequence: `emergency_stop.py` dry mode
(diagnostic) → `cleanup.py --tf-dir ../../terraform --profile
mockopin-pqc --release-eips --pull-verified-marker
/tmp/v9_piloto_coletado/.pull-verified` (main — blocks with a
`RuntimeError` if Step 12 did not run/verify the raw files,
`all_clean: true` expected) → `emergency_stop.py --execute`
(fallback, only if `all_clean: false`).

**`--force --reason "<reason>"` is only acceptable under the rule-7
exceptions** (a cost or safety limit reached mid-pilot, with evidence
not yet collected) — `--force` without `--reason` now fails loudly
(`cleanup.py` requires the reason, never a silent bypass). Used this
way, the final report must explicitly state what was lost (which raw
files were never verified).

---

## Step 15 — final verification: nothing left in the account **[OPERATOR]**

The same 12 calls from Step 14 of `INFRA_REHEARSAL.md` (`describe-instances`/`describe-addresses`/`describe-security-groups`/`describe-key-pairs`, 3 regions × 4 calls), independent of the `all_clean` self-reported by `cleanup.py`.
**Expected output:** all 12 calls return **empty** lists.
**Abort/alert criterion:** any resource still present.

---

## Estimated pilot cost

5 instances (4× `m7i-flex.large` + 1× `t4g.micro`) + 5 EIPs, a 4h
self-shutdown target window, but the real execution (apply → 60
executions → collection → cleanup) should take much less than that —
an expected order of magnitude, by analogy to the infrastructure
rehearsal (~35 min for its Steps 0-10) plus the time for the 60 real
executions/12 captures (never measured yet, no complete real
execution so far): estimate of 1-2h of fleet time.
- Compute: (4 × US$0,0958 + US$0,0084) × (1.5)h ≈ US$0,59
- EIP: 5 × US$0,005 × 1.5h ≈ US$0,04
- **Estimated total: ≈ US$0,6-1,2**, within this authorization's US$5 ceiling, added to what was already spent in Phase A (~US$0,55).

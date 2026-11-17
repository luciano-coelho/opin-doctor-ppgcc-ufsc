# Infrastructure rehearsal — ~35 minutes, no experiment

**Decision 68 (real finding, real execution): Image ID is NEVER
checked anywhere in this script anymore** — `docker image inspect
.Id` diverges between different Docker versions (operator vs.
the real instance), even with identical content, found live in
Decision 67 and reproduced locally with `docker:25-dind`. The
identity of each image is now `tar_sha256` (Step 7, before any
scp) + `RootFS.Layers`/`.Config`/binary inside the container
(Step 9, 2nd hop) — Image ID is still read, only as an
informational field in reports.

Decision 60 (correction to the Decision 59 script — 5 requested
adjustments + 1 additional finding of the same class, found while
fixing item 2): `inventory.json` generation moved earlier and
verified against the actual format the scripts read; the server
address in the handshake read from the inventory (never typed in —
L0 is co-located and dials the PRIVATE IP, not the EIP); the "Docker
ready" loop now fails loudly with the host in the error; the image
delivery (2nd hop) now reports time and identity per host, with an
abort criterion for slowness; a new step before the remote exercise,
confirming that `orchestrator.py` actually imports on the control
host. **Each step below explicitly states ON WHICH MACHINE it
runs** — "OPERATOR" (Luciano's laptop) or "CONTROL" (the `control`
instance, the only one that reaches the server/clients). No address
in this script is typed by hand — all come from
`/tmp/inventory.json` (operator) or its local copy on the control
host (`inventory.json`, delivered in Step 6).

Uses the SAME credentials and the SAME AWS CLI profile already
used in v8 (`mockopin-pqc`). Objective: to prove real `terraform
apply`/`destroy`, the complete delivery of the remote path in 2
hops (operator → control → host, never operator → host directly),
`orchestrator.py` ACTUALLY running from the control host, a real
handshake per profile triggered from the control host to the SAME
address that the real route dials, and the emergency stop — never an
experiment execution (none of the 60 official executions, none of
the 12 criterion-1 captures).

**Target duration: ~35 minutes of measured window, strictly
linear order (0→14, each step depends only on the previous one).**
`self_terminate_hours` reduced to **1h** just for the rehearsal
(a safety net — never intended to actually take that long; steps
11-14 are the real teardown, mandatory even if the rehearsal
finishes before the self-shutdown).

| Convention | Meaning |
|---|---|
| **[OPERATOR]** | Runs on Luciano's laptop. Can only SSH/SCP directly into CONTROL (`ssh_ingress_cidrs = {"operator": var.operator_ip_cidr}`) — never into the server/clients. |
| **[CONTROL]** | Runs FROM INSIDE the `control` instance (via `ssh $CONTROL_IP "<command>"` triggered by the operator). Reaches the server/clients because their `ssh_ingress_cidrs` only lists `{"control": "${module.control.public_ip}/32"}`. |

---

## Step 0 — prerequisites **[OPERATOR]**

```
export TF_VAR_operator_ip_cidr="$(curl -s https://checkip.amazonaws.com)/32"
export TF_VAR_operator_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
cd thesis/results/v9/terraform
terraform init
```
**Expected output:** `Terraform has been successfully initialized!`
**Abort criterion:** any init/provider error.

---

## Step 1 — `terraform plan`, then `terraform apply` (`self_terminate_hours=1`) **[OPERATOR]**

**Resource count, derived by reading `main.tf`/`modules/campaign_instance/main.tf`
directly (never assumed) — confirm the actual `terraform plan` against
this:**

| Resource | Quantity | Where |
|---|---|---|
| `tls_private_key.campaign` | 1 | `main.tf` |
| `aws_key_pair` | 4 | 3 regional (`campaign_sa_east_1`/`eu_north_1`/`ap_southeast_1`) + 1 for the operator |
| `aws_security_group.this` | 5 | 1 per module (`control`, `client_l0`, `client_eu_north_1`, `client_ap_southeast_1`, `server_sa_east_1`) |
| `aws_vpc_security_group_ingress_rule.ssh` | 5 | 1 per module (each has exactly 1 entry in `ssh_ingress_cidrs`) |
| `aws_vpc_security_group_ingress_rule.gateway` | 3 | only `server_sa_east_1` (`role=="server"`) — 1 entry per client (L0/L219/L325) |
| `aws_instance.this` | 5 | 1 per module |
| `aws_eip.this` | 5 | 1 per module |
| **Total** | **28** | |

```
terraform plan -var="self_terminate_hours=1"
```
**Expected output:** `Plan: 28 to add, 0 to change, 0 to destroy.` — if the actual number diverges from 28, **stop and reconcile before applying**.

```
terraform apply -var="self_terminate_hours=1" -auto-approve
```
**Expected output:** `Apply complete! Resources: 28 added, 0 changed, 0 destroyed.`
**Abort criterion:** any apply error, or N ≠ 28 without explanation — run `terraform destroy -auto-approve` immediately, stop the rehearsal.

**Check against `ssh_ingress_cidrs`/`gateway_ingress_cidrs` (main.tf), for the rest of this script:**

| Resource | SSH (22) accepted from | Gateway (443) accepted from |
|---|---|---|
| `control` | `var.operator_ip_cidr` (the OPERATOR) | n/a |
| `server_sa_east_1` | `module.control.public_ip` (ONLY the control host) | `client_l0` (private IP), `client_eu_north_1`/`client_ap_southeast_1` (public IP) |
| `client_l0`/`client_eu_north_1`/`client_ap_southeast_1` | `module.control.public_ip` (ONLY the control host) | n/a (they dial out, they don't receive) |

**No row in this table lists the operator as an SSH source to the
server or to any client** — every step below that talks to the
server/client must run **[CONTROL]**, never **[OPERATOR]**.

---

## Step 2 — confirm instances + generate and verify `/tmp/inventory.json` **[OPERATOR]**

```
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 \
  --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" \
  --query "Reservations[].Instances[].State.Name"
```
(repeat for `eu-north-1`/`ap-southeast-1`, 1 instance each — 5 total)
**Expected output:** each `describe-instances` returns `"running"`.
**Abort criterion:** any instance outside `running`/`pending` for more than 2 minutes.

**Generate `/tmp/inventory.json` NOW (not only in Step 5 — every
subsequent step that needs an address reads from here, never typed
by hand) and check the format against what `deliver_source.py`/
`pki_relay.py`/`orchestrator.py` actually read** (`inventory["server"]["public_ip"
/"private_ip"]`, `inventory["clients"][route]["public_ip"/"private_ip"
/"colocated"]`, `inventory["control"]["public_ip"]` — confirmed by
reading the 3 files: all of them expect the dict ALREADY UNWRAPPED,
which is why the `"value"` extraction below is needed — `terraform
output -json <name>`, for a NAMED output, always wraps it in
`{"sensitive":..., "value":...}`):
```
cd ../../terraform
terraform output -json inventory | python3 -c "
import json, sys
raw = json.load(sys.stdin)
inv = raw['value'] if 'value' in raw else raw
assert 'server' in inv and 'clients' in inv and 'control' in inv, f'formato inesperado: {list(inv.keys())}'
assert all(k in inv['clients'] for k in ('L0', 'L219', 'L325')), f'rotas inesperadas: {list(inv[\"clients\"].keys())}'
json.dump(inv, open('/tmp/inventory.json', 'w'), indent=2)
print('formato OK -- server/clients/control presentes, salvo em /tmp/inventory.json')
"
cd ../campaign/scripts
```
**Expected output:** `formato OK -- server/clients/control presentes, salvo em /tmp/inventory.json`.
**Abort criterion:** any `AssertionError` — the actual format diverged from what the scripts expect, investigate BEFORE using the file in any subsequent step.

**Variables used in the rest of this script — ALWAYS read from
`/tmp/inventory.json`, never typed by hand:**
```
CONTROL_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['control']['public_ip'])")
SERVER_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['server']['public_ip'])")
L0_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['clients']['L0']['public_ip'])")
L219_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['clients']['L219']['public_ip'])")
L325_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['clients']['L325']['public_ip'])")
```

---

## Step 3 — deliver the campaign's SSH key to the control host **[OPERATOR → CONTROL]**

**Why this step exists:** `pki_relay.py`/`deliver_source.py`
(second hop)/`orchestrator.py` (running from the control host) ALL
assume `~/.ssh/campaign_key` is already present on the control host —
**no script in this package ever delivered it** (the key is a
sensitive Terraform `output`, never written to a file by Terraform
itself). The same real pattern from v8 (`campaign_up.sh`). Without
this step, **no** step below that talks to the server/client works.

```
terraform -chdir=../../terraform output -raw campaign_private_key | \
  python pki_relay.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --deliver-campaign-key --inventory-json /tmp/inventory.json
```
(`--inventory-json` is required by argparse but never read in this mode — pass the actual file already generated in Step 2 instead of an empty placeholder.)

**Expected output:** JSON with `"campaign_key_remote_path": "/home/ec2-user/.ssh/campaign_key"`.
**Abort criterion:** any `RuntimeError`.
**Never printed:** the key's content never appears in any output of this script (`test_deliver_campaign_key_um_so_salto_nunca_imprime_o_conteudo`).

---

## Step 4 — Docker ready + port, across the 5 instances **[CONTROL for server/clients; OPERATOR only for the control host]**

**Control:**
```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" "docker info >/dev/null 2>&1 && echo 'Docker pronto (controle)'"
```

**Server/clients — via relay, using the campaign key (Step 3).
Correction in this round: the loop now FAILS LOUDLY (exit code ≠ 0,
message with the host(s) that did not become ready) instead of just
silently moving on if one never becomes ready:**
```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s "$SERVER_IP" "$L0_IP" "$L219_IP" "$L325_IP" <<'REMOTE'
FAILED=""
for IP in "$1" "$2" "$3" "$4"; do
  READY=0
  for i in $(seq 1 20); do
    ssh -i ~/.ssh/campaign_key -o StrictHostKeyChecking=no ec2-user@"$IP" "docker info >/dev/null 2>&1" && { echo "Docker pronto: $IP"; READY=1; break; }
    sleep 3
  done
  [ "$READY" -eq 1 ] || FAILED="$FAILED $IP"
done
if [ -n "$FAILED" ]; then
  echo "FALHA: Docker nao ficou pronto nos hosts:$FAILED" >&2
  exit 1
fi
REMOTE
```
**Expected output:** `"Docker pronto: <IP>"` for the 5 instances (control + the 4 above).
**Abort criterion:** exit code ≠ 0 from the block above — the message already states exactly which host(s) failed.

**Port used = the Security Group ingress rule's port (confirmed in Step 1):** SSH 22 (control→host only); gateway 443 (client→server only, never SSH).

---

## Step 5 — `deliver_source.py`: source code and certificates **[OPERATOR → CONTROL → server/clients]**

```
python deliver_source.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --inventory-json /tmp/inventory.json
```
**Expected output:** a report per destination (`server`, `L0`, `L219`, `L325`) with `files` listing the delivered paths (`certs/generated` only for the 3 clients).
**Abort criterion:** any `RuntimeError`.

---

## Step 6 — `deliver_source.py --to-control`: `orchestrator.py` and what it needs **[OPERATOR → CONTROL]** (1 hop only)

**What exactly is copied to the control host** (`CONTROL_FILES`, `deliver_source.py`):
- `thesis/results/v9/campaign/scripts/{orchestrator,cli,preflight}.py`
- `thesis/results/v9/campaign/scripts/rehearsal_handshake.sh`
- `thesis/results/v9/campaign/PINS.json`
- `thesis/results/v9/integration/evaluate_criteria.py`
- `inventory.json` (copied separately — it is not a repository file)

```
python deliver_source.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --to-control --inventory-json /tmp/inventory.json
```
**Expected output:** `{"target": "control", "ip": "...", "files": [...]}`.
**Abort criterion:** any `RuntimeError`. **Never talks to any server/client** (`test_deliver_to_control_um_so_salto_nunca_fala_com_servidor_ou_cliente`).

After this step, `orchestrator.py` exists at
`~/thesis/results/v9/campaign/scripts/orchestrator.py` on the CONTROL
host, along with its own copy of `inventory.json` — this is where
Steps 8/9/10 below read addresses from, never from the operator.

---

## Step 7 — `deliver_images.py`: the 4 images, 1st hop (operator → control) **[OPERATOR → CONTROL]**

```
time python deliver_images.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador>
```
**What this step does, in order:** `docker save -o` of each image
into a `.tar` (locally, on the operator) → the `.tar`'s sha256
checked against the pinned `tar_sha256` (Decision 68 — BEFORE any
scp, catches a wrong/rebuilt local image) → extracts the gateway
binary and checks its sha256 against `PINS.json` (locally, on the
operator) → checks disk space on the control host (`df`, real — a
30GB `gp3` volume, huge headroom for the ~140MB total measured in
this session: gateway ~10MB, proxy ~9MB, pqc-signer ~59MB, measure
~58MB) → scp to the control host → `sha256sum -c` there (transport).

**Real finding from this round (Decision 68): Image ID is NO
LONGER checked anywhere** — `docker image inspect .Id` diverges
between different Docker versions (operator vs. the real instance),
even with identical content, confirmed live in Decision 67 and
reproduced locally with `docker:25-dind`. Identity is now
`tar_sha256` (here) + `RootFS.Layers`/`.Config`/binary (Step 9,
2nd hop) — Image ID is still read, only as an informational field.

**Expected output:** JSON with `disk_check`, `images` (4 entries, `sha256_ok: true`), `gateway_binary_info_delivered: true`.
**Abort criterion:** any `RuntimeError`.

**No `docker run`, no mTLS connection yet — only the 1st delivery hop.**

---

## Step 8 — check `python3` and `orchestrator.py`'s dependencies on the control host **[CONTROL]** (NEW)

**Why `--help` is already enough:** `cli`/`preflight`/`evaluate_criteria`
are imported at the TOP of the `orchestrator.py` module (outside any
function, lines before `def main()`) — if ANY of these imports
fails, `python3 orchestrator.py --help` never gets to print the
usage, it breaks with the import traceback before that. Checked by
reading all 3 files line by line: **none imports a third-party
package** — only the standard library (`argparse`/`json`/`re`/
`subprocess`/`sys`/`pathlib`/`collections`/`random`/`datetime`/
`time`). There is, therefore, no `pip` package needed here.

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 --version
python3 orchestrator.py --help >/dev/null && echo "OK: orchestrator.py importa e roda"
REMOTE
```
**Expected output:** the Python 3 version, followed by `OK: orchestrator.py importa e roda`.
**If something is missing:** since none of the 3 modules uses a
third-party package, the only real cause is `python3` missing/broken
on Amazon Linux 2023 ARM64 (the control host is a `t4g.micro`) —
`install_common_packages.sh` already installs `python3-pip` (which
brings `python3` as a dependency) on EVERY instance, control host
included, so this should not be missing; if it is missing anyway:
`sudo dnf install -y python3`. **Never run `pip install` here** —
there is no third-party dependency to install.
**Abort criterion:** any import traceback, or `python3`
missing — resolve BEFORE Step 9 (no real exercise
would work otherwise anyway).

---

## Step 9 — `orchestrator.py --exercise-start-stop`: 2nd hop (control → host) + real start_block/stop_block **[CONTROL]**

**Why this also proves the 2nd hop:** `SSHExecutor._deliver_image`
(inside `start_block`, called by this exercise) does the rest —
scp of the `.tar` already staged on the control host (Step 7) to the
HOST, `ssh host docker load`, then checks the host's
`RootFS.Layers`/`.Config` against PINS.json and, for `gateway`/
`proxy`, the sha256 of the binary INSIDE the loaded container
(Decision 68 — **Image ID is never compared**, only read/recorded).
It proves all 3 pinned images (`gateway`/`proxy`/`pqc-signer`) at
once, plus the TCP probe (finding 18) and the gateway binary
(Decision 54), with no timed execution at all.

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 orchestrator.py --mode ssh \
  --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --exercise-start-stop --exercise-profile classico --exercise-route L0 > /tmp/exercise_report.json
cat /tmp/exercise_report.json
echo "--- tempo/identidade de entrega por imagem (2o salto, controle->host) ---"
python3 -c "
import json
r = json.load(open('/tmp/exercise_report.json'))
for v in r['image_delivery_verifications']:
    print(f\"{v['image_key']:12s} host={v['host']:16s} elapsed={v['elapsed_seconds']:>7.1f}s \"
          f\"tar={v['tar_bytes']} bytes ok={v['ok']} slow={v['slow']} \"
          f\"layers_ok={v['layers_ok']} config_ok={v['config_ok']} binary_ok={v['binary_ok']} \"
          f\"image_id_INFORMATIVO={v['loaded_image_id']}\")"
REMOTE
```
**Expected output:** JSON with `"start_block_ok": true`, `"stop_block_ok": true`,
`gateway_binary_verifications` (1 entry, `pin_matched: true`,
`running_container_sha256_ok: true`), followed by the per-image time/
identity listing (gateway/proxy/pqc-signer), none with
`slow: true`, all with `ok: true`/`layers_ok: true`/`config_ok:
true`/`binary_ok: true` (the printed `image_id` is only
informational — it may diverge from what `PINS.json` lists, this is
expected and not a cause for alarm, Decision 68), and
`tcp_preflight_results` (1 entry, `"ok": true`).

Manually confirm, in a second session **[CONTROL]** while the
call above is running, that the 3 containers exist while the
command runs:
```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" "ssh -i ~/.ssh/campaign_key ec2-user@$SERVER_IP docker ps -a --filter name=v9-mtls"
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" "ssh -i ~/.ssh/campaign_key ec2-user@$L0_IP docker ps -a --filter name=tls_kem_proxy_run --filter name=pqc_signer_service_run"
```
**Abort criterion:** any `"ok": false`/exception; **OR any
delivery with `elapsed_seconds` > 600 (10 minutes, `"slow":
true`)** — a symptom of a degraded control↔host link, never proceed
with the rest of the rehearsal without investigating first. **No
manifest/execution file is written by this step**
(`test_exercise_start_stop_sobe_e_desce_sem_execucao_nem_manifest`)
— it never counts as any of the 60/12 official ones. **No call
invokes `docker` locally on the control host**
(`test_deliver_image_nunca_invoca_docker_localmente`).

---

## Step 10 — real handshake per profile (4, proof of mechanism) **[CONTROL]**

**Tested locally in loopback before being delivered** (still on
the operator's laptop, pure local Docker validation, no AWS — actual
output from this session):
```
$ GATEWAY_SSH="" CLIENT_SSH="" GATEWAY_HOST="mtls" bash rehearsal_handshake.sh
=== [classico] removendo gateway anterior (se houver) ===
=== [classico] subindo gateway com CRYPTO_PROFILE=classico ===
=== [classico] esperando o gateway ficar pronto (limite: 30 tentativas, 1s cada) ===
=== [classico] disparando a conexao real (negtest -scenario matrix) ===
RESULT matrix client=classico server=classico outcome=SUCCESS curve=CurveP384 dualAuthenticated=false error=none
=== [classico] extraindo a linha 'connection OK' (grep, nunca tail -1) ===
gateway: classico connection OK remoteAddr=172.21.0.6:35062 sni="mtls" curve=CurveP384 dualAuthenticated=false clientCert="classico_client" handshakeBytesIn=1513 handshakeBytesOut=1640
=== [classico] handshakeBytesIn=1513 (esperado 1513, delta 0) | handshakeBytesOut=1640 (esperado 1640, delta 0) ===
OK [classico]: delta 0B nos dois sentidos
... (pqc, hibrido-v8, hibrido-and: mesmo padrão, mesmo resultado) ...
RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos
```

**Correction in this round (item 2): the `GATEWAY_HOST` address
must be the SAME one that the L0 route actually dials in production
(`orchestrator._server_gateway_ip`) — confirmed in `outputs.tf`: L0
is `colocated: true` (same AZ ID as the server), so it dials the
server's PRIVATE IP, never the EIP. Calculated below from the local
copy of `inventory.json` on the control host (delivered in Step 6),
never typed by hand — the same applies to the `GATEWAY_SSH`/
`CLIENT_SSH` addresses (always the PUBLIC IP, for SSH — Decision
43/45) and to the `negtest` delivery's 2nd hop below, which also had
fixed placeholders before this correction.**

`mockopin-v9-negtest` is not pinned in `PINS.json` (reason
already recorded in Decision 57) — delivered here via a manual 2nd
hop, similar in spirit to `deliver_images.py` but without going
through PINS.json:

```
# 1st hop (operator -> control), [OPERATOR]:
docker save mockopin-v9-negtest > /tmp/negtest.tar
scp -i <chave-do-operador> /tmp/negtest.tar ec2-user@"$CONTROL_IP":~/images/negtest.tar

# 2nd hop (control -> client L0) + the rehearsal itself, all [CONTROL] --
# addresses recalculated HERE from the local copy of inventory.json,
# never received as a placeholder from the operator:
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
SERVER_IP=$(python3 -c "import json; print(json.load(open('inventory.json'))['server']['public_ip'])")
L0_IP=$(python3 -c "import json; print(json.load(open('inventory.json'))['clients']['L0']['public_ip'])")
GATEWAY_HOST_L0=$(python3 -c "
import json
inv = json.load(open('inventory.json'))
c = inv['clients']['L0']
print(inv['server']['private_ip'] if c.get('colocated') else inv['server']['public_ip'])
")

scp -i ~/.ssh/campaign_key ~/images/negtest.tar ec2-user@"$L0_IP":~/negtest.tar
ssh -i ~/.ssh/campaign_key ec2-user@"$L0_IP" "docker load < ~/negtest.tar && rm -f ~/negtest.tar"

GATEWAY_SSH="ssh -i ~/.ssh/campaign_key ec2-user@$SERVER_IP" \
CLIENT_SSH="ssh -i ~/.ssh/campaign_key ec2-user@$L0_IP" \
GATEWAY_HOST="$GATEWAY_HOST_L0" \
bash rehearsal_handshake.sh
REMOTE
```
**Expected output:** `RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos` — same as the local test, now on real network/instances, triggered from the control host, dialing the SAME address that the real route uses.
**Abort criterion:** any `FALHA` printed by the script, or `RESULTADO FINAL: FAIL` — marks the rehearsal as **failed at this point**, recorded explicitly, before moving on to step 11.

**What this step does NOT do:** it does not count as any of the 60 official executions nor any of the 12 criterion-1 captures.

---

## Step 11 — `emergency_stop.py`, dry mode **[OPERATOR]** (diagnostic, before any teardown)

```
python emergency_stop.py --profile mockopin-pqc
```
**Expected output:** `instances_found`/`eips_found`/`security_groups_found`/`key_pairs_found` listing the rehearsal's actual resources (4 key pairs, fixed in Decision 57), and all the `..._terminated`/`..._released`/`..._deleted` lists **empty**.
**Abort criterion:** any non-empty action list in dry mode.

---

## Step 12 — MAIN teardown: `cleanup.py --release-eips --force` **[OPERATOR]**

**Why `cleanup.py`, not `emergency_stop.py`, is the main path**
(Decision 57): the same 5 structural checks as v8, but `cleanup.py`
detects self-shutdown drift BEFORE the destroy and ACTIVELY releases
orphaned EIPs.

```
python cleanup.py --tf-dir ../../terraform --profile mockopin-pqc --release-eips --force
```
**Expected output:** JSON with `"all_clean": true`.
**Abort criterion:** `all_clean: false` — go to step 13 (fallback), never skip directly to step 14.

---

## Step 13 — fallback: `emergency_stop.py --execute`, only if something is left **[OPERATOR]**

**Only runs if step 12 reported `all_clean: false`.** If it already gave `all_clean: true`, skip directly to step 14.

```
python emergency_stop.py --profile mockopin-pqc --execute
```
**Expected output:** any resource that step 12 did not clean up now appears in `..._terminated`/`..._released`/`..._deleted`.
**Abort criterion:** any persistent permission error — manual investigation via the AWS console.

---

## Step 14 — final verification: nothing left in the account **[OPERATOR]**

```
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" "Name=instance-state-name,Values=running,pending,stopping,stopped"
aws ec2 describe-addresses --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
aws ec2 describe-security-groups --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
aws ec2 describe-key-pairs --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
```
(repeat the 4 calls for `eu-north-1`/`ap-southeast-1` — 12 calls total)

**Expected output:** all 12 calls return **empty** lists.
**Abort/alert criterion:** any resource still present.

---

## Estimated rehearsal cost

~35 minutes of fleet time (steps 0-14, +5 min over Decision 59
due to the new dependency-check step and the extra time/Image ID
check) — 5 instances: 4× `m7i-flex.large` + 1× `t4g.micro` — + 5 EIPs:
- Compute: (4 × US$0,0958 + US$0,0084) × (35/60)h ≈ US$0,230
- EIP: 5 × US$0,005 × (35/60)h ≈ US$0,015
- EBS: negligible (deleted together during destroy/termination)
- **Estimated total: ≈ US$0,25**, even at double the time (70 min): ≈ US$0,49.

**If something fails and the 1h self_terminate triggers before
manual cleanup:** cost rises to ~2× the above (≈US$0,46 of compute)
— the EIPs carry the same already-documented residual risk, covered
both by `cleanup.py --release-eips` (main) and by `emergency_stop.py`
(fallback).

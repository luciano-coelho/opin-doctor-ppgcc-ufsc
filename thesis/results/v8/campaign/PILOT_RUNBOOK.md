# Pilot runbook — v8 real-AWS campaign

Scope: **`sa-east-1` only** — the server, the `L0` and `L325` clients,
and the control instance. `terraform plan` for exactly this topology:
**21 resources to add, 0 to change, 0 to destroy** (confirmed live,
read-only, this turn — Decision 69). 10 executions per profile per
scenario, 3 profiles, 2 scenarios = **60 executions total**, 1 window
(not the full campaign's 3).

This is the step that comes BEFORE the full 12-instance/8-scenario
campaign (Decision 47/54/55's own sequence) — it exists to catch a
wrong instance type, a broken delivery, a wrong curve, or an
unacceptable tcpdump overhead on a **small, cheap, fast-to-tear-down**
topology before spending the full campaign's time and money on it.

Every `terraform apply`/`destroy` and every instance launch in this
runbook **requires Luciano physically present** — this document is not
a substitute for that, and no command in it is meant to be run
unattended. Anything this runbook's own commands print that contains a
real ARN, account ID, instance ID, or IP address must go through
`scripts/scan_secrets.sh` before being pasted into any document this
repository tracks (the example outputs below use clearly-fake
placeholders for exactly this reason).

## Pré-condições

Both of these must be true before step 1 below is run for real:

1. **The flex launch test (Decision 43) is complete and an instance
   type is chosen.** `server_client_instance_type` has **no default on
   purpose** (Decision 52) — `terraform plan`/`apply` fail outright if
   it's unset, specifically so a placeholder can't get used by
   accident before this test resolves it. Until this is done, every
   command below that needs `MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE`
   is a dry run against whatever placeholder you supply, not a real
   plan for the actual pilot.
2. **Luciano has personally checked, in the AWS Billing console, just
   now — not from memory:**
   - The remaining Free Plan credit balance and its expiration date.
   - That the billing budget alert is configured and has not already
     fired.
   This project's restricted `mockopin-pqc` IAM profile **cannot read
   either value via the API** (Decision 44) — `campaign_up.sh` already
   stops and asks for this exact confirmation interactively before it
   will apply anything; this precondition is that check, stated here
   so it isn't skipped by running something else first.

## Credenciais e acesso (confirmado nesta sessão, antes de qualquer comando abaixo)

- Active AWS profile: **`mockopin-pqc`** (the project's own dedicated,
  restricted IAM user — Decision 44: EC2/VPC-only policy, no IAM/Org
  management). Confirmed by listing profile NAMES only (`~/.aws/config`,
  `~/.aws/credentials`) — exactly one profile exists in either file,
  and it's this one.
- No admin/default credential is present in this session's environment
  — no `AWS_ACCESS_KEY_ID`/`AWS_SESSION_TOKEN` env vars set, no
  `[default]` profile in either AWS config file.
- `terraform plan` is read-only and was run freely this session
  (against real, live AWS data) to validate the exact pilot topology
  below. `terraform apply`/`destroy` and any instance launch are not
  run by anyone other than Luciano, present, following this runbook.

## Passo a passo

Every command below assumes `campaign.vars.local.sh` already exists
(copied from `scripts/campaign.vars.example.sh`, gitignored, filled in
with the real operator key paths) and that `MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE`
in it is the type the flex launch test actually chose.

### 1. Scope the apply to the pilot topology

Add this line to `campaign.vars.local.sh` (or export it directly
before running `campaign_up.sh`):

```bash
export MOCKOPIN_ENABLED_CLIENT_SCENARIOS="L0@sa-east-1 L325@sa-east-1"
```

### 2. Preview the plan (read-only, no Luciano-presence requirement by itself — but don't apply without him)

```bash
cd thesis/results/v8/campaign/terraform
terraform plan \
  -var="operator_ip_cidr=$(curl -s https://checkip.amazonaws.com)/32" \
  -var="operator_ssh_public_key=$(cat /path/to/mockopin_pqc_discovery.pub)" \
  -var="server_client_instance_type=<CHOSEN_TYPE>" \
  -var='enabled_client_scenarios=["L0@sa-east-1","L325@sa-east-1"]'
```

**Expected output** (exact resource count, confirmed live this turn —
Decision 69): the final line reads

```
Plan: 21 to add, 0 to change, 0 to destroy.
```

If it shows a different number, **stop** — something about the
topology or the variable scoping has drifted since this runbook was
written; do not proceed to apply.

### 3. Apply (Luciano present)

```bash
cd thesis/results/v8/campaign/scripts
./campaign_up.sh campaign.vars.local.sh
```

**Expected prompts, in order** (both already built into the script,
not added by this runbook):

```
==> BEFORE APPLYING: confirm you have personally checked, in the AWS
    console, just now -- not from memory -- both of the following
    (Decision 44: this project's restricted IAM profile cannot read
    either value via the API, so this has to be a human check):
      1. The billing budget alert is configured and has not already fired.
      2. The remaining Free Plan credit balance and its expiration date.
    Type 'checked' to confirm both: checked
==> terraform apply -- REQUIRES THE AUTHOR PRESENT. Ctrl-C now if not.
    Type 'apply' to continue: apply
```

**Expected final output:**

```
==> campaign_up.sh completed: instances up (12, or fewer if MOCKOPIN_ENABLED_CLIENT_SCENARIOS scoped this apply), connectivity and clock sync verified.
```

The script's own built-in verification (SSH reachability + `chronyc
tracking` on every host, proxied through control) must show `OK:` for
all 3 pilot hosts (server + 2 clients) before this line prints — a
`FATAL:` anywhere means step 4 below is already covering a real
problem, not a formality.

### 4. First contact with AWS — verification (every item is a real check, not a formality)

Run each of these over SSH, proxied through the control instance's own
key (same pattern `campaign_up.sh` itself uses). Replace
`<CONTROL_IP>`/`<SERVER_IP>`/`<CLIENT_IP>` with the real values from
`terraform output -json inventory` (pass that JSON through
`scan_secrets.sh`'s own spirit before pasting it anywhere outside this
local check — it contains real IPs).

| Check | Command (run from the control instance, or via `ssh ... <cmd>` proxied through it) | Expected |
|---|---|---|
| cloud-init finished | `cloud-init status` | `status: done` |
| docker installed + active | `systemctl is-active docker` | `active` |
| `ec2-user` in the `docker` group | `groups ec2-user` | includes `docker` |
| docker usable without sudo | `docker ps` (no `sudo`) | empty table header, no `permission denied` |
| chrony active + synced | `chronyc tracking` | `Leap status : Normal`, `Stratum` a small number (not `0`) |
| rsync installed | `command -v rsync` | a path, e.g. `/usr/bin/rsync` |
| Elastic IP actually associated | `curl -s https://checkip.amazonaws.com` (run ON the instance) | matches the EIP Terraform's own output shows for that instance |
| environment recorded, AMI matches pinned | after `campaign_run.py` starts (step 5), check `v8/latency/_campaign-control/environment/<instance>.json` was written for every pilot instance, and that its `ami_id` matches `terraform/main.tf`'s own `pinned_ami_x86_by_region`/`pinned_ami_arm64_sa_east_1` for that region | file exists, `ami_id` matches the pinned value exactly (a mismatch means the instance didn't boot from the AMI Terraform pinned — investigate before trusting any data from it) |
| security group: server accepts 443 only from its 2 pilot clients | `aws ec2 describe-security-groups --group-ids <SG_ID> --profile mockopin-pqc` (run from the OPERATOR's own machine, not an instance) | exactly 2 ingress rules on 443, each a /32 matching the 2 clients' own IPs (one private — `L0`'s, co-located — one public — `L325`'s) |
| security group: clients/server accept 22 only from control's EIP | same `describe-security-groups` on each client/server's own SG | exactly one ingress rule on 22, the control instance's EIP /32 |
| control ↔ server connectivity | `ssh -i ~/.ssh/campaign_key ec2-user@<SERVER_IP> echo ok` (from control) | `ok` |
| control ↔ each client connectivity | same, against each client's IP | `ok` |
| server → client network path exists (gateway's own ingress rule) | from the `L325` client: `nc -zv <SERVER_PUBLIC_IP> 443` (before the stack is even up, expect connection refused, NOT a timeout — a timeout means the security group rule is wrong, a refusal means the rule is right and nothing's listening yet) | `Connection refused` (good) or `Connection timed out` (bad — stop) |

Any row that doesn't match → **abort** (see criteria below), do not
proceed to step 5.

### 5. Deliver images, run settling + the acceptance battery

```bash
cd thesis/results/v8/campaign/scripts
MOCKOPIN_CONTROL_IP_OVERRIDE="<CONTROL_IP>" \
  bash deliver_images.sh campaign.vars.local.sh
```

**Expected final line:** `==> deliver_images.sh completed for all 4 images.`
(the 4 custom-built images — Decision 55; the 3 stock images pull from
their own public registries on the server directly, no delivery step
needed for them).

Then start the orchestrator itself (on the control instance, as a
systemd service — `campaign_run.service`, already written) with the
pilot's own short schedule (`CAMPAIGN_RUNS_PER_WINDOW=10`,
`CAMPAIGN_WINDOWS_PER_CAMPAIGN=1`, `CAMPAIGN_INSTALLATIONS=sa-east-1` —
the SAME env-var overrides this turn validated against the local
rehearsal, Decision 68/69, now pointed at the real pilot instances
instead):

```bash
ssh -i ~/.ssh/campaign_key ec2-user@<CONTROL_IP>
sudo systemctl edit campaign_run.service   # add the 3 Environment= lines above under [Service]
sudo systemctl start campaign_run.service
journalctl -u campaign_run -f              # watch it live
```

**Expected**, per profile block: `[sa-east-1/<profile>] settling:
client curves=[...]` showing the profile's OWN expected curve
(`CurveP384` classic / `MLKEM1024` pqc / `SecP384r1MLKEM1024` hybrid),
matching `internal curves=['CurveP256']` always. A settling verification
failure here is an **abort criterion** (below), not something to
retry past.

### 6. Pull the data back and verify it

```bash
cd thesis/results/v8/campaign/scripts
./campaign_pull.sh campaign.vars.local.sh ./pilot-data-pulled
```

**Expected final lines:**
```
OK: every pulled file matches its sha256.
==> campaign_pull.sh completed, verified copy at: ./pilot-data-pulled
    (.pull-verified written -- campaign_down.sh checks for this before it will destroy anything)
```

### 7. Run the acceptance battery

```bash
python thesis/results/v8/campaign/scripts/pilot_acceptance.py ./pilot-data-pulled
```

See `pilot_acceptance.py`'s own module docstring for exactly what each
criterion checks and how. **Expected:** one `PASS`/`FAIL` line per
criterion, ending in `OVERALL: PASS` or `OVERALL: FAIL`.

## Pontos em que Luciano confirma antes de seguir

1. Before `terraform apply` (step 3) — the budget/credit check, already
   built into `campaign_up.sh` as an interactive prompt.
2. Before `terraform apply` itself (step 3) — the "author present"
   prompt, also already built in.
3. **After step 4** (first-contact checks), before spending any money
   on step 5's settling runs — a human look at the table above, not
   just "the script didn't error."
4. **After step 7** (acceptance battery), before either of the two
   outcomes below — this is the actual pilot/no-pilot decision point.
5. Before `campaign_down.sh` is ever run with `--force` (it refuses by
   default unless `.pull-verified` exists, Decision 49 — `--force`
   bypasses that refusal and is a real, deliberate override).

## Critérios de aborto

Abort (stop, do not spend further pilot budget, go to teardown) if ANY
of these happen:

- Step 2's plan shows anything other than exactly `21 to add, 0 to
  change, 0 to destroy`.
- Any row in step 4's first-contact table fails.
- A settling block's negotiated-group check fails for real (not the
  pre-flight's own informational mismatch, B.12's actual post-switch
  abort, Decision 62/67) — this means the delivered image or the
  profile switch itself is wrong, not a flaky run.
- `pre_block_checks()`'s `image_id` check aborts (Decision 69, item 1)
  — the loaded gateway image doesn't match what was actually delivered.
- `deliver_images.sh` fails its own sha256 verification step, even
  once, even after a retry.
- Any execution's tcpdump capture aborts the block (Decision 63 — a
  missing capture tool or a bad interface, by design, never silently
  skipped).
- `pilot_acceptance.py` reports `OVERALL: FAIL`.
- The AWS Billing console (checked by Luciano, not inferred) shows
  spend meaningfully above this runbook's own cost estimate below
  without a clear, understood reason.

## Acompanhamento de custo durante a execução

The restricted IAM profile cannot read current spend via the API
(Decision 44) — **Luciano checks the AWS Billing console directly**,
not a script, at:
- **T+0** (right after step 3's apply completes) — baseline sanity
  check, nothing should show yet (billing data lags).
- **T+2h** — after settling + roughly half the 60 executions, per the
  duration estimate below.
- **Right before step 6** (pulling data) — last check before deciding
  between the two outcomes.
- **Immediately after teardown** (if that's the chosen outcome) — confirm
  the cost stopped accruing, not just that `campaign_down.sh` printed
  success.

## Estimativa de duração e custo (labeled estimate, same method as Decisions 47/54/55 — not a precise figure)

- **Active run time**: `sa-east-1`'s own per-execution average from
  Decision 47/54 (~9.2s/execution, derived from "~55min active / 360
  sa-east-1 executions in the full campaign") × 60 pilot executions ≈
  **~9 minutes**.
- **Settling**: 3 profile switches (1 window × 3 profiles), roughly
  **~7 minutes** (Decision 47's own ~21min/9-switches rate).
- **Realistic wall-clock for the pilot's own instances**, including
  boot, first-contact verification, image delivery (Decision 55:
  ~25-40 minutes one-time for the FULL 4-image/3-server delivery — the
  pilot delivers to only 1 server, so proportionally faster, call it
  **~10-15 minutes**), and the confirmation points above: **roughly
  1-2 hours total**, not days — this is the whole point of a pilot
  being small.
- **Cost**: 4 instances (1 `t4g.micro` control + 1 server + 2 clients,
  type TBD by the flex test) for ~1-2 hours, at the same blended
  ~$0.10-0.15/hr/instance (compute + public IPv4) this project's own
  docs already use (Decisions 47/54/55) ≈ **4 × 1.5h × $0.125 ≈ $0.75,
  call it under $1** for the pilot's own active run. This is NOT a
  substitute for Luciano's own Billing console check above — it's a
  sanity-check number to notice if something is badly wrong (e.g. the
  flex instance type turning out far pricier than `m7i-flex`/
  `c7i-flex` class, or an instance left running far longer than
  planned).

## Os dois desfechos

**(A) Seguir para a campanha completa.** Run `campaign_up.sh` again,
WITHOUT `MOCKOPIN_ENABLED_CLIENT_SCENARIOS` set (or set to the full
8-scenario list) — `terraform apply` on the UNCHANGED topology (same
state, same `terraform.tfstate`) adds the other 24 resources (the
other 2 installations' servers/clients) without touching any of the
pilot's own 21 (Decision 69's own structural proof: every resource
address the pilot already created has identical planned config in the
full-topology plan, so Terraform's own plan would show `0 to change`
for all 21, only `24 to add`). **Do not `campaign_down.sh` the pilot
first if this is the outcome** — that would destroy and recreate work
that doesn't need recreating, costing more time and (briefly) more
money than just extending it.

**(B) Teardown e correção.** Any abort criterion fired, or Luciano's
own judgment says something needs fixing first (instance type, a
config bug, a protocol change — see the data-retention rule below for
what "protocol change" means for the data already collected).

```bash
cd thesis/results/v8/campaign/scripts
./campaign_down.sh campaign.vars.local.sh
```

Refuses by default unless `.pull-verified` exists (i.e., step 6 ran
and passed) — pass `--force` only if the pilot is being abandoned
WITHOUT trusting its data at all (an aborted run, not a completed one
worth keeping even as "second window" data per the retention rule).
`campaign_down.sh` verifies region-by-region via the AWS API directly
afterward (instances, security groups, key pairs, volumes, Elastic
IPs) — a clean run shows zero resources left in every category.

## Dados do piloto — regra de retenção

**Regra:** os dados do piloto (as 10 execuções por perfil, 3 perfis, 1
janela, nas 2 células `L0`/`sa-east-1` e `L325`/`sa-east-1`) só contam
como a PRIMEIRA janela (window 1) dessas células na campanha completa
SE o protocolo de medição não mudar depois do piloto. Se mudar, os
dados do piloto NÃO são descartados — vão para uma pasta separada,
preservados, mas fora da árvore `v8/latency/...` que a campanha
completa usa para computar os resultados da tese.

**O que conta como "o protocolo mudar"** (qualquer um destes invalida
o window 1 do piloto para fins de mistura com dados futuros da mesma
célula):
- Mudança em `campaign_run.py`/`campaign_client_runner.py` que altere
  O QUE é medido ou COMO (ex.: um novo bug de medição corrigido depois
  do piloto, uma mudança no que `t_fluxo_seconds`/`calls.jsonl`
  capturam, uma mudança na lógica de tcpdump/sampler de CPU).
- Mudança no tipo de instância (`MOCKOPIN_SERVER_CLIENT_INSTANCE_TYPE`)
  usado pro servidor ou os clientes — já que o teste de lançamento flex
  (pré-condição deste runbook) pode revelar a necessidade de trocar o
  tipo escolhido.
- Mudança na imagem Docker entregue (`deliver_images.sh`) que altere o
  comportamento do gateway mTLS ou dos serviços medidos.
- Mudança nos critérios de aceite (`pilot_acceptance.py`) que implique
  uma correção retroativa na forma de interpretar os dados já
  coletados (não apenas uma correção no PRÓPRIO script de verificação,
  que não afeta os dados brutos).

**O que NÃO conta como mudança de protocolo** (o window 1 do piloto
continua válido): achar e corrigir um bug em
`pilot_acceptance.py`/`campaign_pull.sh` que não altera nenhum dado já
gravado pelas instâncias (ex.: um bug de parsing do lado da análise);
ajustes de documentação; mudanças em scripts de regiões/cenários NÃO
usados pelo piloto (`L0`/`L325`/`sa-east-1`).

**Se o protocolo mudar:** os arquivos já coletados sob
`v8/latency/experiment{1,2,3} - {Classic,PQC,Hybrid}/{L0,L325}/sa-east-1/`
são movidos (não apagados) para
`v8/latency/_pilot-superseded-<data-UTC-do-piloto>/` com a mesma
estrutura interna, e uma nota é adicionada ao `DECISIONS.md` explicando
o motivo da mudança e por que os dados antigos não foram reaproveitados
como window 1. A campanha completa então recomeça window 1 dessas 2
células do zero, sob o protocolo corrigido.

**Se o protocolo NÃO mudar:** os dados do piloto permanecem exatamente
onde `campaign_pull.sh` os deixou, e `campaign_up.sh` (outcome A acima)
simplesmente continua a numeração de janelas/execuções a partir daí —
nenhuma recoleta das 2 células do piloto é necessária.

## Manter as instâncias de pé até a campanha, ou derrubar: comparação para Luciano decidir

This is a genuine judgment call, not something this runbook can answer
for you — it depends entirely on how long the gap will actually be
between the pilot finishing and the full campaign starting, which only
Luciano can estimate.

| | **Keep the 4 pilot instances up** | **Tear down, reapply later** |
|---|---|---|
| **Cost while waiting** | ~4 × $0.125/hr ≈ **$0.50/hour** of idle time, accruing the whole gap | ~$0 while torn down (the only cost is the few minutes of EC2/EIP provisioning time on the LATER apply — a few cents at most) |
| **Time cost when the full campaign actually starts** | None — `campaign_up.sh` (full scenario list) just adds the other 24 resources on top | Must redo: `terraform apply` (a few minutes for all 28 resources this time, not incremental), THEN **redo step 4's entire first-contact checklist** on the 4 pilot resources too (they're now brand-new instances, not the ones the pilot actually verified) |
| **Risk** | The pilot's own server/clients could drift (a manual change, an unexpected restart) during a long idle gap, undetected until the full campaign starts | None specific to idling — but a fresh apply could hit a NEW problem (quota, AMI update, region issue) that the pilot itself didn't catch, discovered only after the gap |
| **Breakeven, roughly** | — | If the gap is expected to be **under ~30 minutes** (e.g. Luciano is running the acceptance check and will decide within the same sitting), keeping it up is cheaper AND avoids re-verifying. **Over a few hours**, tearing down is clearly cheaper ($0.50+/hour vs ~$0 while down) and the re-verification is the same ~15-20 minutes either way (step 4's checklist is quick, already scripted as a table above, not a research task) |

**This runbook's own recommendation, stated plainly so Luciano can
override it**: if the decision to proceed to the full campaign is made
in the SAME session as the pilot (Luciano still present, reviewing
`pilot_acceptance.py`'s output right now), keep the 4 instances up and
go straight to outcome (A). If there's going to be a real gap (waiting
on a protocol fix, a different day), tear down — the idle cost adds up
fast relative to the pilot's own ~$1 total, and the safety-timer
default (48h, Decision 49) would otherwise auto-terminate them anyway
if the gap runs long and nobody renews it.

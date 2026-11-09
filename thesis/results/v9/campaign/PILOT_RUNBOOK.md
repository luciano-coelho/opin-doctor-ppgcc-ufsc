# PILOT_RUNBOOK.md — Fase B, piloto real (60 execuções, 4 perfis × 3 rotas × N=5)

Decisão do Luciano, item 4 (DECISIONS.md, Decisão 79): "escreva o
PILOT_RUNBOOK.md da Fase B... no mesmo nível de detalhe do
INFRA_REHEARSAL.md, e siga-o." Mesma convenção de máquina/comando
daquele roteiro — repetida aqui, nunca redefinida:

| Convenção | Significado |
|---|---|
| **[OPERADOR]** | Roda no laptop do Luciano. Só alcança o CONTROLE direto (`ssh_ingress_cidrs = {"operator": var.operator_ip_cidr}`) — nunca servidor/clientes direto. |
| **[CONTROLE]** | Roda DE DENTRO da instância `control` (via `ssh $CONTROL_IP "<comando>"` disparado pelo operador). Só o controle alcança servidor/clientes (`ssh_ingress_cidrs` deles só listam `{"control": "${module.control.public_ip}/32"}`). |

**`self_terminate_hours=4`** (vs. 1h do ensaio de infraestrutura) —
o piloto real tem 60 execuções + 12 capturas dedicadas + 3 passos de
entrega, uma janela maior que o ensaio puro de infraestrutura.

**Pré-checagem do IP do operador (Decisão 77, `check_operator_ip.py`)
roda ANTES de QUALQUER fase deste roteiro que dependa de SSH
funcionar** — nunca só uma vez no Passo 0. Repita o comando do Passo
1 antes de cada bloco marcado com 🔁 abaixo.

**Gap fechado (Decisão 85):** os critérios 2 (initcwnd), 3 (zero
erros na rota mais distante) e 7 (sanidade de latência) agora rodam
de verdade contra o piloto real — `dedicated_criteria.py` (novo,
entregue ao controle) liga os 3 produtores (`thesis/results/v9/
integration/producers/{criterio2_probe,criterio3_collector,
criterio7_rtt}.py`) ao pipeline: uma porta de ingress NOVA (9876,
Decisão 85, mesmo escopo de `gateway_ingress_cidrs`) pro criterio 2;
um adaptador que reusa `evaluate_criteria.criterion_4_counts` (nunca
reimplementado) pro criterio 3; os dois produtores corrigidos pra
rodar `tshark` via `docker run ... mockopin-v9-measure` (o servidor
real nunca tem `tshark` no PATH do host) pro criterio 7. **Este
roteiro agora fecha os 7 critérios de verdade — nenhum "sem
evidência" esperado por desenho.**

---

## Passo 0 — pré-requisitos **[OPERADOR]**

```
export TF_VAR_operator_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
cd thesis/results/v9/terraform
terraform init
```
**Saída esperada:** `Terraform has been successfully initialized!`
**Critério de abortar:** qualquer erro de init/provider.

---

## Passo 1 — pré-checagem do IP do operador (Decisão 77) **[OPERADOR]** 🔁

```
python ../campaign/scripts/check_operator_ip.py --tf-dir .
```
**Saída esperada (fleet ainda não existe, 1ª vez):** `{"ok": false, "error": "... recurso ... nao encontrado no state ..."}` — **esperado e inofensivo** antes do primeiro apply (Passo 2); a regra só existe depois dele. Depois do Passo 2, repita este comando — a partir daí a saída esperada é `{"ok": true, "changed": false, ...}` (ou `"changed": true` com o IP novo, se tiver mudado).
**Critério de abortar:** depois do Passo 2 existir, qualquer `"ok": false` com uma mensagem de `terraform apply` falhando — nunca prosseguir pra nenhum passo com SSH sem resolver isto primeiro (ver nota de infraestrutura da Decisão 72/77 — um bloqueio real de 8 minutos já custou uma fleet inteira).

---

## Passo 2 — `terraform plan`, depois `terraform apply` (`self_terminate_hours=4`) **[OPERADOR]**

Mesma infraestrutura do ensaio de infraestrutura, MAIS 3 regras novas
(Decisão 85 — porta dedicada do produtor do critério 2):

| Recurso | Quantidade |
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
**Saída esperada:** `Plan: 31 to add, 0 to change, 0 to destroy.` — se divergir, **pare e reconcilie antes do apply**.

```
terraform apply -var="self_terminate_hours=4" -auto-approve
```
**Saída esperada:** `Apply complete! Resources: 31 added, 0 changed, 0 destroyed.`
**Critério de abortar:** qualquer erro de apply, ou N ≠ 31 sem explicação — `terraform destroy -auto-approve` imediatamente.

Repita o Passo 1 agora (a regra de ingress já existe).

---

## Passo 3 — confirmar instâncias + gerar `/tmp/inventory.json` **[OPERADOR]**

```
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 \
  --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" \
  --query "Reservations[].Instances[].State.Name"
```
(repetir para `eu-north-1`/`ap-southeast-1`)
**Saída esperada:** `"running"` nas 3 regiões (5 instâncias no total).
**Critério de abortar:** qualquer instância fora de `running`/`pending` por mais de 2 minutos.

Gera `/tmp/inventory.json` (`terraform output -json inventory`), confere o formato real contra o que `deliver_source.py`/`pki_relay.py`/`orchestrator.py` leem (mesmo procedimento do Passo 2 de `INFRA_REHEARSAL.md`).

---

## Passo 4 — entregar a chave SSH da campanha pro controle **[OPERADOR → CONTROLE]**

```
terraform -chdir=../../terraform output -raw campaign_private_key | \
  python pki_relay.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --deliver-campaign-key --inventory-json /tmp/inventory.json
```
**Saída esperada:** JSON com `"campaign_key_remote_path": "/home/ec2-user/.ssh/campaign_key"`.
**Critério de abortar:** qualquer `RuntimeError`.
**Nunca impresso:** o conteúdo da chave.

---

## Passo 5 — Docker pronto nas 5 instâncias **[CONTROLE/OPERADOR]**

Mesmo laço fail-closed do Passo 4 de `INFRA_REHEARSAL.md` (SSH direto do controle a cada host, relé pela chave da campanha, `FAILED=""`/`exit 1` se algum nunca ficar pronto).
**Saída esperada:** `"Docker pronto: <IP>"` pras 5 instâncias.
**Critério de abortar:** exit code ≠ 0 — a mensagem já diz qual host falhou.

---

## Passo 6 — `deliver_source.py`: código-fonte e certificados **[OPERADOR → CONTROLE → servidor/clientes]** 🔁

```
python deliver_source.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --inventory-json /tmp/inventory.json
```
**Saída esperada:** relatório por destino (`server`, `L0`, `L219`, `L325`) — `files` lista `COMMON_FILES` (todos) + `certs/generated` (só clientes) + `"requirements_installed": true"` (só clientes, Decisão 71).
**Critério de abortar:** qualquer `RuntimeError`.

---

## Passo 7 — `deliver_source.py --to-control`: `orchestrator.py` e dependências **[OPERADOR → CONTROLE]**

**O que é copiado pro controle agora** (`CONTROL_FILES`, Decisões 76/85 acrescentam os últimos itens desta lista):
- `campaign/scripts/{orchestrator,cli,preflight}.py`, `rehearsal_handshake.sh`
- `campaign/scripts/{dedicated_criteria,deliver_images}.py` (Decisão 85 — `orchestrator.py` agora importa `deliver_images` pro `BACKEND_IMAGE_KEYS`; `dedicated_criteria.py` roda do controle, mesma convenção)
- `campaign/PINS.json`, `integration/evaluate_criteria.py`
- `v8/campaign/scripts/redact_aws_errors.py`
- **`thesis/results/v9/certs/generated`** (Decisão 76 — o diagnóstico de bytes do smoke gate, Passo 10, lê isto do controle; sem isto, antes desta Decisão, quebrava com `FileNotFoundError` — agora, mesmo se faltasse, só pausaria o diagnóstico, nunca o gate oficial)
- `inventory.json` (copiado em separado)

```
python deliver_source.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --to-control --inventory-json /tmp/inventory.json
```
**Saída esperada:** `{"target": "control", "ip": "...", "files": [...]}` incluindo `thesis/results/v9/certs/generated`.
**Critério de abortar:** qualquer `RuntimeError`. Nunca fala com servidor/cliente.

---

## Passo 8 — `deliver_images.py`: as 4 imagens pinadas (gateway/proxy/pqc-signer/measure) **[OPERADOR → CONTROLE]**

```
python deliver_images.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador>
```
**Saída esperada:** JSON com `disk_check`, `images` (4 entradas, `sha256_ok: true`), `gateway_binary_info_delivered: true`.
**Critério de abortar:** qualquer `RuntimeError`.

**Não entregue aqui, de propósito (Decisão 57):** `mockopin-v9-negtest` — não é usada pelo piloto real (só pelo ensaio `rehearsal_handshake.sh`), nunca necessária neste roteiro.

## Passo 8b — `deliver_images.py --images`: as 3 imagens do backend de negócio (Decisão 83) **[OPERADOR → CONTROLE]**

**Achado real (Decisão 91, ao executar este roteiro de novo):** o default
de `--images` em `deliver_images.py` é `ALL_IMAGE_KEYS` (gateway/proxy/
pqc-signer/measure — nome enganoso, nunca incluiu o backend), nunca
`BACKEND_IMAGE_KEYS` (auth/mongo_seed/mockapi, Decisão 83/87) — o Passo
8 sozinho NUNCA entrega o backend. Sem este passo, `start_block`
(chamado já no Passo 10) quebra com `RuntimeError: _deliver_image(auth,
...): .../auth.tar nao encontrado no controle`.

```
python deliver_images.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --images auth mongo_seed mockapi
```
**Saída esperada:** JSON com `disk_check`, `images` (3 entradas — auth/
mongo_seed/mockapi, `sha256_ok: true`).
**Critério de abortar:** qualquer `RuntimeError`.

---

## Passo 9 — conferir `python3`/dependências do pipeline real no controle **[CONTROLE]**

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 --version
python3 orchestrator.py --help >/dev/null && echo "OK: orchestrator.py importa e roda"
REMOTE
```
**Saída esperada:** versão do Python 3, depois `OK: orchestrator.py importa e roda`.
**Nota (Decisão 76):** `evaluate_criteria.py` não depende mais de `cryptography` pro diagnóstico de bytes (trocado por `ssl.PEM_cert_to_DER_cert`, stdlib) — nenhum pacote de terceiros é necessário pra este passo.
**Critério de abortar:** qualquer traceback de import, ou `python3` ausente.

---

## Passo 10 — porta de fumaça: preflight de captura + 12 execuções (Decisão 48/53/55/76) **[CONTROLE]** 🔁

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
mkdir -p ~/campaign-data/v9/smoke
python3 orchestrator.py --mode ssh --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --images-staging-dir ~/images --smoke --out ~/campaign-data/v9/smoke
REMOTE
```
**O que roda, na ordem, automaticamente, dentro de UMA chamada**
(`run_smoke_gate`, nunca passos separados): (1) `capture_ready_
check()` — aborta ANTES de qualquer execução se tcpdump/sudo/imagem/
interface faltar; (2) 12 execuções (1 por perfil × rota, nunca
contam nas 60 oficiais); (3) 4 capturas de prova do mecanismo
(`smoke_capture_proof/`, nunca confundidas com as 12 oficiais do
critério 1); (4) diagnóstico de bytes por perfil (Decisão 76 —
NUNCA quebra mais o gate; qualquer desvio ou exceção só marca
`bytes_diagnostic_needs_decision`, pausa, nunca derruba `smoke_ok`).

**Saída esperada:** JSON com `"smoke_ok": true`, `"capture_preflight":
{"go": true, ...}`, `"capture_proof_ok": true`, `"total_execucoes":
12`. `"bytes_diagnostic_needs_decision"` pode vir `true` ou `false`
— **nunca**, por si só, motivo de abortar (é diagnóstico, nunca o
gate oficial).
**Critério de abortar:** `"smoke_ok": false` — o script PAUSA e sai
com código 1 por conta própria (nunca destrói nada automaticamente,
Decisão 49/Emenda 12). Decisão do Luciano: corrigir e repetir dentro
da janela de 4h, ou mandar destruir (Passo 14). Se o motivo for um
critério pré-registrado falhando com o código já verificado correto
— regra 7(a) desta autorização, STOP.

---

## Passo 11 — piloto real: 60 execuções + 12 capturas dedicadas **[CONTROLE]** 🔁

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
mkdir -p ~/campaign-data/v9/piloto
python3 orchestrator.py --mode ssh --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --images-staging-dir ~/images --out ~/campaign-data/v9/piloto
REMOTE
```
**Saída esperada:** JSON com `"total_execucoes": 60`, `"expected_total": 60`, `"total_capturas": 12`, `"smoke": false` — `manifest.json`/`piloto_combined.log`/`piloto_calls.json`/`criterio6_execucoes.json`/`criterio1_capturas/*.log` (12 arquivos) escritos em `~/campaign-data/v9/piloto/` (saída FLAT, Decisão 75/78 — nunca dividida por perfil).
**Critério de abortar:** qualquer exceção/`RuntimeError` (start_block, run_execution, dedicated_capture) — nenhuma correção de código no meio desta janela sem registrar Decisão numerada; se a correção alterar o que é medido, regra 7(e), STOP.

---

## Passo 11.5 — produtores dedicados dos critérios 2/3/7 (Decisão 85) **[CONTROLE]**

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 dedicated_criteria.py --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --dir ~/campaign-data/v9/piloto
REMOTE
```
**O que roda, na ordem:** critério 3 (local, reusa `evaluate_criteria.
criterion_4_counts` já escrito pelo Passo 11, filtra L325) → critério
2 (sobe `criterio2_probe.py` no servidor, dispara 1 conexão de teste
do cliente L219 via `/dev/tcp`, porta 9876) → critério 7 (por rota:
`probe` do cliente contra 443, `pcap` no servidor reaproveitando os
pcaps dedicados que o Passo 11 já escreveu em `/tmp`). Escreve
`criterio2_initcwnd.json`/`criterio3_l325_execucoes.json`/
`criterio7_rtt_por_rota.json` no MESMO diretório `~/campaign-data/v9/
piloto/` — um único pull no Passo 12 traz tudo junto.
**Saída esperada:** JSON com as 3 chaves (`criterio2`/`criterio3`/
`criterio7`), nenhuma vazia.
**Critério de abortar:** qualquer `RuntimeError` — nunca prossiga pro
Passo 12 com um dos 3 arquivos ausente (a consolidação reportaria
"sem evidência" silenciosamente, sem dizer que a causa foi este
passo falhando).

---

## Passo 12 — coleta com manifesto verificado (Decisão 78) **[OPERADOR → CONTROLE]**

```
python collect_artifacts.py --control-ip "$CONTROL_IP" --key <chave-do-operador> \
  --remote-dir ~/campaign-data/v9/piloto --local-dir /tmp/v9_piloto_coletado
```
**Saída esperada:** JSON com `"files_verified": N` (N = todos os arquivos do diretório: `manifest.json` + `piloto_combined.log` + `piloto_calls.json` + `criterio6_execucoes.json` + 12 de `criterio1_capturas/` + `criterio2_initcwnd.json` + `criterio3_l325_execucoes.json` + `criterio7_rtt_por_rota.json` + `manifest.sha256`), `.pull-verified` escrito em `/tmp/v9_piloto_coletado/`.
**Critério de abortar:** qualquer `RuntimeError` ("nao bate"/"ausente") — nunca confiar numa cópia parcial/corrompida.

---

## Passo 13 — consolidação final (Decisão 79) **[OPERADOR]**

```
python consolidate_v9_pilot.py \
  --collected-dir /tmp/v9_piloto_coletado \
  --out-dir ../../piloto/dados_oficiais/piloto-real-aws-<data-utc> \
  --run-label piloto-real-aws-<data-utc>
```
**Saída esperada:** `RELATORIO_PILOTO.md` + `criteria_evaluation.json` + `raw/` escritos em `thesis/results/v9/piloto/dados_oficiais/piloto-real-aws-<data>/`. **Esperado, por desenho, nesta rodada (Decisão 85 fechou o gap):** os 7 critérios avaliados de verdade sobre dados REAIS de AWS pela primeira vez na história deste pacote (PASS ou FAIL real por critério, nunca suposto, nunca "sem evidência"). `"all_criteria_pass"` reflete o resultado real — nem sempre `true` é esperado (um critério pode reprovar de verdade), mas nenhum deve reprovar por ARQUIVO AUSENTE.
**Critério de abortar:** nenhum — é só leitura/consolidação, nunca toca a fleet. Se algum dos 7 reprovar por "arquivo não encontrado" (em vez de um FAIL real com dados), volte ao Passo 11.5 — algo não rodou.

---

## Passo 14 — teardown **[OPERADOR]**

Mesma sequência dos Passos 11-13 de `INFRA_REHEARSAL.md`: `emergency_stop.py` modo dry (diagnóstico) → `cleanup.py --tf-dir ../../terraform --profile mockopin-pqc --release-eips --force` (principal, `all_clean: true` esperado) → `emergency_stop.py --execute` (fallback, só se `all_clean: false`).

---

## Passo 15 — verificação final: nada ficou na conta **[OPERADOR]**

As mesmas 12 chamadas do Passo 14 de `INFRA_REHEARSAL.md` (`describe-instances`/`describe-addresses`/`describe-security-groups`/`describe-key-pairs`, 3 regiões × 4 chamadas), independentes do `all_clean` auto-reportado pelo `cleanup.py`.
**Saída esperada:** as 12 chamadas devolvem listas **vazias**.
**Critério de abortar/alerta:** qualquer recurso ainda presente.

---

## Custo estimado do piloto

5 instâncias (4× `m7i-flex.large` + 1× `t4g.micro`) + 5 EIPs, janela
alvo de autodesligamento 4h, mas a execução real (apply → 60
execuções → coleta → cleanup) deve durar bem menos que isso — ordem
de grandeza esperada, por analogia ao ensaio de infraestrutura (~35
min pros Passos 0-10 dali) mais o tempo das 60 execuções/12 capturas
reais (nunca medido ainda, nenhuma execução real completa até
agora): estimativa de 1-2h de fleet.
- Compute: (4 × US$0,0958 + US$0,0084) × (1.5)h ≈ US$0,59
- EIP: 5 × US$0,005 × 1.5h ≈ US$0,04
- **Total estimado: ≈ US$0,6-1,2**, dentro do teto de US$5 desta autorização, somado ao já gasto na Fase A (~US$0,55).

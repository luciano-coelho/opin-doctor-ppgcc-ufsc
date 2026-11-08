# Ensaio de infraestrutura — ~30 minutos, sem experimento

Decisão 59 (correção do roteiro da Decisão 58 — achado real: o
operador NUNCA alcança o servidor/clientes direto numa AWS real, só o
controle alcança — `ssh_ingress_cidrs = {"control": ...}` em
`main.tf` — e o controle nunca roda `docker`, confirmado em
`PILOT_READINESS.md`. Isso bloqueava o piloto, não era trabalho
futuro — corrigido nesta rodada, modelo da v8 restaurado). **Cada
passo abaixo diz explicitamente EM QUE MÁQUINA roda** — "OPERADOR"
(o laptop do Luciano) ou "CONTROLE" (a instância `control`, única que
alcança servidor/clientes). Nenhum comando deste roteiro assume SSH
direto do operador pro servidor ou pra qualquer cliente — conferido
passo a passo contra `ssh_ingress_cidrs`/`gateway_ingress_cidrs` reais
de `main.tf`.

Usa as MESMAS credenciais e o MESMO profile AWS CLI já usados na v8
(`mockopin-pqc`). Objetivo: provar `terraform apply`/`destroy` reais,
a entrega completa do caminho remoto em 2 saltos (operador → controle
→ host, nunca operador → host direto), `orchestrator.py` rodando DE
VERDADE a partir do controle, um handshake real por perfil disparado
do controle, e a parada de emergência — nunca uma execução de
experimento (nenhuma das 60 execuções oficiais, nenhuma das 12
capturas do critério 1).

**Duração alvo: ~30 minutos de janela medida, ordem estritamente
linear (0→12, cada passo depende só do anterior).** `self_terminate_hours`
reduzido pra **1h** só pro ensaio (rede de segurança — nunca
pretendido pra durar isso; os passos 10-12 são o teardown real,
obrigatórios mesmo que o ensaio termine antes do autodesligamento).

| Convenção | Significado |
|---|---|
| **[OPERADOR]** | Roda no laptop do Luciano. Só pode SSH/SCP direto no CONTROLE (`ssh_ingress_cidrs = {"operator": var.operator_ip_cidr}`) — nunca no servidor/clientes. |
| **[CONTROLE]** | Roda DE DENTRO da instância `control` (via `ssh <control-ip> "<comando>"` disparado pelo operador). Alcança servidor/clientes porque `ssh_ingress_cidrs` deles só lista `{"control": "${module.control.public_ip}/32"}`. |

---

## Passo 0 — pré-requisitos **[OPERADOR]**

```
export TF_VAR_operator_ip_cidr="$(curl -s https://checkip.amazonaws.com)/32"
export TF_VAR_operator_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
cd thesis/results/v9/terraform
terraform init
```
**Saída esperada:** `Terraform has been successfully initialized!`
**Critério de abortar:** qualquer erro de init/provider.

---

## Passo 1 — `terraform plan`, depois `terraform apply` (`self_terminate_hours=1`) **[OPERADOR]**

**Contagem de recursos, derivada lendo `main.tf`/`modules/campaign_instance/main.tf`
diretamente (nunca suposta) — confirme o `terraform plan` real contra
isto:**

| Recurso | Quantidade | Onde |
|---|---|---|
| `tls_private_key.campaign` | 1 | `main.tf` |
| `aws_key_pair` | 4 | 3 regionais (`campaign_sa_east_1`/`eu_north_1`/`ap_southeast_1`) + 1 do operador |
| `aws_security_group.this` | 5 | 1 por módulo (`control`, `client_l0`, `client_eu_north_1`, `client_ap_southeast_1`, `server_sa_east_1`) |
| `aws_vpc_security_group_ingress_rule.ssh` | 5 | 1 por módulo (cada um tem exatamente 1 entrada em `ssh_ingress_cidrs`) |
| `aws_vpc_security_group_ingress_rule.gateway` | 3 | só `server_sa_east_1` (`role=="server"`) — 1 entrada por cliente (L0/L219/L325) |
| `aws_instance.this` | 5 | 1 por módulo |
| `aws_eip.this` | 5 | 1 por módulo |
| **Total** | **28** | |

```
terraform plan -var="self_terminate_hours=1"
```
**Saída esperada:** `Plan: 28 to add, 0 to change, 0 to destroy.` — se o número real divergir de 28, **pare e reconcilie antes do apply**.

```
terraform apply -var="self_terminate_hours=1" -auto-approve
```
**Saída esperada:** `Apply complete! Resources: 28 added, 0 changed, 0 destroyed.`
**Critério de abortar:** qualquer erro de apply, ou N ≠ 28 sem explicação — `terraform destroy -auto-approve` imediatamente, parar o ensaio.

**Conferência contra `ssh_ingress_cidrs`/`gateway_ingress_cidrs` (main.tf), pra todo o resto deste roteiro:**

| Recurso | SSH (22) aceito de | Gateway (443) aceito de |
|---|---|---|
| `control` | `var.operator_ip_cidr` (o OPERADOR) | n/a |
| `server_sa_east_1` | `module.control.public_ip` (SÓ o controle) | `client_l0` (IP privado), `client_eu_north_1`/`client_ap_southeast_1` (IP público) |
| `client_l0`/`client_eu_north_1`/`client_ap_southeast_1` | `module.control.public_ip` (SÓ o controle) | n/a (eles discam, não recebem) |

**Nenhuma linha desta tabela lista o operador como origem de SSH pro
servidor ou pra qualquer cliente** — todo passo abaixo que fala com
servidor/cliente tem que rodar **[CONTROLE]**, nunca **[OPERADOR]**.

---

## Passo 2 — confirmar as 5 instâncias via `describe-instances` **[OPERADOR]**

```
terraform output -json inventory
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 \
  --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" \
  --query "Reservations[].Instances[].State.Name"
```
(repetir para `eu-north-1`/`ap-southeast-1`, 1 instância cada — total 5)

**Saída esperada:** `inventory` com os 5 IPs; cada `describe-instances` devolve `"running"`.
**Critério de abortar:** qualquer instância fora de `running`/`pending` por mais de 2 minutos.
**Por que roda no operador:** API da AWS direta, nenhum SSH a instância alguma — sem restrição de Security Group.

---

## Passo 3 — entregar a chave SSH da campanha pro controle **[OPERADOR → CONTROLE]** (NOVO, achado real desta rodada)

**Por que este passo existe:** `pki_relay.py`/`deliver_source.py`
(segundo salto)/`orchestrator.py` (rodando do controle, Passo 7) TODOS
assumem `~/.ssh/campaign_key` já presente no controle — **nenhum
script deste pacote jamais o entregava** (a chave é um `output`
sensível do Terraform, `tls_private_key.campaign.private_key_openssh`,
nunca escrito em arquivo pelo próprio Terraform). Mesmo padrão real
da v8 (`campaign_up.sh`: `scp "$TMP_KEY" "ec2-user@${CONTROL_IP}:~/.ssh/campaign_key"`).
Sem este passo, **nenhum** passo abaixo que fala com servidor/cliente
funciona.

```
cd ../campaign/scripts
terraform -chdir=../../terraform output -raw campaign_private_key | \
  python pki_relay.py --control-ip <IP-controle> --operator-key <chave-do-operador> \
  --deliver-campaign-key --inventory-json <(echo '{}')
```
**Saída esperada:** JSON com `"campaign_key_remote_path": "/home/ec2-user/.ssh/campaign_key"`.
**Critério de abortar:** qualquer `RuntimeError` — nenhum passo seguinte pode prosseguir sem isso.
**Nunca impresso:** o conteúdo da chave nunca aparece em nenhuma saída deste script, nem em `calls` nos testes (`test_deliver_campaign_key_um_so_salto_nunca_imprime_o_conteudo`) — só o caminho de destino.

---

## Passo 4 — Docker pronto + porta, nas 5 instâncias **[CONTROLE para servidor/clientes; OPERADOR só pro controle]**

**Controle (o único que o operador pode checar direto):**
```
ssh -i <chave-do-operador> ec2-user@<IP-controle> "docker info >/dev/null 2>&1 && echo 'Docker pronto (controle)'"
```

**Servidor/clientes — via relé pelo controle, usando a chave da campanha já entregue no Passo 3 (NUNCA SSH direto do operador):**
```
ssh -i <chave-do-operador> ec2-user@<IP-controle> bash -s <<'REMOTE'
for IP in <EIP-servidor> <IP-cliente-L0> <IP-cliente-L219> <IP-cliente-L325>; do
  echo "=== $IP ==="
  for i in $(seq 1 20); do
    ssh -i ~/.ssh/campaign_key -o StrictHostKeyChecking=no ec2-user@$IP "docker info >/dev/null 2>&1" && { echo "Docker pronto"; break; }
    sleep 3
  done
done
REMOTE
```
**Saída esperada:** `"Docker pronto"` pras 5 instâncias, dentro de 20 tentativas (~60s) cada.
**Critério de abortar:** qualquer instância sem Docker pronto depois de 20 tentativas.

**Porta usada = porta da regra de ingress do Security Group (confirmado no Passo 1):** SSH 22 (só controle→host); gateway 443 (só cliente→servidor, nunca SSH).

---

## Passo 5 — `deliver_source.py`: código-fonte e certificados **[OPERADOR → CONTROLE → servidor/clientes]**

Ships `thesis/scripts/*.py`, `mock-service-os/certs` (servidor + todo
cliente) e `thesis/results/v9/certs/generated` (só clientes) — achado
real já corrigido na Decisão 58 (ver DECISIONS.md). Mesmo relé de 2
saltos: hop 1 (operador→controle) e hop 2 (controle→host, com a
chave da campanha do Passo 3) rodam dentro da MESMA chamada deste
script, disparada **[OPERADOR]**:

```
INVENTORY_JSON=$(terraform -chdir=../../terraform output -json inventory | python -c "import json,sys; raw=json.load(sys.stdin); print(json.dumps(raw['value'] if 'value' in raw else raw))")
echo "$INVENTORY_JSON" > /tmp/inventory.json

python deliver_source.py --control-ip <IP-controle> --operator-key <chave-do-operador> \
  --inventory-json /tmp/inventory.json
```
**Saída esperada:** relatório por destino (`server`, `L0`, `L219`, `L325`) com `files` listando os caminhos entregues.
**Critério de abortar:** qualquer `RuntimeError`.

---

## Passo 6 — `deliver_source.py --to-control`: `orchestrator.py` e o que ele precisa **[OPERADOR → CONTROLE]** (1 salto só)

**O que é copiado pro controle, exatamente** (`CONTROL_FILES`, `deliver_source.py`):
- `thesis/results/v9/campaign/scripts/orchestrator.py`
- `thesis/results/v9/campaign/scripts/cli.py`
- `thesis/results/v9/campaign/scripts/preflight.py`
- `thesis/results/v9/campaign/scripts/rehearsal_handshake.sh`
- `thesis/results/v9/campaign/PINS.json`
- `thesis/results/v9/integration/evaluate_criteria.py`
- `inventory.json` (copiado em separado — não é um arquivo do repositório, é gerado por `terraform output`)

```
python deliver_source.py --control-ip <IP-controle> --operator-key <chave-do-operador> \
  --to-control --inventory-json /tmp/inventory.json
```
**Saída esperada:** `{"target": "control", "ip": "<IP-controle>", "files": [...]}`.
**Critério de abortar:** qualquer `RuntimeError`. **Nunca fala com servidor/cliente nenhum** (confirmado por teste, `test_deliver_to_control_um_so_salto_nunca_fala_com_servidor_ou_cliente`).

Depois deste passo, `orchestrator.py` existe em
`~/thesis/results/v9/campaign/scripts/orchestrator.py` no CONTROLE —
é de lá que ele roda nos Passos 7/8/9 abaixo, nunca do laptop do
operador (Security Group do servidor/clientes não permite).

---

## Passo 7 — `deliver_images.py`: as 4 imagens, 1º salto (operador → controle) **[OPERADOR → CONTROLE]**

**Modelo restaurado da v8** (achado real: `docker save <imagem> | ssh
<host> docker load`, Decisão 55, exigia Docker na máquina que executa
esse comando — e essa máquina passou a ser o CONTROLE, que nunca tem
Docker). Agora em 2 saltos reais:

```
time python deliver_images.py --control-ip <IP-controle> --operator-key <chave-do-operador>
```
**O que este passo faz, na ordem:** `docker save` de cada imagem em
`.tar` (local, no operador) → extrai o binário do gateway e confere
sha256 contra `PINS.json` (local, no operador — nunca no controle) →
checa espaço em disco no controle (`df`, real — o volume é `gp3` de
30GB, confirmado em `main.tf`, folga enorme pros ~140MB totais
medidos nesta sessão: gateway ~10MB, proxy ~9MB, pqc-signer ~59MB,
measure ~58MB) → scp dos `.tar`+`.sha256` pro controle → `sha256sum -c`
no controle.

**Saída esperada:** JSON com `disk_check` (`avail_kb`/`needed_kb`),
`images` (4 entradas, `sha256_ok: true` cada), `gateway_binary_info_delivered: true`.
**Critério de abortar:** qualquer `RuntimeError` — nenhuma imagem incompleta/corrompida pode ficar estagiada no controle.

**Tempo medido por imagem (preencher durante o ensaio real):**

| Imagem | Tamanho do `.tar` (medido nesta sessão) | Tempo operador→controle |
|---|---|---|
| gateway | ~10MB | _a preencher_ |
| proxy | ~9MB | _a preencher_ |
| pqc-signer | ~59MB | _a preencher_ |
| measure | ~58MB | _a preencher_ |

**Nenhum `docker run`, nenhuma conexão mTLS ainda — só o 1º salto da entrega.**

---

## Passo 8 — `orchestrator.py --exercise-start-stop`: 2º salto (controle → host) + start_block/stop_block reais **[CONTROLE]**

**Por que isto prova o 2º salto também:** `SSHExecutor._deliver_image`
(dentro de `start_block`, chamado por este exercício) faz o resto —
scp do `.tar` já estagiado no controle (Passo 7) pro HOST, `ssh host
docker load`, `docker image inspect` comparado contra `PINS.json`
(fail-closed). Prova as 3 imagens com pin (`gateway`/`proxy`/
`pqc-signer`) de uma vez, mais a sondagem TCP (achado 18) e o
binário do gateway (Decisão 54), sem nenhuma execução cronometrada.

```
ssh -i <chave-do-operador> ec2-user@<IP-controle> bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 orchestrator.py --mode ssh \
  --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --exercise-start-stop --exercise-profile classico --exercise-route L0
REMOTE
```
**Saída esperada:** JSON com `"start_block_ok": true`, `"stop_block_ok": true`,
`gateway_binary_verifications` (1 entrada, `pin_matched: true`,
`running_container_sha256_ok: true`), `image_delivery_verifications`
(3 entradas — gateway/proxy/pqc-signer — `"ok": true`),
`tcp_preflight_results` (1 entrada, `"ok": true`).

Confirme manualmente, numa segunda sessão **[CONTROLE]** durante a
chamada acima, que os 3 containers existem enquanto o comando roda:
```
ssh -i <chave-do-operador> ec2-user@<IP-controle> \
  "ssh -i ~/.ssh/campaign_key ec2-user@<EIP-servidor> docker ps -a --filter name=v9-mtls"
ssh -i <chave-do-operador> ec2-user@<IP-controle> \
  "ssh -i ~/.ssh/campaign_key ec2-user@<IP-cliente-L0> docker ps -a --filter name=tls_kem_proxy_run --filter name=pqc_signer_service_run"
```
**Critério de abortar:** qualquer campo `"ok": false`/exceção. **Nenhum
arquivo de manifesto/execução é escrito por este passo** (testado,
`test_exercise_start_stop_sobe_e_desce_sem_execucao_nem_manifest`) —
nunca conta como nenhuma das 60/12 oficiais. **Nenhuma chamada invoca
`docker` localmente no controle** (testado,
`test_deliver_image_nunca_invoca_docker_localmente`).

---

## Passo 9 — handshake real por perfil (4, prova de mecanismo) **[CONTROLE]**

**Testado localmente em loopback antes de ser entregue** (ainda no
laptop do operador, pura validação Docker local, sem AWS — saída real
desta sessão):
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

**No ensaio real (AWS), o script roda DE DENTRO DO CONTROLE (achado
real desta rodada — `GATEWAY_SSH`/`CLIENT_SSH` apontados pro
servidor/cliente direto, do laptop do operador, violaria o Security
Group — Passo 1). `rehearsal_handshake.sh` já chegou no controle via
Passo 6.** `mockopin-v9-negtest`, que o script usa no cliente, não é
pinada em `PINS.json` (motivo já registrado na Decisão 57: nenhum
código de produção a usa) — entregue aqui por um 2º salto manual,
igual em espírito a `deliver_images.py` mas sem passar por PINS.json:

```
# 1o salto (operador -> controle), [OPERADOR]:
docker save mockopin-v9-negtest > /tmp/negtest.tar
scp -i <chave-do-operador> /tmp/negtest.tar ec2-user@<IP-controle>:~/images/negtest.tar

# 2o salto (controle -> cliente L0) + o ensaio em si, tudo [CONTROLE]:
ssh -i <chave-do-operador> ec2-user@<IP-controle> bash -s <<'REMOTE'
scp -i ~/.ssh/campaign_key ~/images/negtest.tar ec2-user@<IP-cliente-L0>:~/negtest.tar
ssh -i ~/.ssh/campaign_key ec2-user@<IP-cliente-L0> "docker load < ~/negtest.tar && rm -f ~/negtest.tar"

cd ~/thesis/results/v9/campaign/scripts
GATEWAY_SSH="ssh -i ~/.ssh/campaign_key ec2-user@<EIP-servidor>" \
CLIENT_SSH="ssh -i ~/.ssh/campaign_key ec2-user@<IP-cliente-L0>" \
GATEWAY_HOST="<EIP-servidor>" \
bash rehearsal_handshake.sh
REMOTE
```
**Saída esperada:** `RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos` — igual ao teste local, agora numa rede/instâncias reais, disparado do controle.
**Critério de abortar:** qualquer `FALHA` impressa pelo script, ou `RESULTADO FINAL: FAIL` — marca o ensaio como **reprovado neste ponto**, registrado explicitamente, antes de seguir pro passo 10.

**O que este passo NÃO faz:** não conta como nenhuma das 60 execuções oficiais nem nenhuma das 12 capturas do critério 1.

---

## Passo 10 — `emergency_stop.py`, modo dry **[OPERADOR]** (diagnóstico, antes de qualquer teardown)

```
cd ../campaign/scripts
python emergency_stop.py --profile mockopin-pqc
```
**Saída esperada:** `instances_found`/`eips_found`/`security_groups_found`/`key_pairs_found` listando os recursos reais do ensaio (4 key pairs, corrigido na Decisão 57), e todas as listas `..._terminated`/`..._released`/`..._deleted` **vazias**.
**Critério de abortar:** qualquer lista de ação não-vazia em modo dry.
**Por que roda no operador:** API da AWS direta, nenhum SSH a instância alguma.

---

## Passo 11 — teardown PRINCIPAL: `cleanup.py --release-eips --force` **[OPERADOR]**

**Por que `cleanup.py`, não `emergency_stop.py`, é o caminho principal**
(comparado linha a linha contra `v8/campaign/scripts/campaign_down.sh`
na Decisão 57): mesmos 5 checks estruturais, mas `cleanup.py` tem 2
capacidades novas — detecção de drift por autodesligamento ANTES do
destroy, e liberação ATIVA de EIPs órfãos (`--release-eips`).

**Redação de erros da AWS:** já confirmada presente (Decisão 58) —
`cli.run_terraform`/`cli.run_aws`/`cli.run_aws_json` redigem
`stdout`/`stderr` antes de devolver ou levantar, nenhuma mudança
necessária.

```
python cleanup.py --tf-dir ../../terraform --profile mockopin-pqc --release-eips --force
```
**Saída esperada:** JSON com `"all_clean": true`.
**Critério de abortar:** `all_clean: false`, ou qualquer excessão — ir pro passo 12 (fallback), nunca pular direto pro passo 13.
**Por que roda no operador:** `terraform destroy` precisa do state local; a verificação é API da AWS direta.

---

## Passo 12 — fallback: `emergency_stop.py --execute`, só se sobrou algo **[OPERADOR]**

**Só roda se o passo 11 reportou `all_clean: false`.** Se já deu `all_clean: true`, pule direto pro passo 13.

```
python emergency_stop.py --profile mockopin-pqc --execute
```
**Saída esperada:** qualquer recurso que o passo 11 não limpou aparece em `..._terminated`/`..._released`/`..._deleted` agora.
**Critério de abortar:** qualquer erro de permissão persistente — investigação manual pela console AWS.

---

## Passo 13 — verificação final: nada ficou na conta **[OPERADOR]**

```
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" "Name=instance-state-name,Values=running,pending,stopping,stopped"
aws ec2 describe-addresses --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
aws ec2 describe-security-groups --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
aws ec2 describe-key-pairs --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
```
(repetir as 4 chamadas para `eu-north-1`/`ap-southeast-1` — 12 chamadas no total)

**Saída esperada:** as 12 chamadas devolvem listas **vazias**.
**Critério de abortar/alerta:** qualquer recurso ainda presente.

---

## Custo estimado do ensaio

~30 minutos de frota (passos 0-13, +5 min sobre a Decisão 58 pelos
passos novos: entrega da chave da campanha, 2 saltos reais de
entrega de imagem) — 5 instâncias: 4× `m7i-flex.large` + 1× `t4g.micro` — + 5 EIPs:
- Compute: (4 × US$0,0958 + US$0,0084) × (30/60)h ≈ US$0,197
- EIP: 5 × US$0,005 × (30/60)h ≈ US$0,013
- EBS: negligível (apagado junto no destroy/termination)
- **Total estimado: ≈ US$0,21**, mesmo no dobro do tempo (60 min): ≈ US$0,42.

**Se algo falhar e o self_terminate de 1h disparar antes da limpeza manual:** custo sobe para ~2× o acima (≈US$0,42 de compute) — os EIPs seguem o mesmo risco residual já documentado, coberto tanto por `cleanup.py --release-eips` (principal) quanto por `emergency_stop.py` (fallback).

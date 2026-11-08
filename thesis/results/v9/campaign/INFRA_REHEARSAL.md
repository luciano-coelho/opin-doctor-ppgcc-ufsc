# Ensaio de infraestrutura — ~35 minutos, sem experimento

Decisão 60 (correção do roteiro da Decisão 59 — 5 ajustes pedidos +
1 achado adicional da mesma classe, encontrado corrigindo o item 2):
geração do `inventory.json` antecipada e verificada contra o formato
real que os scripts leem; endereço do servidor no handshake lido do
inventário (nunca digitado — L0 é co-localizado e disca o IP
PRIVADO, não o EIP); o laço de "Docker pronto" agora falha alto com o
host no erro; a entrega de imagem (2º salto) agora reporta tempo e
Image ID por host, com critério de abortar por demora; passo novo
antes do exercício remoto, confirmando que `orchestrator.py` importa
de verdade no controle. **Cada passo abaixo diz explicitamente EM QUE
MÁQUINA roda** — "OPERADOR" (o laptop do Luciano) ou "CONTROLE" (a
instância `control`, única que alcança servidor/clientes). Nenhum
endereço deste roteiro é digitado à mão — todos vêm de
`/tmp/inventory.json` (operador) ou da cópia local dele no controle
(`inventory.json`, entregue no Passo 6).

Usa as MESMAS credenciais e o MESMO profile AWS CLI já usados na v8
(`mockopin-pqc`). Objetivo: provar `terraform apply`/`destroy` reais,
a entrega completa do caminho remoto em 2 saltos (operador → controle
→ host, nunca operador → host direto), `orchestrator.py` rodando DE
VERDADE a partir do controle, um handshake real por perfil disparado
do controle pro MESMO endereço que a rota real disca, e a parada de
emergência — nunca uma execução de experimento (nenhuma das 60
execuções oficiais, nenhuma das 12 capturas do critério 1).

**Duração alvo: ~35 minutos de janela medida, ordem estritamente
linear (0→14, cada passo depende só do anterior).** `self_terminate_hours`
reduzido pra **1h** só pro ensaio (rede de segurança — nunca
pretendido pra durar isso; os passos 11-14 são o teardown real,
obrigatórios mesmo que o ensaio termine antes do autodesligamento).

| Convenção | Significado |
|---|---|
| **[OPERADOR]** | Roda no laptop do Luciano. Só pode SSH/SCP direto no CONTROLE (`ssh_ingress_cidrs = {"operator": var.operator_ip_cidr}`) — nunca no servidor/clientes. |
| **[CONTROLE]** | Roda DE DENTRO da instância `control` (via `ssh $CONTROL_IP "<comando>"` disparado pelo operador). Alcança servidor/clientes porque `ssh_ingress_cidrs` deles só lista `{"control": "${module.control.public_ip}/32"}`. |

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

## Passo 2 — confirmar instâncias + gerar e verificar `/tmp/inventory.json` **[OPERADOR]**

```
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 \
  --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" \
  --query "Reservations[].Instances[].State.Name"
```
(repetir para `eu-north-1`/`ap-southeast-1`, 1 instância cada — total 5)
**Saída esperada:** cada `describe-instances` devolve `"running"`.
**Critério de abortar:** qualquer instância fora de `running`/`pending` por mais de 2 minutos.

**Gera `/tmp/inventory.json` AGORA (não só no Passo 5 — todo passo
seguinte que precisa de um endereço lê daqui, nunca digitado à mão) e
confere o formato contra o que `deliver_source.py`/`pki_relay.py`/
`orchestrator.py` realmente leem** (`inventory["server"]["public_ip"
/"private_ip"]`, `inventory["clients"][rota]["public_ip"/"private_ip"
/"colocated"]`, `inventory["control"]["public_ip"]` — confirmado
lendo os 3 arquivos: todos esperam o dict JÁ DESEMBRULHADO, por isso
a extração de `"value"` abaixo — `terraform output -json <nome>`,
pra um output NOMEADO, sempre embrulha em `{"sensitive":...,
"value":...}`):
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
**Saída esperada:** `formato OK -- server/clients/control presentes, salvo em /tmp/inventory.json`.
**Critério de abortar:** qualquer `AssertionError` — o formato real divergiu do que os scripts esperam, investigar ANTES de usar o arquivo em qualquer passo seguinte.

**Variáveis usadas no resto deste roteiro — SEMPRE lidas de
`/tmp/inventory.json`, nunca digitadas à mão:**
```
CONTROL_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['control']['public_ip'])")
SERVER_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['server']['public_ip'])")
L0_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['clients']['L0']['public_ip'])")
L219_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['clients']['L219']['public_ip'])")
L325_IP=$(python3 -c "import json; print(json.load(open('/tmp/inventory.json'))['clients']['L325']['public_ip'])")
```

---

## Passo 3 — entregar a chave SSH da campanha pro controle **[OPERADOR → CONTROLE]**

**Por que este passo existe:** `pki_relay.py`/`deliver_source.py`
(segundo salto)/`orchestrator.py` (rodando do controle) TODOS assumem
`~/.ssh/campaign_key` já presente no controle — **nenhum script deste
pacote jamais o entregava** (a chave é um `output` sensível do
Terraform, nunca escrito em arquivo pelo próprio Terraform). Mesmo
padrão real da v8 (`campaign_up.sh`). Sem este passo, **nenhum** passo
abaixo que fala com servidor/cliente funciona.

```
terraform -chdir=../../terraform output -raw campaign_private_key | \
  python pki_relay.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --deliver-campaign-key --inventory-json /tmp/inventory.json
```
(`--inventory-json` é exigido pelo argparse mas nunca lido neste modo — passar o arquivo real já gerado no Passo 2 em vez de um placeholder vazio.)

**Saída esperada:** JSON com `"campaign_key_remote_path": "/home/ec2-user/.ssh/campaign_key"`.
**Critério de abortar:** qualquer `RuntimeError`.
**Nunca impresso:** o conteúdo da chave nunca aparece em nenhuma saída deste script (`test_deliver_campaign_key_um_so_salto_nunca_imprime_o_conteudo`).

---

## Passo 4 — Docker pronto + porta, nas 5 instâncias **[CONTROLE para servidor/clientes; OPERADOR só pro controle]**

**Controle:**
```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" "docker info >/dev/null 2>&1 && echo 'Docker pronto (controle)'"
```

**Servidor/clientes — via relé, usando a chave da campanha (Passo 3).
Correção desta rodada: o laço agora FALHA ALTO (exit code ≠ 0,
mensagem com o(s) host(s) que não ficaram prontos) em vez de só
seguir em frente silenciosamente se algum nunca ficar pronto:**
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
**Saída esperada:** `"Docker pronto: <IP>"` pras 5 instâncias (controle + as 4 acima).
**Critério de abortar:** exit code ≠ 0 do bloco acima — a mensagem já diz exatamente qual(is) host(s) falhou(aram).

**Porta usada = porta da regra de ingress do Security Group (confirmado no Passo 1):** SSH 22 (só controle→host); gateway 443 (só cliente→servidor, nunca SSH).

---

## Passo 5 — `deliver_source.py`: código-fonte e certificados **[OPERADOR → CONTROLE → servidor/clientes]**

```
python deliver_source.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --inventory-json /tmp/inventory.json
```
**Saída esperada:** relatório por destino (`server`, `L0`, `L219`, `L325`) com `files` listando os caminhos entregues (`certs/generated` só para os 3 clientes).
**Critério de abortar:** qualquer `RuntimeError`.

---

## Passo 6 — `deliver_source.py --to-control`: `orchestrator.py` e o que ele precisa **[OPERADOR → CONTROLE]** (1 salto só)

**O que é copiado pro controle, exatamente** (`CONTROL_FILES`, `deliver_source.py`):
- `thesis/results/v9/campaign/scripts/{orchestrator,cli,preflight}.py`
- `thesis/results/v9/campaign/scripts/rehearsal_handshake.sh`
- `thesis/results/v9/campaign/PINS.json`
- `thesis/results/v9/integration/evaluate_criteria.py`
- `inventory.json` (copiado em separado — não é um arquivo do repositório)

```
python deliver_source.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador> \
  --to-control --inventory-json /tmp/inventory.json
```
**Saída esperada:** `{"target": "control", "ip": "...", "files": [...]}`.
**Critério de abortar:** qualquer `RuntimeError`. **Nunca fala com servidor/cliente nenhum** (`test_deliver_to_control_um_so_salto_nunca_fala_com_servidor_ou_cliente`).

Depois deste passo, `orchestrator.py` existe em
`~/thesis/results/v9/campaign/scripts/orchestrator.py` no CONTROLE,
junto com a própria cópia dele de `inventory.json` — é de lá que os
Passos 8/9/10 abaixo leem endereços, nunca do operador.

---

## Passo 7 — `deliver_images.py`: as 4 imagens, 1º salto (operador → controle) **[OPERADOR → CONTROLE]**

```
time python deliver_images.py --control-ip "$CONTROL_IP" --operator-key <chave-do-operador>
```
**O que este passo faz, na ordem:** `docker save` de cada imagem em
`.tar` (local, no operador) → extrai o binário do gateway e confere
sha256 contra `PINS.json` (local, no operador) → checa espaço em
disco no controle (`df`, real — volume `gp3` de 30GB, folga enorme
pros ~140MB totais medidos nesta sessão: gateway ~10MB, proxy ~9MB,
pqc-signer ~59MB, measure ~58MB) → scp pro controle → `sha256sum -c` lá.

**Saída esperada:** JSON com `disk_check`, `images` (4 entradas, `sha256_ok: true`), `gateway_binary_info_delivered: true`.
**Critério de abortar:** qualquer `RuntimeError`.

**Nenhum `docker run`, nenhuma conexão mTLS ainda — só o 1º salto da entrega.**

---

## Passo 8 — conferir `python3` e as dependências de `orchestrator.py` no controle **[CONTROLE]** (NOVO)

**Por que `--help` já basta:** `cli`/`preflight`/`evaluate_criteria`
são importados no TOPO do módulo `orchestrator.py` (fora de qualquer
função, linhas antes de `def main()`) — se QUALQUER um desses
imports falhar, `python3 orchestrator.py --help` nunca chega a
imprimir o usage, quebra com o traceback de import antes disso.
Conferido lendo os 3 arquivos linha por linha: **nenhum importa
pacote de terceiros** — só biblioteca padrão (`argparse`/`json`/`re`/
`subprocess`/`sys`/`pathlib`/`collections`/`random`/`datetime`/
`time`). Não há, portanto, nenhum pacote `pip` necessário aqui.

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 --version
python3 orchestrator.py --help >/dev/null && echo "OK: orchestrator.py importa e roda"
REMOTE
```
**Saída esperada:** a versão do Python 3, depois `OK: orchestrator.py importa e roda`.
**Se faltar algo:** como nenhum dos 3 módulos usa pacote de terceiros,
a única causa real é `python3` ausente/quebrado no Amazon Linux 2023
ARM64 (o controle é `t4g.micro`) — `install_common_packages.sh` já
instala `python3-pip` (que traz `python3` como dependência) em TODA
instância, controle incluso, então isso não deveria faltar; se
faltar mesmo assim: `sudo dnf install -y python3`. **Nunca rode `pip
install` aqui** — não há dependência de terceiros a instalar.
**Critério de abortar:** qualquer traceback de import, ou `python3`
ausente — resolver ANTES do Passo 9 (nenhum exercício real
funcionaria mesmo assim).

---

## Passo 9 — `orchestrator.py --exercise-start-stop`: 2º salto (controle → host) + start_block/stop_block reais **[CONTROLE]**

**Por que isto prova o 2º salto também:** `SSHExecutor._deliver_image`
(dentro de `start_block`, chamado por este exercício) faz o resto —
scp do `.tar` já estagiado no controle (Passo 7) pro HOST, `ssh host
docker load`, `docker image inspect` comparado contra `PINS.json`
(fail-closed). Prova as 3 imagens com pin (`gateway`/`proxy`/
`pqc-signer`) de uma vez, mais a sondagem TCP (achado 18) e o
binário do gateway (Decisão 54), sem nenhuma execução cronometrada.

```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" bash -s <<'REMOTE'
cd ~/thesis/results/v9/campaign/scripts
python3 orchestrator.py --mode ssh \
  --inventory-json inventory.json --ssh-key ~/.ssh/campaign_key \
  --exercise-start-stop --exercise-profile classico --exercise-route L0 > /tmp/exercise_report.json
cat /tmp/exercise_report.json
echo "--- tempo/Image ID de entrega por imagem (2o salto, controle->host) ---"
python3 -c "
import json
r = json.load(open('/tmp/exercise_report.json'))
for v in r['image_delivery_verifications']:
    print(f\"{v['image_key']:12s} host={v['host']:16s} elapsed={v['elapsed_seconds']:>7.1f}s \"
          f\"tar={v['tar_bytes']} bytes ok={v['ok']} slow={v['slow']} \"
          f\"image_id_ok={v['loaded_image_id'] == v['expected_image_id']}\")"
REMOTE
```
**Saída esperada:** JSON com `"start_block_ok": true`, `"stop_block_ok": true`,
`gateway_binary_verifications` (1 entrada, `pin_matched: true`,
`running_container_sha256_ok: true`), seguido da listagem de tempo/
Image ID por imagem (gateway/proxy/pqc-signer), nenhuma com
`slow: true`, todas com `ok: true`/`image_id_ok: true`, e
`tcp_preflight_results` (1 entrada, `"ok": true`).

Confirme manualmente, numa segunda sessão **[CONTROLE]** durante a
chamada acima, que os 3 containers existem enquanto o comando roda:
```
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" "ssh -i ~/.ssh/campaign_key ec2-user@$SERVER_IP docker ps -a --filter name=v9-mtls"
ssh -i <chave-do-operador> ec2-user@"$CONTROL_IP" "ssh -i ~/.ssh/campaign_key ec2-user@$L0_IP docker ps -a --filter name=tls_kem_proxy_run --filter name=pqc_signer_service_run"
```
**Critério de abortar:** qualquer `"ok": false`/exceção; **OU
qualquer entrega com `elapsed_seconds` > 600 (10 minutos, `"slow":
true`)** — sintoma de link controle↔host degradado, nunca prosseguir
pro resto do ensaio sem investigar antes. **Nenhum arquivo de
manifesto/execução é escrito por este passo**
(`test_exercise_start_stop_sobe_e_desce_sem_execucao_nem_manifest`) —
nunca conta como nenhuma das 60/12 oficiais. **Nenhuma chamada invoca
`docker` localmente no controle**
(`test_deliver_image_nunca_invoca_docker_localmente`).

---

## Passo 10 — handshake real por perfil (4, prova de mecanismo) **[CONTROLE]**

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

**Correção desta rodada (item 2): o endereço de `GATEWAY_HOST` tem
que ser o MESMO que a rota L0 realmente disca em produção
(`orchestrator._server_gateway_ip`) — conferido em `outputs.tf`: L0 é
`colocated: true` (mesma AZ ID que o servidor), então disca o IP
PRIVADO do servidor, nunca o EIP. Calculado abaixo a partir da cópia
local de `inventory.json` no controle (entregue no Passo 6), nunca
digitado à mão — o mesmo vale pros endereços de `GATEWAY_SSH`/
`CLIENT_SSH` (sempre o IP PÚBLICO, pra SSH — Decisão 43/45) e pro 2º
salto de entrega do `negtest` abaixo, que também estavam com
placeholders fixos antes desta correção.**

`mockopin-v9-negtest` não é pinada em `PINS.json` (motivo já
registrado na Decisão 57) — entregue aqui por um 2º salto manual,
igual em espírito a `deliver_images.py` mas sem passar por PINS.json:

```
# 1o salto (operador -> controle), [OPERADOR]:
docker save mockopin-v9-negtest > /tmp/negtest.tar
scp -i <chave-do-operador> /tmp/negtest.tar ec2-user@"$CONTROL_IP":~/images/negtest.tar

# 2o salto (controle -> cliente L0) + o ensaio em si, tudo [CONTROLE] --
# endereços recalculados AQUI a partir da copia local de inventory.json,
# nunca recebidos como placeholder do operador:
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
**Saída esperada:** `RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos` — igual ao teste local, agora numa rede/instâncias reais, disparado do controle, discando o MESMO endereço que a rota real usa.
**Critério de abortar:** qualquer `FALHA` impressa pelo script, ou `RESULTADO FINAL: FAIL` — marca o ensaio como **reprovado neste ponto**, registrado explicitamente, antes de seguir pro passo 11.

**O que este passo NÃO faz:** não conta como nenhuma das 60 execuções oficiais nem nenhuma das 12 capturas do critério 1.

---

## Passo 11 — `emergency_stop.py`, modo dry **[OPERADOR]** (diagnóstico, antes de qualquer teardown)

```
python emergency_stop.py --profile mockopin-pqc
```
**Saída esperada:** `instances_found`/`eips_found`/`security_groups_found`/`key_pairs_found` listando os recursos reais do ensaio (4 key pairs, corrigido na Decisão 57), e todas as listas `..._terminated`/`..._released`/`..._deleted` **vazias**.
**Critério de abortar:** qualquer lista de ação não-vazia em modo dry.

---

## Passo 12 — teardown PRINCIPAL: `cleanup.py --release-eips --force` **[OPERADOR]**

**Por que `cleanup.py`, não `emergency_stop.py`, é o caminho
principal** (Decisão 57): mesmos 5 checks estruturais da v8, mas
`cleanup.py` detecta drift por autodesligamento ANTES do destroy e
libera ATIVAMENTE EIPs órfãos.

```
python cleanup.py --tf-dir ../../terraform --profile mockopin-pqc --release-eips --force
```
**Saída esperada:** JSON com `"all_clean": true`.
**Critério de abortar:** `all_clean: false` — ir pro passo 13 (fallback), nunca pular direto pro passo 14.

---

## Passo 13 — fallback: `emergency_stop.py --execute`, só se sobrou algo **[OPERADOR]**

**Só roda se o passo 12 reportou `all_clean: false`.** Se já deu `all_clean: true`, pule direto pro passo 14.

```
python emergency_stop.py --profile mockopin-pqc --execute
```
**Saída esperada:** qualquer recurso que o passo 12 não limpou aparece em `..._terminated`/`..._released`/`..._deleted` agora.
**Critério de abortar:** qualquer erro de permissão persistente — investigação manual pela console AWS.

---

## Passo 14 — verificação final: nada ficou na conta **[OPERADOR]**

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

~35 minutos de frota (passos 0-14, +5 min sobre a Decisão 59 pelo
passo novo de conferência de dependências e pela checagem extra de
tempo/Image ID) — 5 instâncias: 4× `m7i-flex.large` + 1× `t4g.micro` — + 5 EIPs:
- Compute: (4 × US$0,0958 + US$0,0084) × (35/60)h ≈ US$0,230
- EIP: 5 × US$0,005 × (35/60)h ≈ US$0,015
- EBS: negligível (apagado junto no destroy/termination)
- **Total estimado: ≈ US$0,25**, mesmo no dobro do tempo (70 min): ≈ US$0,49.

**Se algo falhar e o self_terminate de 1h disparar antes da limpeza manual:** custo sobe para ~2× o acima (≈US$0,46 de compute) — os EIPs seguem o mesmo risco residual já documentado, coberto tanto por `cleanup.py --release-eips` (principal) quanto por `emergency_stop.py` (fallback).

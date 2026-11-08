# Ensaio de infraestrutura — ~20 minutos, sem experimento

Decisão 57 (revisão do roteiro da Decisão 56, item 3). Roteiro para
o Luciano executar (este processo nunca roda nenhum passo abaixo) —
usa as MESMAS credenciais e o MESMO profile AWS CLI já usados na v8
(`mockopin-pqc`). Objetivo: provar `terraform apply`/`destroy`
reais, `docker save`/`load` com conferência de Image ID, um
handshake real por perfil (prova de mecanismo, não experimento), e a
parada de emergência — nunca uma execução de experimento (nenhuma
das 60 execuções oficiais, nenhuma das 12 capturas do critério 1).

**Duração alvo: ~20 minutos de janela medida, ordem estritamente
linear (0→8, cada passo depende só do anterior).** `self_terminate_hours`
reduzido pra **1h** só pro ensaio (rede de segurança — nunca
pretendido pra durar isso; os passos 6-8 são o teardown real,
obrigatórios mesmo que o ensaio termine antes do autodesligamento).

---

## Passo 0 — pré-requisitos

```
export TF_VAR_operator_ip_cidr="$(curl -s https://checkip.amazonaws.com)/32"
export TF_VAR_operator_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
cd thesis/results/v9/terraform
terraform init
```
**Saída esperada:** `Terraform has been successfully initialized!`
**Critério de abortar:** qualquer erro de init/provider.

---

## Passo 1 — `terraform plan`, depois `terraform apply` (`self_terminate_hours=1`)

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
**Saída esperada:** `Plan: 28 to add, 0 to change, 0 to destroy.` — se o número real divergir de 28, **pare e reconcilie antes do apply** (não assuma que a tabela acima está errada nem que o plan está errado — leia o motivo da diferença).

```
terraform apply -var="self_terminate_hours=1" -auto-approve
```
**Saída esperada:** `Apply complete! Resources: 28 added, 0 changed, 0 destroyed.`
**Critério de abortar:** qualquer erro de apply, ou um `plan`/`apply` com N ≠ 28 sem explicação encontrada — rodar `terraform destroy -auto-approve` imediatamente e parar o ensaio.

---

## Passo 2 — confirmar as 5 instâncias: `running`, Docker pronto, porta certa

```
terraform output -json inventory
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 \
  --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" \
  --query "Reservations[].Instances[].State.Name"
```
(repetir para `eu-north-1`/`ap-southeast-1`, 1 instância cada — total 5: 3 em sa-east-1, 1 em cada uma das outras duas)

**Saída esperada:** `inventory` com os 5 IPs; cada `describe-instances` devolve `"running"`.
**Critério de abortar:** qualquer instância fora de `running`/`pending` por mais de 2 minutos.

**Docker pronto, em CADA uma das 5 instâncias** (user_data já instala Docker — `install_common_packages.sh` — mas a instância pode ainda estar processando o `user_data` quando `running` aparece):
```
for IP in <os 5 IPs públicos>; do
  echo "=== $IP ==="
  for i in $(seq 1 20); do
    ssh -i <chave-da-campanha-ou-operador> ec2-user@$IP "docker info >/dev/null 2>&1" && { echo "Docker pronto"; break; }
    sleep 3
  done
done
```
**Saída esperada:** `"Docker pronto"` pras 5, dentro de 20 tentativas (~60s) cada.
**Critério de abortar:** qualquer instância sem Docker pronto depois de 20 tentativas — SSH funcionando mas Docker nunca sobe é sinal de `user_data` falhado, investigar antes de prosseguir.

**Porta usada no ensaio = porta da regra de ingress do Security Group, confirmado em `main.tf`:** SSH usa 22 (`aws_vpc_security_group_ingress_rule.ssh`, `from_port=22 to_port=22`); o gateway usa 443 (`aws_vpc_security_group_ingress_rule.gateway`, `from_port=443 to_port=443`, só no servidor) — os Passos 3/4 abaixo discam exatamente a porta 443, nenhuma outra.

---

## Passo 3 — `docker save | load`: gateway pro servidor, negtest pro cliente L0

Local (máquina do Luciano, já com as imagens construídas):
```
python -c "import json; print(json.load(open('../PINS.json'))['images']['gateway']['image_id'])"
docker save mockopin-v9-gateway | ssh -i <chave-da-campanha> ec2-user@<EIP-servidor> docker load
ssh -i <chave-da-campanha> ec2-user@<EIP-servidor> "docker image inspect mockopin-v9-gateway --format '{{.Id}}'"

docker save mockopin-v9-negtest | ssh -i <chave-da-campanha> ec2-user@<IP-cliente-L0> docker load
```
**Saída esperada:** o `.Id` do gateway na instância é **idêntico** ao `image_id` do `PINS.json` local.
**Critério de abortar:** qualquer divergência de Image ID no gateway — nunca rodar essa imagem.

**`mockopin-v9-negtest` NÃO é pinada em `PINS.json`, de propósito — e está certo que não seja:** confirmado por grep, nenhum arquivo do orquestrador real (`orchestrator.py`/`preflight.py`) referencia `negtest` em nenhum lugar — é uma ferramenta de teste negativo/diagnóstico (Decisão 19/52), usada só em validações manuais e neste ensaio, nunca no caminho medido do piloto (que usa `mockopin-v9-proxy` via `opin_flow.py`, não `negtest`). Pinar um artefato que nenhum código de produção carrega não protegeria nada — por isso não há conferência de Image ID pra ela aqui, só o `docker load` em si (que já falha alto se o tar estiver corrompido).

**Nenhum `docker run`, nenhuma conexão mTLS ainda — só a entrega das imagens.**

---

## Passo 4 — handshake real por perfil (4, prova de mecanismo, nunca experimento)

Script de verdade, **testado localmente em loopback antes de ser
entregue** — saída real desta sessão:

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
**Os 4 perfis passaram, delta 0B nos dois sentidos, confirmado real nesta sessão** (gateway reconstruído a cada perfil, `negtest -scenario matrix` discando de verdade via rede Docker, nunca simulado).

No ensaio real (AWS), rodar o MESMO script, parametrizado pros hosts reais:
```
EIP_SERVIDOR=$(terraform output -json inventory | python -c "import json,sys; print(json.load(sys.stdin)['server']['public_ip'])")
IP_CLIENTE_L0=$(terraform output -json inventory | python -c "import json,sys; print(json.load(sys.stdin)['clients']['L0']['public_ip'])")

GATEWAY_SSH="ssh -i <chave-da-campanha> ec2-user@$EIP_SERVIDOR" \
CLIENT_SSH="ssh -i <chave-da-campanha> ec2-user@$IP_CLIENTE_L0" \
GATEWAY_HOST="$EIP_SERVIDOR" \
bash rehearsal_handshake.sh
```
**Saída esperada:** `RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos` — igual ao teste local, agora numa rede/instâncias reais.
**Critério de abortar:** qualquer `FALHA` impressa pelo script, ou `RESULTADO FINAL: FAIL` — não é motivo de destruir às pressas (é um achado sobre o mecanismo, não da infraestrutura), mas marca o ensaio como **reprovado neste ponto**, registrado explicitamente, antes de seguir pro passo 5.

**O que este passo NÃO faz:** não conta como nenhuma das 60 execuções oficiais nem nenhuma das 12 capturas do critério 1.

---

## Passo 5 — `emergency_stop.py`, modo dry (diagnóstico, antes de qualquer teardown)

```
cd ../campaign/scripts
python emergency_stop.py --profile mockopin-pqc
```
**Saída esperada:** `instances_found`/`eips_found`/`security_groups_found`/`key_pairs_found` listando os recursos reais do ensaio (**4 key pairs agora aparecem de verdade** — corrigido nesta rodada, ver nota abaixo), e todas as listas `..._terminated`/`..._released`/`..._deleted` **vazias** — modo dry nunca age.
**Critério de abortar:** qualquer lista de ação não-vazia em modo dry — bug real, investigar antes de usar `--execute` em qualquer cenário.

**Achado e corrigido nesta rodada:** nenhum `aws_key_pair` (nem aqui, nem na v8 original) tinha tag `Project` — `emergency_stop.py` (que filtra tudo por tag) nunca teria encontrado nenhuma key pair, mesmo com as 4 existindo de verdade. `main.tf` corrigido (tags adicionadas às 4, aditivo, nunca muda `key_name`/`public_key` nem o comportamento de nenhum outro recurso) — confirme no passo acima que `key_pairs_found` lista as 4 agora.

---

## Passo 6 — teardown PRINCIPAL: `cleanup.py --release-eips --force`

**Por que `cleanup.py`, não `emergency_stop.py`, é o caminho principal:**
comparado linha a linha contra `v8/campaign/scripts/campaign_down.sh`
(o teardown real da v8): os 5 checks de verificação são estruturalmente
IDÊNTICOS (mesmo tipo de filtro por recurso — tag para
instâncias/volumes/EIPs, padrão de NOME para security groups/key
pairs — só a constante de nome mudou, `mockopin-pqc-campaign*` →
`mockopin-pqc-v9-piloto*`), MAS `cleanup.py` tem 2 capacidades NOVAS
que a v8 nunca teve: detecção de drift por autodesligamento ANTES do
destroy, e liberação ATIVA de EIPs órfãos (`--release-eips`) — a v8
real só FALHA e exige intervenção manual se um EIP sobra, nunca o
libera sozinha. Isso é uma mudança de lógica real (capacidade nova,
não só renomeação) — por isso o caminho principal passa a ser
`cleanup.py`, mais capaz, nunca o `emergency_stop.py` (mais novo,
pior testado contra a AWS real).

```
python cleanup.py --tf-dir ../../terraform --profile mockopin-pqc --release-eips --force
```
**Saída esperada:** JSON com `"all_clean": true` — `cleanup.py` já roda `terraform destroy` E verifica as 5 categorias internamente, nas 3 regiões, incluindo a liberação de qualquer EIP órfão encontrado.
**Critério de abortar:** `all_clean: false`, ou qualquer excessão — não destruir mais nada manualmente ainda, ir pro passo 7 (fallback), nunca pular direto pro passo 8.

---

## Passo 7 — fallback: `emergency_stop.py --execute`, só se sobrou algo

**Só roda se o passo 6 reportou `all_clean: false`.** Se o passo 6
já deu `all_clean: true`, pule direto pro passo 8 (nada a fazer aqui
— registre isso no relatório do ensaio).

```
python emergency_stop.py --profile mockopin-pqc --execute
```
**Saída esperada:** qualquer recurso que o passo 6 não limpou aparece em `..._terminated`/`..._released`/`..._deleted` agora (com as tags do passo 5, incluindo as 4 key pairs corrigidas).
**Critério de abortar:** qualquer erro de permissão persistente — nesse ponto, investigação manual pela console AWS é o próximo passo, nunca mais automação.

---

## Passo 8 — verificação final: nada ficou na conta

```
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" "Name=instance-state-name,Values=running,pending,stopping,stopped"
aws ec2 describe-addresses --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
aws ec2 describe-security-groups --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
aws ec2 describe-key-pairs --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
```
(repetir as 4 chamadas para `eu-north-1`/`ap-southeast-1` — 12 chamadas no total, 4 tipos × 3 regiões)

**Saída esperada:** as 12 chamadas devolvem listas **vazias**. Se o passo 6 já deu `all_clean: true`, este passo é só a confirmação formal e independente (API direta, não reaproveita o JSON do `cleanup.py`).
**Critério de abortar/alerta:** qualquer recurso ainda presente — investigar antes de considerar o ensaio limpo.

---

## Custo estimado do ensaio

~20 minutos de frota (passos 0-8) — 5 instâncias: 4× `m7i-flex.large`
+ 1× `t4g.micro` — + 5 EIPs:
- Compute: (4 × US$0,0958 + US$0,0084) × (20/60)h ≈ US$0,131
- EIP: 5 × US$0,005 × (20/60)h ≈ US$0,008
- EBS: negligível (apagado junto no destroy/termination)
- **Total estimado: ≈ US$0,14**, mesmo no dobro do tempo (40 min): ≈ US$0,28.

**Se algo falhar e o self_terminate de 1h disparar antes da limpeza manual:** custo sobe para ~4× o acima (≈US$0,56 de compute) — os EIPs seguem o mesmo risco residual já documentado, agora coberto tanto por `cleanup.py --release-eips` (principal) quanto por `emergency_stop.py` (fallback).

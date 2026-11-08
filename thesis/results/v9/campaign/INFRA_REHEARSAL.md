# Ensaio de infraestrutura — 15 minutos, sem experimento

Decisão 56, item 3. Roteiro para o Luciano executar (este processo
nunca roda nenhum passo abaixo) — usa as MESMAS credenciais e o
MESMO profile AWS CLI já usados na v8 (`mockopin-pqc`). Objetivo:
provar `terraform apply`/`destroy` reais, `docker save`/`load` com
conferência de Image ID, e a parada de emergência (`emergency_stop.py`)
contra recursos REAIS — nunca uma execução de experimento (nenhum
perfil medido, nenhuma conexão mTLS real contada).

**Duração alvo: 15 minutos de janela medida (passos 0-6) + ~5 minutos
pro passo 7 (prova de handshake, proposto nesta rodada) = ~20 minutos
no total.** `self_terminate_hours` reduzido pra **1h** só pro ensaio
(rede de segurança — nunca pretendido pra durar isso; a limpeza
manual do passo 6 é o teardown real, obrigatório mesmo que o ensaio
termine antes do autodesligamento).

---

## Passo 0 — pré-requisitos (antes de começar a contar os 15 minutos)

```
export TF_VAR_operator_ip_cidr="$(curl -s https://checkip.amazonaws.com)/32"
export TF_VAR_operator_ssh_public_key="$(cat ~/.ssh/id_ed25519.pub)"
cd thesis/results/v9/terraform
terraform init
```
**Saída esperada:** `Terraform has been successfully initialized!`
**Critério de abortar:** qualquer erro de init/provider — nunca prossegue pro apply.

---

## Passo 1 — `terraform apply` real, com `self_terminate_hours=1`

```
terraform apply -var="self_terminate_hours=1" -auto-approve
```
**Saída esperada:** `Apply complete! Resources: N added, 0 changed, 0 destroyed.` — N deve corresponder exatamente aos recursos de `main.tf` (5 instâncias + 5 EIPs + 5 security groups + regras de ingress + 3 key pairs regionais + 1 key pair do operador).
**Critério de abortar:** qualquer erro de apply (quota, permissão, AMI) — rodar `terraform destroy -auto-approve` imediatamente e parar o ensaio.

## Passo 2 — conferir que as 5 instâncias subiram

```
terraform output -json inventory
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 \
  --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" \
  --query "Reservations[].Instances[].State.Name"
```
(repetir `describe-instances` para `eu-north-1`/`ap-southeast-1`, 1 instância cada)

**Saída esperada:** `inventory` com os 5 IPs públicos/privados; cada `describe-instances` devolve `"running"` para as instâncias daquela região (3 em sa-east-1, 1 em cada uma das outras duas — total 5).
**Critério de abortar:** qualquer instância em `"pending"` por mais de 2 minutos ou em qualquer estado que não seja `running`/`pending` — destruir e parar.

## Passo 3 — `docker save | load`, conferindo o Image ID contra PINS.json

Local (máquina do Luciano, mesma que já tem as 3 imagens construídas):
```
python -c "import json; print(json.load(open('../PINS.json'))['images']['gateway']['image_id'])"
docker save mockopin-v9-gateway | ssh -i <chave-da-campanha> ec2-user@<IP-do-servidor> docker load
ssh -i <chave-da-campanha> ec2-user@<IP-do-servidor> "docker image inspect mockopin-v9-gateway --format '{{.Id}}'"
```
**Saída esperada:** o `.Id` devolvido pela instância é **idêntico, caractere a caractere**, ao `image_id` impresso do `PINS.json` local.
**Critério de abortar:** qualquer divergência de Image ID — a instância NUNCA deve rodar essa imagem; investigar antes de prosseguir (mas o ensaio já provou o que precisava: o mecanismo de conferência funciona).

(Repetir o mesmo padrão para `mockopin-v9-proxy` num cliente, se o tempo do ensaio permitir — não obrigatório pros 15 minutos, o gateway já prova o mecanismo.)

**Nenhum `docker run`, nenhuma conexão mTLS, nenhum perfil ativado — o ensaio para aqui, nunca ativa o gateway de verdade.**

## Passo 4 — `emergency_stop.py`, modo dry (sem `--execute`)

```
cd ../campaign/scripts
python emergency_stop.py --profile mockopin-pqc
```
**Saída esperada:** JSON com `instances_found`/`eips_found`/`security_groups_found`/`key_pairs_found` listando os recursos reais do ensaio (tag `Project=mockopin-pqc-v9-piloto`), e `instances_terminated`/`eips_released`/etc. todos **vazios** (`[]`) — modo dry nunca age.
**Critério de abortar:** se QUALQUER lista de `..._terminated`/`..._released`/`..._deleted` vier não-vazia em modo dry — bug real, parar e investigar antes de usar `--execute` em qualquer cenário real.

## Passo 5 — `emergency_stop.py --execute`, sobre os recursos do ENSAIO

```
python emergency_stop.py --profile mockopin-pqc --execute
```
**Saída esperada:** as mesmas 5 instâncias/5 EIPs/5 security groups/4 key pairs do passo 4, agora em `..._terminated`/`..._released`/`..._deleted` — e o relatório não deve listar nenhum ID que não apareceu no passo 4 (mesma tag, mesma lista).
**Critério de abortar:** qualquer erro de permissão (ver `security_groups_errors`, se um SG ainda estiver em uso porque uma instância não terminou a tempo — o script já espera até 2 minutos, mas registra o erro em vez de travar) — se aparecer, esperar mais e rodar de novo só a etapa de security groups, nunca prosseguir pro passo 6 com recursos ainda presos.

## Passo 6 — verificação final: nada ficou na conta

```
aws ec2 describe-instances --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto" "Name=instance-state-name,Values=running,pending,stopping,stopped"
aws ec2 describe-addresses --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
aws ec2 describe-security-groups --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
aws ec2 describe-key-pairs --profile mockopin-pqc --region sa-east-1 --filters "Name=tag:Project,Values=mockopin-pqc-v9-piloto"
```
(repetir as 4 chamadas para `eu-north-1`/`ap-southeast-1`)

**Saída esperada:** as 12 chamadas (4 tipos × 3 regiões) devolvem listas **vazias**.
**Critério de abortar/alerta:** qualquer recurso ainda presente — não é motivo de pânico (o `terraform state` ainda existe, `terraform destroy` normal cobre o resto), mas precisa ser investigado antes de considerar o ensaio limpo. Se `emergency_stop.py` já limpou tudo, este passo é só a confirmação formal — `terraform destroy` depois dele deve reportar `0 destroyed` adicionais (ou dar erro de recurso já removido, esperado e inofensivo nesse caso específico).

```
terraform destroy -auto-approve
```
(fecha o state do Terraform, mesmo que `emergency_stop.py` já tenha limpo os recursos reais — mantém o state consistente com a conta)

## Passo 7 — prova de handshake real por perfil (4, sem experimento)

**Numerado 7 porque foi proposto nesta rodada, DEPOIS dos passos 0-6
originais — mas roda CRONOLOGICAMENTE entre o passo 3 e o passo 4**
(depois do `docker load` confirmado, antes de qualquer
`emergency_stop.py`; nunca depois do passo 6, que já destruiu tudo).
Não existia no roteiro original — proposto agora porque nenhum passo
anterior liga o gateway, disca de verdade, ou confere o delta de
bytes contra o EIP real. Usa a MESMA imagem já pinada (passo 3,
construída com certificados de SAN placeholder, formato
`<IP>,::1`) — nunca reconstrói nem repina nada, porque o valor do IP
no SAN nunca precisa bater com o EIP de verdade (Decisão 30 do
pré-registro: a verificação do certificado checa só o DNS "mtls" via
hostname, nunca o endereço IP do SAN — confirmado no código,
`cert.VerifyHostname("mtls")`). Este passo demonstra isso ao vivo,
não só cita a decisão.

```
EIP_SERVIDOR=$(terraform output -json inventory | python -c "import json,sys; print(json.load(sys.stdin)['server']['public_ip'])")

# confere o que esta de fato gravado no SAN do certificado JA EMBUTIDO
# na imagem pinada -- nunca precisa bater com $EIP_SERVIDOR.
docker run --rm --entrypoint sh mockopin-v9-gateway -c \
  "cat /certs/classico_server.crt" | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"

ssh -i <chave-da-campanha> ec2-user@$EIP_SERVIDOR \
  "docker run -d --name v9-mtls-ensaio -p 443:443 -e HTTP_MODE=business -e CRYPTO_PROFILE=classico mockopin-v9-gateway"

for PERFIL in classico pqc hibrido-v8 hibrido-and; do
  ssh -i <chave-da-campanha> ec2-user@<IP-do-cliente-L0> \
    "docker run --rm --network host mockopin-v9-negtest -scenario matrix -client-mode $PERFIL -server-mode $PERFIL -target $EIP_SERVIDOR:443 -cert-dir /certs"
  ssh -i <chave-da-campanha> ec2-user@$EIP_SERVIDOR "docker logs v9-mtls-ensaio 2>&1 | tail -1"
done

ssh -i <chave-da-campanha> ec2-user@$EIP_SERVIDOR "docker rm -f v9-mtls-ensaio"
```
(repetir o `docker run -d` do gateway trocando `CRYPTO_PROFILE` antes de cada perfil, igual ao `_launch_gateway` real — simplificado aqui numa única linha por brevidade do roteiro)

**Saída esperada, por perfil:**
- O SAN impresso no início do passo mostra um IP que **não precisa, e normalmente não vai, ser igual a `$EIP_SERVIDOR`** — registrar os dois valores lado a lado no relatório do ensaio, exatamente para mostrar a diferença, não para forçar que batam.
- `RESULT matrix client=<perfil> server=<perfil> outcome=SUCCESS curve=... dualAuthenticated=...` — a conexão TEM que fechar com sucesso MESMO com o SAN do certificado apontando para um IP diferente do EIP real que o `-target` discou.
- A linha `connection OK` do gateway mostra `handshakeBytesIn=X handshakeBytesOut=Y` — comparar os 4 pares contra `BASELINE_HANDSHAKE_BYTES` (`evaluate_criteria.py`): **delta esperado 0B nos 4 perfis, nos 2 sentidos** (a mesma evidência da Decisão 55/56, agora numa rede e numa instância reais, não loopback local).

**Critério de abortar:** qualquer `outcome=FAIL`, ou qualquer delta != 0B contra o baseline — não é motivo de destruir às pressas (não é um erro de infraestrutura, é um achado sobre o mecanismo que precisa de investigação antes do piloto de verdade rodar), mas o ensaio deve ser marcado como **reprovado neste ponto**, registrado explicitamente no relatório, antes de seguir para o passo 4.

**O que este passo NÃO faz:** não conta como nenhuma das 60 execuções oficiais nem como nenhuma das 12 capturas do critério 1 — é só prova de mecanismo, 4 conexões soltas, nunca um bloco cronometrado.

---

## Custo estimado do ensaio

~20 minutos de frota (passos 0-7, incluindo o novo passo 7) — 5
instâncias: 4× `m7i-flex.large` + 1× `t4g.micro` — + 5 EIPs:
- Compute: (4 × US$0,0958 + US$0,0084) × (20/60)h ≈ US$0,131
- EIP: 5 × US$0,005 × (20/60)h ≈ US$0,008
- EBS: negligível nessa janela (apagado junto no destroy/termination)
- **Total estimado: ≈ US$0,14**, mesmo se o ensaio levar o dobro do previsto (40 min): ≈ US$0,28. Dentro de qualquer alerta de orçamento razoável (item g do `PILOT_READINESS.md`).

**Se algo falhar e o self_terminate de 1h disparar antes da limpeza manual:** custo sobe para ~4× o acima (≈US$0,56 de compute) — ainda pequeno, e os EIPs seguem o mesmo risco residual já documentado (órfãos até liberação manual/`emergency_stop.py`).

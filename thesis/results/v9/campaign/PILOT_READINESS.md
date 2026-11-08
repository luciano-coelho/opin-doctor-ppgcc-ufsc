# Dossiê de prontidão do piloto v9 — PQC/híbrido/AND, AWS

Documento autônomo (Decisão 54, item 4). Não exige ter acompanhado as
53 decisões anteriores. Cobre: status real dos 7 critérios do piloto,
os pré-requisitos de AWS que só Luciano pode fazer, o teto de custo e
o procedimento de parada de emergência, os riscos residuais conhecidos
e a confirmação de que o runbook cobre a janela de 3-4h com Luciano
presente.

Escopo: piloto de 60 execuções (4 perfis × 3 rotas × N=5), nunca a
campanha oficial de 960. Branch `v9/fase1-local`. Nenhuma ação de AWS
foi tomada para produzir este documento — é leitura de código e
Terraform, mais os dados já medidos localmente nas rodadas anteriores.

---

## a) Os 7 critérios de ir/não-ir — status real

| # | Critério (limiar) | Status | Evidência / o que falta |
|---|---|---|---|
| 1 | Tamanhos por mensagem — 0B no ClientHello, ±4B na Certificate, 0B nas demais, nas 12 capturas (4 perfis × 3 rotas) | **Validado localmente (mecânica completa)** | pcap real decifrado por perfil, flight extraído via tshark, bate exato com os baselines nos 4 perfis (Decisão 52/54). `SSHExecutor.dedicated_capture` implementado e testado. **Só a AWS confirma:** interface real (`ens5`, não `eth0` do bridge Docker), tráfego cruzando 2 instâncias de verdade, e a tolerância de bytes com o SAN real (EIP) em vez do loopback. |
| 2 | initcwnd real ≥ 10 segmentos | **Só validável na AWS** | O método (`criterio2_probe.py`) está escrito e testado mecanicamente (JSON válido), mas só é significativo com RTT > 0 — em loopback local o MSS nunca segmenta de verdade (reconhecido no próprio script). Nunca rodado contra uma rota real. |
| 3 | Zero erros em 20/20 execuções na rota mais distante (`sa-east-1/L325`) | **Só validável na AWS** | Depende da rota L325 existir de verdade (instância em `ap-southeast-1`). |
| 4 | 44 HTTP / 6 mTLS / 28 JWT / 4 jwks / 4 CA, exatos, em 60/60 | **Parcialmente validado localmente** | A contagem exata (`{"http":44,"jwts":28,"jwks":4,"ca":4,"mtls":6}`) foi confirmada em dezenas de execuções reais via shim local (Decisões 50-54) para os 4 perfis. **Só a AWS confirma** que a mesma contagem se mantém sob rede real (latência/perda não simuladas aqui) e nas 60 execuções completas. |
| 5 | Zero erros em 60/60 execuções combinadas | **Parcialmente validado localmente** | Mesma evidência do item 4 — zero erros em toda execução real feita localmente até aqui (nenhuma das ~500+ conexões reais produzidas nesta sessão falhou). Cardinalidade de 60 só a AWS fecha. |
| 6 | CurveID + DualAuthenticated em 100% das execuções, keylog+captura+tamanhos extraídos com sucesso | **Validado localmente (mecânica)** | `dualAuthenticated=true`/`curve` corretos confirmados nos 4 perfis via log real do gateway, em ~500 conexões reais desta sessão (0 falhas). Keylog real decifra via tshark (Decisão 52/54). **Só a AWS confirma** a cardinalidade 60/60. |
| 7 | RTT de cada rota dentro de ±10% do nominal, dois canais concordando | **Não validado** | Método definido (`criterio7_rtt.py`), nunca executado — depende de rotas reais existirem. |

**Leitura honesta:** nenhum dos 7 critérios está 100% fechado sem AWS — isso é esperado e correto (são critérios sobre uma rede real). O que este documento garante é que a MECÂNICA de cada critério (como medir, como extrair, como decidir pass/fail) está implementada, testada com dados reais onde isso é possível localmente, e nunca presa num bug conhecido.

---

## b) Pré-requisitos de AWS que são do Luciano (passos concretos)

Nenhum destes pode ser feito por este processo — exigem acesso à
conta/console que este ambiente não tem.

### 1. Service Quotas por região
Regiões do piloto: `sa-east-1` (controle + servidor + cliente L0, 3
instâncias), `eu-north-1` (cliente L219, 1 instância), `ap-southeast-1`
(cliente L325, 1 instância).

- **vCPU — quota "Running On-Demand Standard (A,C,D,H,I,M,R,T,Z)"**
  (código `L-1216C47A`). Tipos usados: `m7i-flex.large` (servidor e
  3 clientes, família M) e `t4g.micro` (controle, família T) — os
  dois caem na MESMA quota "Standard".
  - `sa-east-1`: precisa de pelo menos **8 vCPU** (3× m7i-flex.large
    ≈ 6 + 1× t4g.micro ≈ 2 — confirme o vCPU exato de cada tipo no
    console, pode variar).
  - `eu-north-1` / `ap-southeast-1`: pelo menos **2 vCPU** cada.
  - **Como verificar:** console AWS → Service Quotas → EC2 → "Running
    On-Demand Standard..." → confirmar o valor atual em CADA uma das
    3 regiões (o default de conta nova costuma já cobrir isso, mas
    precisa ser confirmado, nunca assumido).
- **Elastic IPs por região.** Este piloto aloca **1 EIP por
  instância** (5 no total: 3 em `sa-east-1`, 1 em `eu-north-1`, 1 em
  `ap-southeast-1`). O limite padrão de conta é geralmente 5 por
  região — `sa-east-1` precisa de 3, dentro do padrão, mas **confirme
  quantos EIPs a conta já tem alocados em uso por OUTROS projetos**
  antes do piloto, para não estourar o limite por acúmulo.

### 2. Par de chaves por região
O Terraform (`thesis/results/v9/terraform/main.tf`) já cria as chaves
da CAMPANHA via `tls_private_key`/`aws_key_pair` nas 3 regiões
automaticamente — **isso não exige ação manual do Luciano**. O que
exige ação dele: a chave do CONTROLE usa a chave SSH PESSOAL dele
(`var.operator_ssh_public_key`, `aws_key_pair.operator_sa_east_1`) —
ele precisa ter um par de chaves SSH próprio e passar a metade
pública via `TF_VAR_operator_ssh_public_key` (variável de ambiente,
nunca arquivo versionado) antes do `terraform apply`.

### 3. Política IAM de menor privilégio para o orquestrador
Nenhuma política foi criada na AWS — proposta abaixo, para o Luciano
revisar e aplicar ao usuário/role que o Terraform e os scripts Python
vão usar. Compilada a partir do uso REAL do código (`terraform`, mais
`preflight.py`/`cleanup.py`), não de uma lista genérica:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LeituraGeral",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "sts:GetCallerIdentity",
        "servicequotas:GetServiceQuota",
        "budgets:ViewBudget",
        "budgets:DescribeBudgets"
      ],
      "Resource": "*"
    },
    {
      "Sid": "CicloDeVidaDeInstancia",
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:TerminateInstances",
        "ec2:CreateTags"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:RequestTag/Project": "mockopin-pqc-v9-piloto" }
      }
    },
    {
      "Sid": "TerminarSoDoProjeto",
      "Effect": "Allow",
      "Action": "ec2:TerminateInstances",
      "Resource": "*",
      "Condition": {
        "StringEquals": { "aws:ResourceTag/Project": "mockopin-pqc-v9-piloto" }
      }
    },
    {
      "Sid": "RedeEChaves",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateKeyPair", "ec2:DeleteKeyPair",
        "ec2:AllocateAddress", "ec2:ReleaseAddress",
        "ec2:AssociateAddress", "ec2:DisassociateAddress",
        "ec2:CreateSecurityGroup", "ec2:DeleteSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress"
      ],
      "Resource": "*"
    }
  ]
}
```

**Limitação honesta, registrada, não escondida:** `ec2:CreateKeyPair`/
`ec2:CreateSecurityGroup`/`ec2:AllocateAddress` **não suportam
condição por tag no momento da criação** (o recurso não existe
ainda) — por isso o bloco "RedeEChaves" acima é mais largo que o
ideal (não pode ser restrito só ao projeto nesse ponto). Mitigação:
o `cleanup.py` já confere por tag (`Project=mockopin-pqc-v9-piloto`)
antes de qualquer `ec2:ReleaseAddress`/etc. real, então o RISCO
prático (apagar recurso de outro projeto por acidente) é baixo, mas
a permissão EM SI é mais ampla do que um purista de least-privilege
aceitaria. Decisão do Luciano se isso é aceitável ou se prefere
revisar manualmente antes de aplicar.

### 4. Alerta de orçamento
Já existe um alerta de orçamento configurado na conta (herdado da
campanha v8, confirmado via `check_budget_alert_exists` — o VALOR
exato nunca é lido nem logado por este projeto, por política,
Decisão 27). O valor de referência histórico citado em
`DECISIONS.md` (linha ~3459) é **US$27,72**, mas nunca confirmado
contra a API real nesta sessão (regra permanente: nenhuma leitura de
valor de orçamento). **Sugestão:** criar (ou confirmar que já existe)
um alerta ESPECÍFICO para o piloto v9, com valor bem menor que o
alerta geral da conta — por exemplo **US$5** (4-5× a estimativa de
custo do item c abaixo, margem suficiente para pegar qualquer anomalia
rápido, sem ser tão apertado que dispare por flutuação normal de
preço). Decisão final do valor é do Luciano.

---

## c) Teto de custo e parada de emergência

### Estimativa de custo (aritmética, fontes datadas, sem chamada à AWS)
Do `DECISIONS.md` (linha ~3440-3453), ancorada no custo REAL medido
da campanha v8 (US$29,34 / 22,45h de frota, 720 execuções):

- 5 instâncias no ar (~1,5-2h de frota): 4× `m7i-flex.large` +
  1× `t4g.micro` + 5× IP público + 5× EBS gp3 30GB + transferência
  entre regiões.
- **Subtotal ≈ US$0,89. Com margem de 30%: ≈ US$1,15.**
- Cabe com folga grande em qualquer alerta de orçamento razoável
  (mesmo o antigo US$27,72 da v8 — usaria ~4-7% dele).

### Procedimento de parada de emergência
Comando exato (roda do controle ou de onde o Terraform tem acesso):

```
python cleanup.py --tf-dir ../../terraform --profile mockopin-pqc --release-eips --force
```

- **`--force`**: necessário numa emergência porque o fluxo normal
  exige `collect_artifacts.py` já ter rodado (`--pull-verified-marker`)
  antes do destroy — numa parada de emergência pode não ter dado
  tempo de coletar nada, e isso é aceitável (dados de execução > dados
  perdidos por não desligar a tempo).
- **`--release-eips`**: sem esta flag, EIPs órfãos (sem instância
  associada — por exemplo, se um autodesligamento por tempo já tiver
  disparado em alguma instância antes do destroy) só são REPORTADOS,
  nunca liberados de verdade. Numa emergência, sempre passar esta
  flag.

**O que o comando destrói:** as 5 instâncias (controle + servidor +
3 clientes), seus grupos de segurança, as chaves SSH exclusivas da
campanha (não a chave pessoal do Luciano, que é usada só no controle
via `key_name`, nunca criada por este Terraform), os volumes EBS, e
os 5 Elastic IPs (liberados pela destruição do próprio recurso
`aws_eip`, que o Terraform já trata como dependente da instância —
Decisão 45: "um `aws_eip` é liberado pela sua PRÓPRIA destruição, não
pela da instância associada", por isso o `terraform destroy` cobre
isso corretamente).

**O que pode sobrar cobrando, e por quê:** EIPs que ficaram órfãos
ANTES deste comando rodar (por exemplo, autodesligamento por tempo já
tendo terminado uma instância fora do ciclo do Terraform) — cobertos
pelo `--release-eips`, mas só se o Luciano passar a flag. Sem
`--release-eips` e sem rodar de novo, um EIP órfão continua cobrando
(~US$0,005/h) indefinidamente até ser liberado manualmente ou via
este script. **Nenhum outro recurso deste piloto sobrevive ao
`terraform destroy` por padrão** (confirmado: todos os 5 blocos de
instância usam o mesmo módulo, mesmo padrão de tags, sem exceção).

---

## d) Riscos residuais conhecidos

| # | Risco | Mitigação existente | Decisão que falta do Luciano |
|---|---|---|---|
| 1 | Imagem `mockopin-v9-measure` (tcpdump+tshark, usada por `dedicated_capture`) precisa existir em cada instância, mas o pipeline de sincronizar+`docker build` o código-fonte nela ainda não está implementado no deploy real | `check_capture_prerequisites` (Decisão 53) detecta a AUSÊNCIA e aborta com mensagem clara, antes de qualquer execução — nunca falha silenciosamente | Decidir COMO essa imagem chega à instância: (a) implementar o passo de scp+build no deploy, ou (b) aceitar rodar o `docker build` manualmente no controle antes do piloto, uma vez |
| 2 | O binário do gateway é verificado por `sha256sum -c` (Decisão 54, item 1), mas o PROXY (`mockopin-v9-proxy`) e a imagem `mockopin-v9-measure` ainda não têm o mesmo mecanismo | Nenhuma ainda | Decidir se o mesmo mecanismo de verificação deve ser estendido a esses dois antes do piloto, ou se o risco é aceitável para esta rodada (nenhum dos dois decide aceitar/rejeitar uma conexão — o proxy só retransmite, a imagem measure só captura) |
| 3 | Instância de controle não tem autodesligamento por tag/projeto separado do mecanismo de tempo (5h) — se o operador rodar `terraform apply` duas vezes sem destruir a primeira, pode haver controles duplicados cobrando | `self_terminate_hours=5` com `terminate` (não `stop`) já limita o tempo máximo de exposição | Nenhuma — risco já aceito e mitigado (Decisão 50), listado aqui por completude |
| 4 | O alerta de orçamento ativo na conta é o geral (herdado da v8, ~US$27,72 nunca confirmado), não um alerta específico e mais sensível para o piloto | Nenhuma | Decidir se cria um alerta específico (sugestão: US$5, item b.4) antes do piloto |
| 5 | O mecanismo AND cobre só TLS 1.3 — conexões que negociassem TLS 1.2 nunca seriam protegidas pelo AND (limitação de design já registrada, Decisão 4c do pré-registro) | Registrado como limitação explícita do escopo medido — nunca escondida | Nenhuma — aceito desde o pré-registro, listado aqui por completude |
| 6 | `handshakeBytesIn/Out` não tem tolerância pré-registrada formal (Decisão 54, item 3) — só uma proposta | Proposta derivada de 480 amostras reais locais (0B de variação) + a tolerância já existente do critério 1 | Aprovar ou ajustar a tolerância proposta no item 3 deste relatório, antes do piloto rodar de verdade na AWS |
| 7 | A política IAM do item b.3 tem permissões mais largas que o ideal em 3 ações específicas (CreateKeyPair/CreateSecurityGroup/AllocateAddress), por limitação do próprio IAM (sem condição de tag no momento de criação) | `cleanup.py` confere por tag antes de qualquer ação destrutiva real | Aceitar a política proposta como está, ou revisar manualmente antes de aplicar |

---

## e) O runbook cobre a janela de 3-4h com o Luciano presente?

**Sim, confirmado pela sequência real do código, com os pontos de
pausa/decisão explícitos:**

1. **`terraform apply`** (Luciano presente, aprova antes de rodar) —
   cria as 5 instâncias + 5 EIPs numa única apply (confirmado:
   `aws_eip` depende de `aws_instance.this.id`, não há etapa
   separada). ~3-5 minutos.
2. **`pki_relay.py`** — distribui certificados/chaves em 2 saltos
   (operador → controle → destino final). ~1-2 minutos.
3. **Preflight de captura** (`check_capture_prerequisites`, Decisão
   53/54) — roda uma vez, confirma tcpdump/sudo/imagem/interface em
   cada instância que vai capturar. **PONTO DE PAUSA 1:** se
   reprovar, o piloto NUNCA prossegue — mensagem clara do que falta,
   decisão do Luciano se corrige e tenta de novo ou aborta.
4. **Porta de fumaça** (12 execuções + prova de captura por perfil,
   Decisão 48/53/54) — ~5-10 minutos. **PONTO DE PAUSA 2, já
   implementado e testado:** se qualquer uma das 12 reprovar, ou a
   prova de captura por perfil falhar, o orquestrador PARA (nunca
   destrói por conta própria — confirmado no código, Decisão 49) e
   imprime: "corrigir e repetir dentro da janela de 4h" ou "mandar
   destruir". Decisão sempre do Luciano.
5. **60 execuções cronometradas** (4 perfis × 3 rotas × 5) — pela
   estimativa de custo (item c), ~30-60 minutos de janela medida.
6. **`collect_artifacts.py`** — coleta com SHA-256 verificado por
   bloco, ~2-5 minutos.
7. **`cleanup.py --release-eips`** (sem `--force`, já que a coleta
   do passo 6 já rodou) — destroy + verificação final de 5 chamadas
   por região. **PONTO DE PAUSA 3 (obrigatório, nunca pulado):** o
   próprio script reprova (`all_clean: false`) se qualquer recurso
   sobreviver, sinalizando para o Luciano antes de considerar o
   piloto encerrado.

**Soma:** ~45 minutos a ~1h20 de execução ativa, dentro da janela de
autodesligamento de 4h (clientes/servidor) / 5h (controle) com folga
grande — mesmo contando setup/troubleshooting manual, a janela de
3-4h com o Luciano presente cobre o runbook completo com margem.

# Dossiê de prontidão do piloto v9 — PQC/híbrido/AND, AWS

Documento autônomo (Decisão 54, revisado na Decisão 55). Não exige
ter acompanhado as decisões anteriores. Cobre: status real dos 7
critérios do piloto, os pins de binário/imagem e como são entregues,
a tolerância derivada de bytes de handshake, a política IAM restrita
e o script de verificação, a parada de emergência independente do
Terraform, o teto de custo (incluindo o pior caso), e o que falta do
lado do Luciano.

Escopo: piloto de 60 execuções (4 perfis × 3 rotas × N=5), nunca a
campanha oficial de 960. Branch `v9/fase1-local`. Nenhuma ação de AWS
foi tomada para produzir este documento.

---

## a) Os 7 critérios de ir/não-ir — status real

| # | Critério (limiar) | Status | Evidência / o que falta |
|---|---|---|---|
| 1 | Tamanhos por mensagem — 0B no ClientHello, ±4B na Certificate, 0B nas demais, nas 12 capturas (4 perfis × 3 rotas) | **Validado localmente (mecânica completa)** | pcap real decifrado por perfil, flight extraído via tshark, bate exato com os baselines nos 4 perfis. `SSHExecutor.dedicated_capture` implementado e testado. **Só a AWS confirma:** interface real (`ens5`), tráfego cruzando 2 instâncias de verdade, tolerância com SAN real (EIP). |
| 2 | initcwnd real ≥ 10 segmentos | **Só validável na AWS** | Método escrito e testado mecanicamente, só significativo com RTT > 0. |
| 3 | Zero erros em 20/20 execuções na rota mais distante (`sa-east-1/L325`) | **Só validável na AWS** | Depende da rota L325 real. |
| 4 | 44 HTTP / 6 mTLS / 28 JWT / 4 jwks / 4 CA, exatos, em 60/60 | **Parcialmente validado localmente** | Contagem exata confirmada em centenas de execuções reais locais, 4 perfis, 0 erros. Cardinalidade 60/60 sob rede real só a AWS fecha. |
| 5 | Zero erros em 60/60 execuções combinadas | **Parcialmente validado localmente** | Mesma evidência do item 4. |
| 6 | CurveID + DualAuthenticated em 100% das execuções, keylog+captura+tamanhos extraídos | **Validado localmente (mecânica)** | Confirmado nos 4 perfis, centenas de conexões reais, 0 falhas. |
| 7 | RTT de cada rota dentro de ±10% do nominal, dois canais concordando | **Não validado** | Método definido, depende de rotas reais. |

**Leitura honesta:** nenhum dos 7 critérios está 100% fechado sem AWS — esperado, são critérios sobre rede real. Este documento garante que a MECÂNICA de cada um está implementada e testada com dados reais onde isso é possível localmente.

---

## b) Baselines de handshake — os 4 valores, com a fonte

**Correção desta rodada:** uma rodada anterior classificou os valores de Classico e PQC como "nunca citados antes" — falso. Os 4 já estavam no pré-registro, Decisão 14 (T6, instrumentação), `DECISIONS.md` linhas 1511-1519 e 1750-1751 (tabela consolidada "Total medido na fronteira do Handshake()").

| Perfil | handshakeBytesIn (cliente→servidor) | handshakeBytesOut (servidor→cliente) | Fonte |
|---|---|---|---|
| Classico | 1.513 | 1.640 | Decisão 14, `DECISIONS.md` L1517/L1750-1751 |
| PQC | 10.728 | 10.878 | Decisão 14, `DECISIONS.md` L1518/L1750-1751 |
| Hibrido-v8 | 8.397 | 8.552 | Decisão 14, `DECISIONS.md` L1519/L1750-1751 |
| Hibrido-AND | 11.902 | 12.177 | Decisão 14, `DECISIONS.md` L1520/L1750-1751 |

Os 4 foram reconfirmados com 0B de desvio em 480 conexões reais locais nesta sessão (Decisão 54) e de novo em 20 rebuilds de certificado com 4 variações de SAN (Decisão 55, item 3, abaixo).

---

## c) Pins de binário/imagem e como são entregues

### O que é pinado, e por quê
`thesis/results/v9/campaign/PINS.json` (versionado) congela, para `gateway`, `proxy` e `measure`: o sha256 do binário extraído, a saída de `go version -m`, e o Image ID Docker — todos de **uma única imagem construída**, nunca recalculados automaticamente. Alterar o arquivo exige uma Emenda numerada em `DECISIONS.md`.

**Reprodutibilidade, testada de verdade:** o binário do gateway e do proxy foi construído duas vezes, do zero (`--no-cache`), com `-trimpath` + `GOARCH=amd64` explícitos — sha256 **idêntico** nas duas vezes, nos dois binários. O **Image ID Docker não é reproduzível** entre builds independentes (confirmado: o mesmo binário, dois builds, dois Image IDs diferentes — metadados de camada/timestamp variam, conteúdo não). Por isso o Image ID em PINS.json só é válido para o artefato **distribuído por `docker save`/`docker load`** (determinístico — nunca para uma reconstrução local independente).

### Como a imagem chega a cada instância — nunca por `docker build`, agora em 2 saltos reais (Decisão 59)
Restaurado o modelo real da v8 (`deliver_images.sh`), porque `docker save <imagem> | ssh <host> docker load` (Decisão 55) exigia Docker na máquina que executa esse comando -- e essa máquina é o CONTROLE agora que `orchestrator.py` roda de lá, e o controle nunca tem Docker. Dois saltos, cada um na máquina certa:
1. `deliver_images.py`, na máquina do OPERADOR (tem Docker): `docker save <imagem> > <imagem>.tar`, sha256, checagem de espaço em disco no controle, scp pro controle (`~/images/`). Pro gateway, também extrai o binário e confere o sha256 contra PINS.json aqui (nunca no controle).
2. `SSHExecutor._deliver_image(image_key, host)`, rodando DO CONTROLE: scp do `.tar` já estagiado (arquivo LOCAL, nunca `docker save`) pro host, `ssh host docker load`, depois `docker image inspect --format '{{.Id}}'` no destino, comparado contra PINS.json. Fail-closed: aborta antes de qualquer execução se o ID carregado divergir.

Testado (binário/Image ID adulterado aborta; correto passa; uma segunda instância de `SSHExecutor`, simulando uma campanha oficial futura, passa com os mesmos pins; nenhuma chamada invoca `docker` localmente nem faz o pipe antigo `docker save | ssh ... docker load`).

### Arquitetura de cada instância — quem roda o quê
**Correção à Decisão 56(a) (achado real da Decisão 59):** "o orquestrador e o build rodam na máquina do operador... NUNCA numa instância AWS" estava **errado** pra parte "o orquestrador". O *build* (docker build/save) continua, de fato, só na máquina do operador — mas `orchestrator.py` (`SSHExecutor`, a execução remota real) só alcança servidor/clientes de dentro do **controle** (Security Group do servidor/clientes só aceita SSH do EIP do próprio controle, `main.tf`) — `deliver_to_control()` (`deliver_source.py`, Decisão 59) entrega `orchestrator.py` + dependências pro controle, de onde ele roda de verdade. `pki_relay.py`/`collect_artifacts.py`/`cleanup.py`/`emergency_stop.py`/`iam_dryrun_check.py` continuam rodando **no operador** (nunca no controle) — falam com o controle por SSH (`pki_relay.py`/`collect_artifacts.py`) ou nem isso (`cleanup.py`/`emergency_stop.py`/`iam_dryrun_check.py`, só API AWS direta).

| Instância | Tipo | Arquitetura | Roda gateway/proxy/measure/pqc-signer? | Roda `docker` localmente? |
|---|---|---|---|---|
| Controle | `t4g.micro` | **ARM64** | **Não.** As 4 imagens (linux/amd64) nunca chegam a ser carregadas/executadas no controle — só relayadas (`.tar` estagiado por `deliver_images.py`, scp pro host, `docker load` rodando NO HOST via ssh). `orchestrator.py` roda de verdade AQUI (Decisão 59), mas nunca invoca `docker` como processo local (confirmado por teste, `test_deliver_image_nunca_invoca_docker_localmente`). | **Não — nunca.** |
| Servidor (L0, sa-east-1) | `m7i-flex.large` | x86_64 | gateway + measure (ambos amd64, batem com a arquitetura real) |
| Cliente L0 (co-localizado) | `m7i-flex.large` | x86_64 | proxy (amd64) |
| Cliente L219 (eu-north-1) | `m7i-flex.large` | x86_64 | proxy |
| Cliente L325 (ap-southeast-1) | `m7i-flex.large` | x86_64 | proxy |

Nenhuma variante ARM das 3 imagens existe nem é necessária.

### `check_capture_prerequisites` — agora confere o ID, não só presença
Corrigido (Decisão 53 só checava presença — uma imagem de origem/build diferente passaria sem ser pega): `check_capture_prerequisites(host, expected_measure_image_id=...)` reprova explicitamente se o Image ID de `mockopin-v9-measure` na instância não bater com PINS.json. Testado com ID errado (reprova) e correto (passa).

---

## d) Tolerância de bytes de handshake — derivada, validada em 20 rebuilds

**Correções desta rodada:** (1) a proposta anterior era assimétrica sem justificativa — o serial number do certificado afeta `In` E `Out`, nos 4 perfis, não só `In` do Hibrido-AND. (2) as 480 amostras anteriores vinham de um único build de certificado, nunca amostrando variação entre builds. As duas estão resolvidas pelo mecanismo abaixo, que substitui a proposta anterior inteira.

### `expected_handshake_bytes(perfil, certs_dir)`
`thesis/results/v9/integration/evaluate_criteria.py`: `esperado = baseline_medido + (soma_DER_certificados_implantados − soma_DER_certificados_do_baseline)`, por sentido (`in` = cadeia do cliente, `out` = cadeia do servidor). Nunca reestima do zero — só propaga a diferença de certificado, a única fonte de variação legítima identificada (Decisão 54, item 3) fora de SNI/tickets/MinVersion (todos já controlados ou verificados por outro mecanismo, incluindo o pin de binário do item c acima).

### Validação real: 20 rebuilds, 4 variações de SAN, 4 perfis
`make certs` rodado 20 vezes (loopback, IP privado, IP público tipo EIP, nome DNS — 5 builds cada), cobrindo os 4 perfis, gateway reconstruído e medido de verdade a cada rebuild (nunca simulado):

| Variante de SAN | Builds | Desvio (previsto − medido), todos os perfis/sentidos |
|---|---|---|
| Loopback (padrão) | 5 | **0B, todos** |
| IP privado (10.0.1.50) | 5 | **0B, todos** |
| IP público tipo EIP (203.0.113.50) | 5 | **0B, todos** |
| Nome DNS adicional | 5 | **0B, todos** |

**20/20 builds, 0B de desvio em TODOS.** Exemplo real (classico, SAN trocado de loopback para IP privado): certificado do servidor cai de 900B para 880B DER (-20B) — previsto `out=1620`, medido `out=1620`. Exato.

### Achado desta rodada (Decisão 56, item 2): o desvio contra o BASELINE também pode ser zerado, não só previsto
A técnica acima prevê corretamente qualquer desvio, mas descobrimos que dá pra **eliminar o desvio na origem**: `make certs SERVER_IPS="<IP real>,::1"` — mantendo a vírgula e o `::1` (placeholder IPv6, decorativo, nunca contatado — o mesmo papel que o próprio IP já tem no SAN, Decisão 30: só DNS importa pra verificação) — preserva EXATAMENTE a mesma contagem e tipo de entrada SAN do baseline (`127.0.0.1,::1`), já que uma entrada IPv4 sempre ocupa 4 bytes e uma IPv6 sempre 16 bytes em ASN.1 DER, **independente do valor**. Validado em 20 builds reais (10 IPs estilo privado, 10 estilo EIP público, variando o valor a cada build): **delta 0B contra o BASELINE (não só contra o previsto) nos 4 perfis, nos 2 sentidos, nos 20/20 builds, 80/80 combinações perfil×sentido.** Uma alternativa por preenchimento de nome DNS foi testada e descartada — o comprimento exato necessário não escala linearmente com o tamanho do nome (edge effects de codificação ASN.1 observados, nunca calibrado para 0B exato em 3 tentativas) — a técnica do IP+`::1` é mais simples e comprovadamente exata, preferida. Nenhuma Emenda necessária (a técnica é viável e não muda nenhum código, só o valor de `SERVER_IPS` passado em `make certs` no dia do piloto).

### Regra final proposta (pré-piloto, para aprovação — não aplicada retroativamente)
- **Os limiares pré-registrados continuam sendo o gate oficial** do critério 1: 0B no ClientHello, ±4B na Certificate, 0B nas demais mensagens (Decisão 20/29/30, nunca alterados).
- **`expected_handshake_bytes` entra como diagnóstico adicional**, nunca substituindo o gate acima. Implementado (`orchestrator._bytes_diagnostic_for_profile`, chamado pelo smoke gate): desvio previsto vs. medido ≠ 0 define `bytes_diagnostic_needs_decision=True` no manifesto — **PAUSA e pede decisão do Luciano, exatamente como o smoke gate** (nunca aborta nem ignora por conta própria). Testado (zero desvio passa; desvio detectado sinaliza a decisão pendente sem bloquear `smoke_ok`, que continua sendo decidido só pelos critérios já oficiais; mutante confirmado).

---

## e) Política IAM e verificação por dry-run

### Toda chamada EC2 que o Terraform faz (plan/apply/destroy), para os recursos de `main.tf`
| Recurso | plan (refresh) | apply (criação/alteração) | destroy |
|---|---|---|---|
| `aws_instance` | `DescribeInstances`, `DescribeInstanceAttribute`, `DescribeVolumes`, `DescribeTags` | `RunInstances`, `CreateTags`, `ModifyInstanceMetadataOptions` (IMDSv2), `ModifyInstanceAttribute` (shutdown behavior) | `TerminateInstances` |
| `aws_eip` | `DescribeAddresses` | `AllocateAddress`, `AssociateAddress`, `CreateTags` | `DisassociateAddress`, `ReleaseAddress` |
| `aws_key_pair` | `DescribeKeyPairs` | `ImportKeyPair` (a chave é fornecida via `tls_private_key`, nunca gerada pela AWS — por isso `ImportKeyPair`, não `CreateKeyPair`) | `DeleteKeyPair` |
| `aws_security_group` | `DescribeSecurityGroups` | `CreateSecurityGroup`, `CreateTags` (inclui a regra de egress, inline no recurso) | `DeleteSecurityGroup` |
| `aws_vpc_security_group_ingress_rule` (SSH + gateway) | `DescribeSecurityGroupRules` | `AuthorizeSecurityGroupIngress`, `CreateTags` | `RevokeSecurityGroupIngress` |
| `data.aws_vpc`/`data.aws_subnets` | `DescribeVpcs`, `DescribeSubnets` | — | — |
| Provider (toda operação) | `sts:GetCallerIdentity` | — | — |

### Política restrita (3 regiões + condições de tag onde o IAM permite)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LeituraGeralTresRegioes",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*", "sts:GetCallerIdentity",
        "servicequotas:GetServiceQuota", "budgets:ViewBudget", "budgets:DescribeBudgets"
      ],
      "Resource": "*",
      "Condition": { "StringEquals": { "aws:RequestedRegion": ["sa-east-1", "eu-north-1", "ap-southeast-1"] } }
    },
    {
      "Sid": "CriarSemCondicaoDeTagPossivel",
      "Effect": "Allow",
      "Action": ["ec2:RunInstances", "ec2:AllocateAddress", "ec2:ImportKeyPair", "ec2:CreateSecurityGroup"],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": ["sa-east-1", "eu-north-1", "ap-southeast-1"],
          "aws:RequestTag/Project": "mockopin-pqc-v9-piloto"
        }
      }
    },
    {
      "Sid": "CreateTagsSoNaCriacaoDesteProjeto",
      "Effect": "Allow",
      "Action": "ec2:CreateTags",
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": ["sa-east-1", "eu-north-1", "ap-southeast-1"],
          "ec2:CreateAction": ["RunInstances", "AllocateAddress", "ImportKeyPair", "CreateSecurityGroup"]
        }
      }
    },
    {
      "Sid": "ModificarSoRecursoJaTagueado",
      "Effect": "Allow",
      "Action": [
        "ec2:ModifyInstanceMetadataOptions", "ec2:ModifyInstanceAttribute", "ec2:TerminateInstances",
        "ec2:AssociateAddress", "ec2:DisassociateAddress", "ec2:ReleaseAddress", "ec2:DeleteKeyPair",
        "ec2:AuthorizeSecurityGroupIngress", "ec2:RevokeSecurityGroupIngress", "ec2:DeleteSecurityGroup"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": ["sa-east-1", "eu-north-1", "ap-southeast-1"],
          "aws:ResourceTag/Project": "mockopin-pqc-v9-piloto"
        }
      }
    }
  ]
}
```

**Limitação honesta, sem mudança possível:** `RunInstances`/`AllocateAddress`/`ImportKeyPair`/`CreateSecurityGroup` não suportam condição por `aws:ResourceTag` no momento da criação (o recurso não existe ainda) — usam `aws:RequestTag` (o que SERIA aplicado), que é o máximo que o IAM permite nesse ponto. `ec2:CreateTags` é restrito por `ec2:CreateAction` (só tageia o que acabou de ser criado por uma das 4 ações do projeto) em vez de por recurso, pela mesma razão.

### `iam_dryrun_check.py` — testado com mock, nunca executado por este processo
Chama cada ação acima com `--dry-run`, por região, usando parâmetros reais (AMIs pinadas, tipo de instância) para as ações sem recurso pré-existente; para as que exigem um recurso real (`TerminateInstances`, `ModifyInstanceAttribute`, `ReleaseAddress`, `DeleteKeyPair`, `RevokeSecurityGroupIngress`), aceita o ID como argumento opcional e marca `"nao testado"` explicitamente sem ele — nunca inventa um PASS. Testado (7 testes, `DryRunOperation`→autorizado, `UnauthorizedOperation`→reprovado, agregação por região). **O Luciano roda, com as credenciais reais, antes do piloto** (`python iam_dryrun_check.py --profile mockopin-pqc [--instance-id ... --key-name ... --sg-id ... --allocation-id ... --rule-id ...]`).

---

## f) Parada de emergência — duas camadas

### Camada 1 (normal): `cleanup.py`, depende do state do Terraform
```
python cleanup.py --tf-dir ../../terraform --profile mockopin-pqc --release-eips --force
```
Ver detalhe na seção g. Depende do `terraform destroy` funcionar (state intacto e acessível).

### Camada 2 (independente do state): `emergency_stop.py`, novo
Para o caso em que o state do Terraform está perdido, corrompido ou inacessível, mas os recursos ainda existem na conta. Age por **tag `Project=mockopin-pqc-v9-piloto`**, direto pela API, nas 3 regiões — cada ação destrutiva confere a tag (via uma chamada `describe-*` filtrada) imediatamente antes de agir, nunca sobre um ID solto.

```
python emergency_stop.py --profile mockopin-pqc --execute
```
Sem `--execute`, só lista o que seria feito (modo padrão, nunca destrutivo por acidente). Ordem: instâncias (termina, espera até 2 min antes de seguir) → EIPs (desassocia, depois libera) → grupos de segurança (só depois das instâncias realmente terminarem) → key pairs. Testado com mock (6 testes: modo dry nunca chama nada mutável; cada ação só roda sobre o ID que veio da tag; desassocia antes de liberar EIP; mutante confirmado).

### Pior caso de custo se nada for feito além do autodesligamento
Autodesligamento (`terminate`, não `stop`) sempre limita o COMPUTE — mas **nunca libera o EIP** (Decisão 45, confirmado direto no código real da v8: nenhum caminho de autodesligamento libera Elastic IP).

- **Compute, limitado pelo autodesligamento:** 4× `m7i-flex.large` por 4h + 1× `t4g.micro` por 5h ≈ (4 × US$0,0958 × 4h) + (US$0,0084 × 5h) ≈ **US$1,575**, e então para (instâncias terminadas).
- **EBS:** `delete_on_termination` é o default do provider (nunca definido como `false` em `main.tf`) — apagado junto com a instância, sem custo residual.
- **5 EIPs órfãos, SEM NENHUM LIMITE DE TEMPO:** US$0,005/h cada × 5 = **US$0,025/hora, indefinidamente**, até alguém rodar `emergency_stop.py`/`cleanup.py --release-eips` ou liberar manualmente. Em um mês esquecido: ≈ **US$18**. Pequeno, mas não-zero e sem teto — exatamente o cenário que `emergency_stop.py` (camada 2) existe para cobrir mesmo sem o Terraform.

---

## g) Alerta de orçamento — reclassificado

**Correção desta rodada:** um alerta de orçamento da AWS é uma **notificação com atraso de cobrança** (os Budgets da AWS são recalculados ~a cada 8-24h, nunca em tempo real) — nunca um limite automático que interrompe gastos. Tratá-lo como "proteção" seria otimista demais; é um alarme que avisa depois do fato, não um freio.

Já existe um alerta geral na conta (herdado da v8, valor nunca lido por este projeto, por política — Decisão 27; referência histórica em `DECISIONS.md`: US$27,72). **Sugestão revisada: US$3** (abaixo da sugestão anterior de US$5) — ainda ~2,6× a estimativa normal do piloto (US$1,15 com margem), baixo o bastante para soar o alarme rápido mesmo contra o cenário do EIP órfão (US$0,60/dia) antes que acumule muito, mas longe o bastante da estimativa normal para não disparar por flutuação de preço. Decisão final do valor é do Luciano.

---

## h) Riscos residuais — atualizados

| # | Risco | Status | Decisão pendente |
|---|---|---|---|
| 1 | Imagem `mockopin-v9-measure` precisa existir em cada instância | **RESOLVIDO** (Decisão 55, item 2) — entregue por `docker save`/`docker load`, Image ID conferido contra PINS.json, nunca `docker build` na instância | Nenhuma |
| 2 | Proxy e measure sem o mesmo mecanismo de verificação do gateway | **RESOLVIDO** (Decisão 55, itens 1-2) — os 3 agora tem pin de Image ID (gateway/proxy também tem pin de binário+`go version -m`) | Nenhuma |
| 3 | Controle sem autodesligamento por tag/projeto separado | Aceito e mitigado (`self_terminate_hours=5`, `terminate`) | Nenhuma |
| 4 | Alerta de orçamento geral, não específico do piloto | Reclassificado (item g) — ainda pendente de criação | Decidir o valor (US$3 sugerido) e criar o alerta |
| 5 | AND cobre só TLS 1.3 | Limitação de design aceita desde o pré-registro | Nenhuma |
| 6 | `handshakeBytesIn/Out` sem tolerância pré-registrada formal | **RESOLVIDO quanto ao mecanismo** (Decisão 55, item 3) — `expected_handshake_bytes` validado em 20 rebuilds reais, 0B de desvio; vira diagnóstico que pausa, nunca o gate oficial | Aprovar o mecanismo como diagnóstico permanente (não é uma mudança de critério, só uma camada nova) |
| 7 | Política IAM mais larga que o ideal em algumas ações de criação | **Documentado com justificativa técnica precisa** (item e) — é um limite real do IAM, não uma folga evitável | Aceitar como está (não há alternativa mais restrita dentro do IAM) |
| 8 (novo) | `emergency_stop.py` nunca foi executado contra a AWS real (só testado com mock) | Registrado honesto | O Luciano testa em modo dry (`sem --execute`) contra a conta real antes de confiar nele numa emergência real |

---

## i) O runbook cobre a janela de 3-4h com o Luciano presente?

Sim — sequência inalterada desta revisão (apply → PKI → preflight de captura → porta de fumaça, agora com diagnóstico de bytes → 60 execuções → coleta → cleanup), ~45min-1h20 de execução ativa dentro da janela de 4h/5h de autodesligamento, com 3 pontos de pausa/decisão explícitos (preflight de captura, porta de fumaça incluindo o novo diagnóstico de bytes, verificação final de limpeza) — todos sempre decisão do Luciano, nunca automáticos.

---

## j) O que falta, do lado do Luciano (lista curta)

1. Confirmar Service Quotas de vCPU nas 3 regiões e de Elastic IPs em `sa-east-1` (item b do dossiê original — sem mudança).
2. Gerar um par de chaves SSH pessoal e exportar `TF_VAR_operator_ssh_public_key` antes do `terraform apply`.
3. Revisar e aplicar a política IAM proposta (seção e) ao usuário/role do orquestrador — aceitar a folga documentada em `RunInstances`/`AllocateAddress`/`ImportKeyPair`/`CreateSecurityGroup`, ou ajustar por conta própria.
4. Rodar `iam_dryrun_check.py` com as credenciais reais antes do piloto, e separadamente testar `emergency_stop.py` em modo dry (sem `--execute`) contra a conta real.
5. Decidir o valor do alerta de orçamento específico do piloto (US$3 sugerido) e criá-lo.
6. Aprovar (ou pedir ajuste) o mecanismo de diagnóstico de bytes (`expected_handshake_bytes`, seção d) como camada de pausa-e-pergunta adicional ao smoke gate — nunca substitui os limiares pré-registrados.
7. Definir a data do piloto.

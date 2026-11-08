# Relatório final — execução autônoma na AWS, 2026-11-08

Luciano ausente durante toda a execução, conforme autorização
explícita. Este relatório cobre tudo que aconteceu desde a
autorização: a Fase A (ensaio de infraestrutura) fechando completa e
verde depois de 7 achados reais corrigidos ao vivo, e a decisão
deliberada de **não** iniciar a Fase B (piloto real de 60 execuções)
nesta sessão.

---

## 1. Resumo executivo

| | |
|---|---|
| **Fase A (ensaio, `INFRA_REHEARSAL.md`)** | **COMPLETA, verde, 15/15 passos (0–14), numa execução real na AWS.** |
| **Fase B (piloto, 60 execuções)** | **NÃO iniciada** — decisão deliberada, não uma parada por erro. 3 lacunas reais encontradas por pesquisa de código (nenhuma chamada à AWS) antes de tocar a conta de novo; uma delas só o Luciano pode decidir. |
| **Fase C (consolidação)** | Não aplicável ainda (depende da Fase B). |
| **Decisões numeradas registradas** | 61 a 74 (14 decisões), todas em `thesis/results/v9/DECISIONS.md`, todas commitadas e empurradas pra `v9/fase1-local`. |
| **Custo estimado, toda a sessão** | Bem abaixo de US$1 (teto autorizado: US$5). Nenhuma retentativa excedeu o limite de 3 por problema distinto. |
| **Conta AWS, ao final** | Confirmada limpa — 2 verificações independentes de 12 chamadas cada (instâncias/EIPs/security-groups/key-pairs × 3 regiões), ambas vazias. |
| **Branch** | `v9/fase1-local`. Nunca tocou `main` nem a tag `v9-prereg`. |

---

## 2. Fase A — o que de fato rodou

A Fase A foi tentada **3 vezes** nesta sessão (contando a tentativa
que já estava em andamento antes da retomada atual):

### Tentativa 1 (antes desta retomada) — parou no Passo 9
Image ID pós-`docker load` divergia entre a versão de Docker do
operador (29.9.1) e a do servidor real (25.0.16), mesmo com
binário/certificados confirmados byte-idênticos. Parada correta,
conforme as regras 6/7(e) — nenhuma correção unilateral de um
mecanismo de verificação pré-registrado sem decisão do Luciano. Frota
derrubada, conta confirmada limpa. Ver `ensaio_infra/` e Decisão 67.

**Decisão do Luciano:** autorizou trocar o mecanismo de verificação
de Image ID por conteúdo (tar sha256 + RootFS.Layers + Config +
sha256 do binário), mais uma varredura completa de CRLF/caminho do
Windows, e só depois retomar a Fase A do zero.

### Tentativa 2 (esta retomada, 1ª fleet) — parou por conectividade, não por código
Com o novo mecanismo de verificação implementado e testado (154 →
158 testes), os Passos 0–9 fecharam **completamente verdes** numa
fleet real nova. No Passo 10 (prova de mecanismo com os 4 perfis),
foram encontrados e corrigidos **3 achados reais em sequência**
(todos no mesmo script, `rehearsal_handshake.sh` — cada um uma causa
raiz genuinamente diferente). Antes de conseguir validar o último
fix ao vivo, **as 3 instâncias da fleet ficaram simultaneamente
inalcançáveis nas portas 22 e 443**, por ~8 minutos, enquanto as
chamadas da API da AWS continuavam funcionando normalmente — um
problema transitório de rota de rede, não um bug de código nem de
configuração (SG/IAM/IP do operador todos confirmados corretos e
inalterados). Pela regra "frota nunca ociosa", a frota foi derrubada
e a conta confirmada limpa. Ver Decisão 72 (nota de infraestrutura).

### Tentativa 3 (esta retomada, 2ª fleet) — COMPLETA E VERDE
Fleet nova reaplicada. Passos 0–9 novamente verdes. O Passo 10,
agora com os 3 fixes anteriores entregues, fechou
`RESULTADO FINAL: PASS -- 4/4 perfis, delta 0B nos dois sentidos`.
Passos 11–14 (parada de emergência em modo dry, teardown principal,
verificação final de 12 chamadas) todos conforme esperado. **Primeira
vez, na história deste pacote, que o roteiro de ensaio inteiro fecha
de ponta a ponta numa execução real na AWS.**

### Achados reais corrigidos nesta retomada (Decisões 68–74)

| Decisão | Achado real | Correção |
|---|---|---|
| 68 | Image ID diverge entre versões de Docker (operador vs. servidor real) | Verificação de entrega trocada pra conteúdo (tar sha256 + RootFS.Layers + Config + sha256 do binário); Image ID passa a ser só informativo |
| 69 | Varredura de CRLF/caminho do Windows no caminho remoto inteiro | `.gitattributes` ganha `*.tftpl`; teste novo varre de verdade em disco; nenhum achado novo além dos já corrigidos |
| 70 | `_launch_gateway` usava rede Docker exclusiva da validação local, travando o container num servidor EC2 real | `-p 443:443` no caso remoto real; `docker run`/espera por "listening on" agora checam erro e abortam rápido |
| 71 | `deliver_source.py` nunca instalava `requirements.txt` no cliente real (passo perdido na reescrita Python da v8) | `install_client_requirements()`, novo, roda `pip3 install --require-hashes` no cliente |
| 72 | `rehearsal_handshake.sh` tinha os mesmos defaults de caminho de certificado da validação local, quebrando no controle real | Caminho absoluto real (`/home/ec2-user/...`) quando `CLIENT_SSH`/`GATEWAY_SSH` setados |
| 73 | Mesmo script: `~` nunca expande dentro de aspas duplas pré-existentes; rede Docker exclusiva da validação local (mesma causa raiz da Decisão 70, nunca replicada aqui) | Caminho absoluto (eliminando a ambiguidade de aspas) + `-p 443:443`/sem rede, condicional ao modo remoto |
| 74 | Conflito de porta 443 com o container `v9-mtls` do Passo 9 anterior, que o `stop_block` nunca remove por design | Remoção defensiva de `v9-mtls` antes de subir o container deste script, só em modo remoto |

Nenhuma destas 7 correções alterou PINS.json, nenhum binário/certificado
pinado, nem nenhum dos 7 critérios pré-registrados do piloto — todas
são mecanismo de infraestrutura (rede, caminho, verificação de
entrega), nunca o que é medido.

### Dados reais de entrega de imagem (Decisão 68, Passo 9, 2ª fleet)
| Imagem | Tempo (2º salto, controle→host) | Tamanho do `.tar` | Verificação |
|---|---|---|---|
| gateway | 2,6s | 10.441.728 B | layers/config/binário: OK |
| proxy | 2,4s | 9.166.336 B | layers/config/binário: OK |
| pqc-signer | 2,8s | 59.075.072 B | layers/config: OK (sem binário Go próprio) |

Nenhuma entrega passou de 10s (limiar de alerta: 600s) nas duas fleets
desta retomada.

---

## 3. Fase B — por que não foi iniciada

Antes de tocar a conta AWS de novo pra Fase B, fiz uma pesquisa de
código **somente leitura** (nenhuma chamada à AWS) pra mapear a
sequência exata — não existe, pra Fase B, um roteiro passo a passo
como `INFRA_REHEARSAL.md`; só o dossiê de prontidão
(`PILOT_READINESS.md`), que descreve a sequência em prosa, não em
comandos prontos. Essa pesquisa encontrou **3 lacunas reais**, cada
uma genuína o bastante para justificar parar e perguntar em vez de
improvisar numa parte do pipeline que nunca rodou de verdade antes
(os 7 critérios do piloto, segundo o próprio `PILOT_READINESS.md`,
estão todos "só validáveis na AWS" ou "parcialmente validados
localmente" — nenhum fechou numa execução real ainda):

### 3.1. SAN real (EIP) do certificado do gateway exige rebuild de imagem — decisão do Luciano
O critério 1 (tamanhos por mensagem) menciona explicitamente "SAN
real (EIP)" como a única coisa que falta validar além da mecânica.
O `PILOT_READINESS.md`, seção d, já registrou a técnica exata
(`make certs SERVER_IPS="<EIP real>,::1"`, validada em 20 rebuilds
reais, 0B de desvio) — **mas o classifica explicitamente como uma
proposta pendente de aprovação do Luciano, "não aplicada
retroativamente"** (seção j, item 6). Além disso, o certificado do
gateway está **embutido na imagem Docker pinada** (`COPY certs
/certs` no Dockerfile, confirmado na Decisão 61) — usar um SAN real
exigiria reconstruir essa imagem, o que a regra vigente desta rodada
proíbe explicitamente até o fim do piloto. Não é um bug: é uma
decisão que só o Luciano pode tomar (aprovar o rebuild único antes do
piloto, ou aceitar deixar essa parte específica do critério 1 sem
validação de SAN real nesta rodada).

### 3.2. Smoke gate quebra sem tratamento de erro no controle
`orchestrator.run_smoke_gate` calcula um diagnóstico de bytes
(`_bytes_diagnostic_for_profile`) que lê certificados de
`thesis/results/v9/certs/generated` e importa `cryptography` — nenhum
dos dois está disponível no controle (`certs/generated` só é entregue
aos clientes; `cryptography` nunca foi instalado no controle, ARM64,
Python 3.9). A função não tem tratamento de erro nenhum ali — uma
`ModuleNotFoundError`/`FileNotFoundError` quebraria o smoke gate
inteiro antes de escrever qualquer manifesto, mesmo que os critérios
OFICIAIS (nunca o diagnóstico, que é só uma camada extra) estivessem
corretos. Correção plausível (entregar `certs/generated` + instalar
`cryptography` no controle, ou envolver o diagnóstico num
try/except que degrada sem quebrar o gate oficial) — mas decidi não
aplicá-la sem registrar o achado primeiro, porque mexe no MESMO
caminho de código que decide `smoke_ok`, a porta de fumaça que o
próprio dossiê classifica como sempre decisão do Luciano.

### 3.3. `collect_artifacts.py` não bate com a saída real de `run_pilot`
`run_pilot` escreve toda a saída da campanha (manifest, logs,
capturas) num **único diretório plano**, nunca dividido por perfil.
`collect_artifacts.py`, porém, espera uma subpasta por perfil mais
um `.sha256` por perfil no controle, e verifica cada um com um
marcador `.pull-verified`. Como estão hoje, as duas peças não se
encaixam — corrigir isso significa ou mudar como `run_pilot` escreve
sua saída (toca a estrutura que vira o dado medido de verdade da
tese) ou reescrever a coleta pra puxar o diretório plano atual. A
regra 7(e) ("dúvida sobre se uma correção altera o que está sendo
medido") se aplica diretamente aqui.

### O que NÃO foi feito, por consequência
Nenhuma fleet de Fase B foi criada; nenhum apply, nenhuma chamada
mutável à AWS pra Fase B. Toda a investigação acima foi leitura de
código local, sem custo e sem risco algum pra conta.

---

## 4. Decisões pendentes do Luciano (curto, pra decidir rápido)

1. **SAN real do gateway (criterio 1):** aprovar o rebuild único da
   imagem do gateway com `SERVER_IPS="<EIP real>,::1"` antes do
   piloto come­çar, ou aceitar rodar sem essa validação específica
   nesta rodada.
2. **Smoke gate:** como corrigir (entregar deps+certs ao controle, ou
   try/except que degrada o diagnóstico sem quebrar o gate oficial).
3. **Coleta de artefatos:** mudar `run_pilot` pra escrever por
   perfil, adaptar `collect_artifacts.py` pro layout atual, ou usar
   `scp -r` simples pra esta rodada.
4. **Roteiro da Fase B:** vale escrever um documento passo a passo
   (equivalente a `INFRA_REHEARSAL.md`) antes de qualquer tentativa
   real do piloto, dado quanto lacuna apareceu só de ler o código?

---

## 5. Log de decisões e commits desta sessão

Todas em `thesis/results/v9/DECISIONS.md`, decisões 61 a 74. Commits
em `v9/fase1-local` (mais recente primeiro):

- `08b4b04c` — Decisões 73/74 (rehearsal_handshake.sh fecha PASS)
- `e6129351` — Decisões 70/71 (_launch_gateway + pip install clientes)
- `4c58a280` — Decisão 72 (cert path, achado + nota de infraestrutura)
- `ffa2f548` — Decisões 68/69 (verificação por conteúdo + varredura CRLF)
- (commits anteriores à retomada, decisões 61–67, já na branch)

---

## 6. Confirmação de conta limpa

Duas verificações independentes de 12 chamadas cada
(`describe-instances`/`describe-addresses`/`describe-security-groups`/
`describe-key-pairs`, filtradas por `tag:Project=mockopin-pqc-v9-piloto`,
nas 3 regiões `sa-east-1`/`eu-north-1`/`ap-southeast-1`) — a primeira
após a fleet da Tentativa 2 (conectividade), a segunda após a fleet
da Tentativa 3 (final). **Todas as 24 chamadas devolveram listas
vazias.** `cleanup.py` também reportou `all_clean: true` nas duas
vezes, sem drift.

---

## 7. Árvore de arquivos deste relatório

```
thesis/results/v9/piloto/
├── README.md                      (índice)
├── RELATORIO_SESSAO.md            (este arquivo)
├── estado.json                    (estado estruturado)
├── PARADA.md                      (histórico -- 1ª parada, Decisão 67)
├── pre_voo_testes.log
├── ensaio_infra/                  (1ª tentativa, parou no Passo 9)
│   ├── IDENTIDADE.json
│   └── logs/ (8 arquivos)
└── ensaio_infra_retomada/         (retomada, fechou completa e verde)
    ├── IDENTIDADE.json
    └── logs/ (10 arquivos, redigidos)
```

---

## 8. Próximo passo sugerido

Com a Fase A comprovada de ponta a ponta, o trabalho que falta antes
de uma tentativa real da Fase B é inteiramente de decisão/revisão do
Luciano (seção 4), não mais de execução. Nenhuma ação adicional foi
tomada contra a AWS depois deste ponto.

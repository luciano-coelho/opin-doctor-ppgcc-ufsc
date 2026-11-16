# Degrau 1 — investigação exploratória da origem das diferenças de latência

Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC. Investigação separada do relatório oficial (`Consolidated_Metrics_Report_FINAL.md`, intocado), sem AWS, a partir SOMENTE de dados já salvos localmente. Pré-registro completo em `PLANO.md` (commitado antes de qualquer análise rodar). Scripts e dados brutos das análises em `scripts/` e `data/`.

## Resumo dos vereditos

| Hipótese | Veredito |
|---|---|
| H1 (ordem do bloco / deriva temporal) | **REFUTADA** (claim principal); achado secundário real não previsto (ver abaixo) |
| H2 (viagens de rede extras / initcwnd) | **REFUTADA** (critério de decisão revisto após auditoria — ver abaixo; IC exclui ativamente o valor teórico, não apenas inclui zero) |
| H3 (custo de CPU das primitivas) | **REFUTADA** só para a reimplementação em Go testada; **INCONCLUSIVA** para a pilha real (Python+Go+Node.js) — custo real do cliente não medido (ver abaixo) |
| H4 (heterogeneidade entre instalações) | **SUSTENTADA** (existência); **INCONCLUSIVA quanto à causa exata** |

**Nota crítica sobre a própria medição (ver seção "Verificação crítica" abaixo):** "T_fluxo", usado em TODAS as seções acima e no relatório oficial, inclui a chamada SSH completa do host de controle até o cliente (confirmado no código), não só as 44 chamadas HTTP cliente-servidor. Uma regressão (item 5b) estima que o excesso tem pelo menos dois componentes reais, estatisticamente distintos de zero: um escalando com o RTT controle-cliente (~13 viagens de rede, compatível com overhead de SSH) e outro com o RTT real cliente-servidor (~19 viagens de rede) — além de um custo fixo (~1,8s) independente de ambos. A métrica, como definida no pipeline, não separa esses componentes.

## H1 — ordem do bloco / deriva temporal: REFUTADA

**Previsão:** posição do bloco (1º-4º) correlaciona com T_fluxo mediano, na mesma direção na maioria das 8 rotas.

**Resultado real** (`scripts/etapa1_h1_order.py`, `data/etapa1_h1_order.json`): correlação de Spearman combinada (32 pontos, posição × mediana) = **-0,009** (essencialmente zero); teste de permutação (8 rotas, posições embaralhadas dentro de cada rota, 10.000 permutações, semente `20270101`): **p = 0,7682**. Por rota, os 8 coeficientes de Spearman variam em ambas as direções (de -0,8 a +0,6), nenhum individualmente significativo (n=4 por rota). **A previsão principal não se sustenta: a posição do bloco na ordem da rota não explica o T_fluxo.**

**Achado secundário real, não previsto pela hipótese como formulada:** a tendência **dentro** de cada bloco (as 10 execuções de um perfil/rota, em ordem temporal real confirmada pelo campo `run`) é significativa (τ de Kendall, p<0,05) em **8 das 32 células** — mais do que o ~5% esperado por puro acaso (~1,6/32). Das 8 células significativas, **7 têm tau negativo** (tendência decrescente — execuções mais tardias dentro do bloco ficam mais rápidas, um padrão de "assentamento"): `classico/L219` (τ=-0,556), `classico/L0-us-east-1` (τ=-0,600), `classico/L30` (τ=-0,556), `pqc/L14` (τ=-0,733), `pqc/L0-ap-northeast-1` (τ=-0,644), `hibrido-v8/L0-us-east-1` (τ=-0,733), `hibrido-and/L0-us-east-1` (τ=-0,511); 1 positiva: `pqc/L325` (τ=+0,600). Isso é um fenômeno relacionado mas **distinto** do que H1 propunha (que era sobre a posição do bloco entre perfis, não sobre a ordem interna das 10 execuções de um único bloco) — registrado honestamente aqui, sem forçá-lo a sustentar a hipótese original.

## H2 — viagens de rede extras / initcwnd: REFUTADA (critério de decisão revisto)

**Previsão:** inclinação de Dif(ms) vs. RTT aproximadamente igual ao número de round-trips extras que o volume de bytes extra exigiria, dado o `cwnd`/MSS reais.

**Parâmetros reais** (critério 2, nunca assumidos): `cwnd` inicial = **10** segmentos, MSS = **1.448 bytes** (primeira janela = 14.480 bytes, confirmado exatamente no dado real). Bytes totais reais por execução: Classic = 121.641B, PQC = 280.900B, Hybrid = 337.149B.

**Critério de decisão revisto (correção pós-auditoria, mais rigoroso que o do `PLANO.md` original):** o `PLANO.md` original refutava H2 se o IC incluísse zero OU fosse incompatível com K teórico — um critério permissivo demais, porque "IC inclui zero" por si só não distingue "não há efeito" de "há efeito, mas os dados não têm poder estatístico pra confirmá-lo". Critério aplicado agora: **REFUTADA somente se o IC exclui ativamente o K teórico previsto**; se o IC incluir tanto zero quanto K teórico ao mesmo tempo (sem poder estatístico pra distinguir os dois cenários), o veredito correto é **INCONCLUSIVA**, não REFUTADA.

**Agrupamento e número de pontos (transparência explícita):** o ajuste é feito **agrupando (pooled) as 8 rotas**, não por instalação separadamente — as 8 rotas vêm de só 3 instalações físicas, com poucos RTTs distintos cada: sa-east-1 contribui **4** pontos (L0-sa-east-1 RTT=0,129ms; L123=122,642ms; L219=220,151ms; L325=323,406ms); us-east-1 contribui **2** (L0-us-east-1=0,287ms; L14=14,759ms); ap-northeast-1 contribui **2** (L0-ap-northeast-1=0,105ms; L30=33,423ms). Duas das 3 instalações têm só 2 RTTs distintos — insuficiente para uma regressão própria com grau de liberdade >0 — por isso o ajuste pré-registrado usa os 8 pontos agrupados (n=8), já ciente de que isso mistura RTT com o efeito de instalação que H4 mostra ser real.

**Resultado agrupado (n=8, `scripts/etapa1_decomp_h2_h4.py`):**
- PQC−Classic: inclinação = **0,868** ms/ms de RTT, IC 95% bootstrap (10.000 reamostragens, semente `20270102`) = **[-0,322; 2,138]**. K teórico = **3,585**. **O IC EXCLUI o valor teórico** (limite superior 2,14 < 3,58) — REFUTADA para este par.
- Hybrid−PQC: inclinação = **0,358** ms/ms, IC = **[-0,786; 0,664]**. K teórico = **2,288**. **O IC EXCLUI o valor teórico** (limite superior 0,66 < 2,29) — REFUTADA para este par.

Em nenhum dos dois pares o IC inclui o K teórico junto com zero — a condição para INCONCLUSIVA não se aplica: os dados excluem ativamente a magnitude prevista pelo modelo de slow-start, não apenas falham em confirmá-la. **Veredito mantido: REFUTADA, agora sob o critério mais rigoroso.**

**Verificação suplementar de transparência** (`scripts/etapa1_verificacoes_adicionais.py`, mesma semente `20270102`; n=4, frágil, NÃO substitui o resultado agrupado pré-registrado acima): refazendo o ajuste só com os 4 pontos de sa-east-1 (a única instalação com mais de 2 RTTs distintos, evitando misturar RTT com o efeito de instalação): PQC−Classic dá inclinação **1,980**, IC = **[1,502; 2,713]** — aqui o IC **exclui zero** (há uma relação real e positiva com o RTT dentro desta instalação isolada) mas também exclui o K teórico de 3,585 (direção certa, magnitude menor que a prevista). Hybrid−PQC dentro de sa-east-1: inclinação **0,396**, IC = **[-0,570; 1,010]** — inclui zero, exclui o K teórico de 2,288. Esta verificação reforça a mesma conclusão por outro caminho: mesmo isolando o efeito de instalação, nenhum dos dois pares atinge a magnitude de round-trips extras que o modelo de slow-start prevê.

## H3 — custo de CPU das primitivas: REFUTADA para a reimplementação em Go testada; INCONCLUSIVA para a pilha real

**Previsão:** nas rotas `L0-*` (RTT~0), a diferença de T_fluxo deve ser da mesma ordem de grandeza (razão entre 0,5x e 2x, declarado a priori) que a diferença de custo de CPU prevista pelo microbenchmark local.

**Correção importante pós-auditoria — de que linguagem/runtime é feito o cliente real, confirmado no código (não suposto):** o microbenchmark mediu TUDO em Go. Isso só é diretamente comparável se o cliente real também executasse essas operações em Go — o que NÃO é o caso para todas elas. Lendo o código real do cliente (`thesis/scripts/opin_flow.py` e os processos que ele orquestra):
- **KEM (ML-KEM-1024 / combinador `SecP384r1MLKEM1024` / P-384 clássico):** o handshake TLS real é feito por um processo Go SEPARADO (`thesis/scripts/tls_kem_proxy/main.go`, módulo `tls_kem_proxy`, Go 1.27rc2, imagem `golang:1.27-rc-alpine`) — um proxy local que faz um handshake `crypto/tls` REAL (não uma chamada de API crua), com `CurvePreferences` igual a `tls.MLKEM1024`/`tls.SecP384r1MLKEM1024`/`tls.CurveP384` conforme o perfil (confirmado nas linhas ~159-197 de `main.go`). O cliente Python (`opin_flow.py`) só conecta a esse proxy via `127.0.0.1:TLS_KEM_PROXY_PORT` — ele mesmo nunca implementa KEM.
- **ML-DSA-65 (assinatura E verificação, roteadas pelos 3 perfis por desenho — ver `start_pqc_signer_service()` em `opin_flow.py`):** feitas por um processo **Node.js** separado (`thesis/scripts/pqc-signer/server.mjs`/`signer_core.mjs`, pacote `jose@6.0.0`), que chama DIRETAMENTE a WebCrypto nativa do runtime (`node:crypto`'s `webcrypto.subtle.sign`/`.verify({name: 'ML-DSA-65'})`, confirmado nas linhas 85/151-152/282/289 de `signer_core.mjs`) — não é Go, não é Python, e não é nenhuma biblioteca PQC de terceiros em JavaScript: é suporte nativo de ML-DSA no próprio `node:crypto`.
- **RSA-2048/PS256 (assinatura clássica, termo JWT do perfil Classic/Hybrid):** esta sim roda em **Python**, de fato, via `pyjwt.encode(claims, signing_key, algorithm="PS256")` (confirmado nas linhas 1574 e 1627 de `opin_flow.py`), que por sua vez delega a assinatura RSA à biblioteca `cryptography` (hazmat).

**Portanto: a premissa "o cliente real é Python" é só parcialmente correta.** `opin_flow.py` (Python, `requests`/`urllib3`) é de fato o processo que orquestra as chamadas HTTP e assina RSA/PS256 real — mas o KEM e o ML-DSA-65 (as duas primitivas PQC centrais desta investigação) **não rodam em Python**: rodam em processos separados, em **Go** (KEM, via handshake TLS completo, não uma chamada de API isolada) e **Node.js** (ML-DSA-65, via WebCrypto nativa), respectivamente.

**O que isso significa para o microbenchmark desta investigação:** ele mediu tudo em Go (`thesis/results/v9/integration/bench/main.go` + `bench_chain/`, nunca modificados). Para o KEM, isso é a mesma linguagem/runtime do processo real (`tls_kem_proxy`, também Go/`crypto/tls`), mas mede operações isoladas de keygen/encapsulate/decapsulate, não o handshake TLS completo (que tem overhead adicional de record layer, parsing de certificado e round-trips de rede) — uma aproximação razoável, não uma medição direta do caminho real. Para ML-DSA-65, o microbenchmark usou a implementação **Go** da primitiva — **não** a implementação Node.js/WebCrypto que o pipeline real usa; nenhum benchmark Node.js foi rodado nesta investigação. Para RSA-2048, o microbenchmark usou `crypto/rsa` do Go — o pipeline real assina RSA/PS256 em **Python** via `pyjwt`+`cryptography`; também não medido aqui.

**Microbenchmark local** (`scripts/` via Docker, imagem `mockopin-v9-toolchain` — mesma toolchain Go 1.27.3 do projeto; hardware: notebook do operador, Intel Core 7 150U, 10 núcleos — ver `data/microbench_hardware.txt`; saída completa em `data/microbench_primitives_raw.txt` e `data/microbench_chain_raw.txt`):

| Operação | ns/op |
|---|---:|
| RSA-2048 sign (PSS-SHA256) | 902.882 |
| RSA-2048 verify | 30.604 |
| ML-DSA-65 sign | 535.535 |
| ML-DSA-65 verify | 144.189 |
| ECDH P-384 keygen | 108.071 |
| ECDH P-384 compute (KEX) | 494.856 |
| ML-KEM-1024 keygen | 74.711 |
| ML-KEM-1024 encapsulate | 49.449 |
| ML-KEM-1024 decapsulate | 72.132 |
| Validação de cadeia, Classic (RSA) | 30.621 |
| Validação de cadeia, PQC (ML-DSA-65) | 151.844 |
| Validação de cadeia, Control (RSA) | 27.337 |
| Validação de cadeia, Hybrid (RSA, só a primária — ver limitação abaixo) | 23.191 |

**Custo total previsto por execução** (KEX×6 conexões + assinatura×26 tokens não-JWE + validação de cadeia×6, contagens reais já confirmadas no relatório oficial): Classic = 27,28ms; PQC = 16,01ms; Control = 42,38ms; Hybrid = 42,33ms.

**Comparação com a diferença real observada (rotas L0, mediana real):**

| Par | Previsto (ms) | L0-sa-east-1 (observado, ms) | L0-us-east-1 (observado, ms) | L0-ap-northeast-1 (observado, ms) |
|---|---:|---:|---:|---:|
| PQC vs. Classic | -11,26 | -69,0 (razão 0,16x) | +223,4 (razão -0,05x) | +462,4 (razão -0,02x) |
| Hybrid vs. PQC | +26,32 | +275,7 (razão 0,10x) | +167,7 (razão 0,16x) | +367,7 (razão 0,07x) |

**Nenhuma das 6 comparações cai na faixa [0,5x; 2x] declarada a priori** — em 2 dos 6 casos (ambos no par PQC vs. Classic: L0-us-east-1 e L0-ap-northeast-1) a previsão tem até o SINAL errado em relação ao observado.

**Veredito, com a correção de linguagem/runtime acima:** para a **reimplementação em Go** testada por este microbenchmark, a hipótese está **REFUTADA** — nem a magnitude, nem (em 2 dos 6 casos) a direção são explicadas. Mas isso não pode ser estendido à afirmação "o custo de CPU da pilha real não explica a diferença", porque a pilha real usa Node.js (ML-DSA-65) e Python (RSA/PS256) para as partes que mais importam aqui, e nenhuma delas foi medida. **Para a pilha real completa, o veredito correto é INCONCLUSIVA** — não porque haja evidência de que o custo real explicaria a diferença, mas porque essa possibilidade nunca foi testada diretamente.

**Limitação de escopo explícita:** a verificação adicional do `AltSignatureValue` ML-DSA-65 do Hybrid (callback customizado, fora do `x509.Verify` padrão) não foi reproduzida no microbenchmark de cadeia — só a cadeia RSA primária foi medida para Hybrid. Isso subestima ligeiramente o custo previsto de Hybrid, mas não o suficiente para mudar a conclusão (a diferença entre previsto e observado é de uma a duas ordens de grandeza).

## H4 — heterogeneidade entre as 3 instalações: SUSTENTADA (existência); INCONCLUSIVA (causa exata)

**Previsão:** T_fluxo do perfil Classic nas 3 rotas `L0-*` difere significativamente entre si, mesmo com RTT~0 nas 3.

**Resultado real** (Mann-Whitney exato bilateral, n=10 cada, correção de Holm sobre a família de 3 testes): as 3 comparações batem no **menor p-valor matematicamente possível** (p bruto = 1,0825×10⁻⁵, p Holm = 3,2×10⁻⁵) — `sa-east-1` (mediana 2.357,9ms) < `us-east-1` (3.817,0ms) < `ap-northeast-1` (5.786,2ms). **Sustentada, sem ambiguidade: as 3 instalações diferem muito entre si, mesmo sendo o mesmo perfil sob RTT efetivamente igual.**

**Decomposição real para localizar a origem** (soma das 44 `latency_ms` reais por execução vs. resíduo = T_fluxo − essa soma):

| Instalação | Soma das chamadas (mediana, ms) | T_fluxo (mediana, ms) | Resíduo (mediana, ms) | Resíduo, % do T_fluxo |
|---|---:|---:|---:|---:|
| sa-east-1 | 475,3 | 2.357,9 | 1.882,0 | 79,8% |
| us-east-1 | 486,2 | 3.817,0 | 3.352,8 | 87,8% |
| ap-northeast-1 | 399,8 | 5.786,2 | 5.395,4 | 93,2% |

**A soma das chamadas HTTP individuais é praticamente constante entre as 3 instalações (400-486ms) — quase toda a diferença entre instalações (de 1.882ms a 5.395ms) mora no RESÍDUO**, não nas chamadas de aplicação medidas individualmente. Isso localiza a diferença fora do que a aplicação mede por chamada — mas o achado da Etapa 0 (não existe campo de tempo de CPU por fase nem de duração de handshake por execução) impede ir além disso com os dados já existentes.

**Tentativa adicional, real, que NÃO ajudou a explicar:** medi a duração real de captura das 32 capturas dedicadas (um pcap por perfil/rota, via `scapy`, offline, local) para Classic nas 3 rotas L0 — `sa-east-1`: 293 pacotes, 2,313s de captura; `us-east-1`: 291 pacotes, 2,153s; `ap-northeast-1`: 290 pacotes, 2,147s. **As durações das capturas dedicadas são praticamente IGUAIS entre as 3 instalações** — não acompanham a diferença de ~3,4 segundos observada nas 320 execuções cronometradas reais. Isso significa que a captura dedicada (uma amostra única, não-cronometrada da mesma forma que as 320 execuções oficiais) **não serve como evidência adicional aqui** — é citada por transparência, não escondida, mas não resolve a pergunta.

**Veredito, portanto:** a existência da heterogeneidade entre instalações é **SUSTENTADA** com a maior confiança estatística possível neste desenho (p no limite matemático do teste). A **causa exata** (hardware da instância, condições de rede locais no momento da coleta, agendamento do hypervisor, latência interna da VPC, ou outro fator) fica **INCONCLUSIVA** — nenhuma atribuição de causa é feita além do que os dados mostram diretamente (o resíduo, não as chamadas de aplicação, carrega a diferença).

## Verificação adicional — hardware/ambiente entre as 3 instalações

**Pergunta:** há alguma diferença real documentada de hardware/ambiente entre as 3 instalações (`sa-east-1`/`us-east-1`/`ap-northeast-1`, servidores e clientes) que ajude a explicar a heterogeneidade de H4? Sem AWS, sem tocar nos dados brutos — só a partir do que já estava coletado localmente.

**Fontes:** `thesis/results/v9/campaign_oficial_conta_nova_host_facts.md` (auditoria somente-leitura já existente, feita antes de qualquer decisão de teardown, nenhuma chamada nova à AWS nesta verificação) + o campo `cpu_client`/`cpu_server` (`steal_pct`/`util_pct`) já presente em cada uma das 320 execuções de `piloto_calls.json` (dado já coletado pela própria campanha, nenhuma captura nova — recálculo em `scripts/etapa1_verificacoes_adicionais.py`, dados em `data/etapa1_verificacoes_adicionais.json`).

**O que o `host_facts.md` já documenta, byte-a-byte idêntico entre os 3 servidores (e entre os 8 clientes) — SEM EXCEÇÃO:** tipo de instância (`m7i-flex.large`, mesma SKU nas 3 regiões), contagem de vCPUs (2), memória (7,6Gi), versão de kernel (`6.1.189-236.400.amzn2023`, x86_64), versão do Docker, padrão de interface/sub-rede (mesmo `/20`), `tc qdisc` (mesmo `fq_codel`, mesmos parâmetros) e os 6 sysctls `net.ipv4.tcp_*` auditados (mesma `congestion_control=cubic`, mesmos `tcp_rmem`/`tcp_wmem` etc.). **Nenhuma divergência de configuração de SO/rede foi encontrada entre as 3 instalações** — a única diferença documentada é a esperada (AMI/IP por região, inerente a rodar em regiões AWS diferentes).

**O que NÃO está documentado nesse arquivo (honesto, não suposto):** modelo exato de CPU, frequência de clock, flags de `/proc/cpuinfo` — o `host_facts.md` registra só a CONTAGEM de vCPUs (2), nunca modelo/flags/frequência. Busca no repositório inteiro confirma: **nenhum arquivo contém uma captura de `/proc/cpuinfo`, `lscpu` ou `mpstat` dos hosts da campanha** — esse dado específico nunca foi coletado em nenhuma rodada anterior, e não pode ser reconstruído sem reconectar à AWS (explicitamente fora do escopo desta verificação). Não invento esse número.

**O que os dados já coletados mostram** (perfil Classic, 3 rotas L0, RTT~0, n=10 cada):

| Instalação | `steal_pct` cliente (mediana) | `steal_pct` servidor (mediana) | `util_pct` cliente (mediana) | `util_pct` servidor (mediana) | T_fluxo (mediana, ms, de H4) |
|---|---:|---:|---:|---:|---:|
| sa-east-1 | 0,0% | 0,0% | 10,16% | 20,52% | 2.357,9 |
| us-east-1 | 0,0% (máx. isolado 0,072%) | 0,0% (máx. isolado 0,072%) | 8,45% | 11,55% | 3.817,0 |
| ap-northeast-1 | 0,0% (máx. isolado 0,04%) | 0,0% (máx. isolado 0,04%) | 4,73% | 8,71% | 5.786,2 |

**Duas leituras honestas:**
1. **`steal_pct` é essencialmente 0 nas 3 instalações, sem exceção** — isso afasta "contenção de CPU por vizinho ruidoso no hypervisor" (um candidato razoável a priori) como explicação para a heterogeneidade: não há evidência de CPU roubada em nenhuma das 3.
2. **`util_pct` CAI conforme o T_fluxo SOBE entre instalações** — sa-east-1 (T_fluxo mais baixo) tem a maior utilização de CPU; ap-northeast-1 (T_fluxo mais alto) tem a menor. Essa relação é a OPOSTA do que se esperaria se a instalação mais lenta estivesse CPU-bound (fazendo o mesmo trabalho de CPU, porém mais lentamente, teria utilização igual ou maior, não menor). É, em vez disso, consistente com a leitura já feita em H4: se o tempo extra é dominado por espera (I/O, rede, agendamento do SO) e não por trabalho de CPU, a mesma quantidade de segundos de CPU se dilui numa janela de parede mais longa, baixando o percentual médio. **Isso não prova a causa do resíduo, mas é mais uma evidência na direção de "espera", não "CPU", consistente com a decomposição já reportada em H4 acima.**

**Conclusão desta verificação:** nenhuma divergência de hardware/SO/rede documentada explica H4 — todas as variáveis auditadas são idênticas entre as 3 instalações. A única variável que de fato varia (`util_pct`) varia na direção OPOSTA a uma explicação "CPU mais lento/mais carregado", e `steal_pct` é zero. **A causa exata de H4 permanece INCONCLUSIVA** (nenhuma mudança no veredito), mas o espaço de hipóteses candidatas fica mais restrito: nem contenção de CPU (steal), nem configuração de SO/kernel/rede documentada, nem um cenário simples CPU-bound (pela leitura do `util_pct`) parecem explicar o resíduo — resta como lacuna real, não suposição, para um futuro "Degrau 2".

## Verificação crítica — o que T_fluxo realmente mede (o próprio artefato de medição)

**Motivação (observação real do usuário):** comparando o T_fluxo mediano de Classic em L0 contra a duração da captura dedicada do MESMO perfil/rota (seção H4 acima): `sa-east-1` 2,358s vs. 2,313-2,417s; `us-east-1` 3,817s vs. 3,538s; `ap-northeast-1` 5,786s vs. 3,493s. O excesso parece crescer com a distância física de `sa-east-1` — levantando a hipótese de que T_fluxo pode incluir overhead de ORQUESTRAÇÃO dependente da região (ex. SSH do controle até o cliente), não só as 44 chamadas HTTP cliente-servidor. As 5 perguntas abaixo foram verificadas direto no código e nos dados reais, nunca supostas.

### Item 1 — exatamente o que está dentro da janela t0..t1: SUSTENTADO (confirmado no código, não é inferência estatística)

Lendo `thesis/results/v9/campaign/scripts/orchestrator.py` linha a linha (método `run_execution`, linhas 1416-1522) e os dois arquivos que ele invoca remotamente:

- **`orchestrator.py:1449`**: `t0 = datetime.now(timezone.utc)` — tomado no processo do CONTROLE, **antes mesmo de o subprocesso `ssh` ser disparado**.
- **`orchestrator.py:1450`** → **`cli.py:133-153`** (`run_ssh`): dispara um processo `ssh` NOVO a cada chamada — **nenhuma opção `ControlMaster`/`ControlPersist`/multiplexação em lugar nenhum** do `argv` montado (confirmado lendo `cli.py:147-152`). Isso significa que cada uma das 320 execuções paga uma conexão SSH FRESCA (não reaproveitada): handshake TCP controle↔cliente (1 RTT), troca de versão do protocolo SSH, key exchange (KEX) + autenticação por chave pública (mais RTTs, mesma distância controle↔cliente) — tudo isso ANTES do comando remoto nem começar a rodar.
- **Comando remoto disparado**: `cd ~/thesis/scripts && {env_prefix} python3 campaign_client_runner.py --label {label}` (`orchestrator.py:1430`) — no CLIENTE, isto inicia um **processo Python novo, do zero** (cold start, nenhum processo reaproveitado), que importa `argparse`, `json`, `os`, `sys`, `latency_automation`, `opin_flow` (`campaign_client_runner.py:23-29`) — custo real de CPU/disco no cliente, sem rede, mas dentro da janela.
- **`latency_automation.py:257`**: `of.load_client_signing_key(crypto_profile)` — chamado **antes** de `t_start` ser marcado (linha 264) dentro de `run_once_timed()`. O comentário do próprio código (linhas 247-256) menciona um custo nomeado: "classic/hybrid's RSA-4096 key-object construction, ~252ms" — fora da medição interna da lib, mas DENTRO da janela SSH do orquestrador. **Correção (ver Item 6-7): o comentário descreve RSA-4096, mas a chave real usada pela campanha oficial é RSA-2048 desde a Decisão 113 (2026-11-10, antes da campanha rodar) — o custo real medido localmente é ~27ms, não ~252ms.**
- **Achado central, nunca antes notado nesta investigação**: `latency_automation.run_once_timed()` (linhas 213-314) já computa, A CADA EXECUÇÃO, um T_fluxo PRÓPRIO, local ao cliente, com `time.monotonic()` (`t_start`/`t_end`, linhas 264/267) cercando SÓ `run_insurance_flow`+`run_person_flow` — e um `phase_accounting` completo (`http_calls_seconds`, `signing_seconds`, `verification_seconds`, `explicit_wait_seconds`, `setup_seconds`, e um `residual_seconds` residual explícito, documentado no código como "o hop do TLS-KEM-proxy e o handshake mTLS/KEM que ele faz... overhead do interpretador Python", por subtração). **Este dado rico é retornado por `campaign_client_runner.py` (via stdout JSON) mas `orchestrator.py` (linhas 1504-1522) DESCARTA `result["t_fluxo_seconds"]` e `result["phase_accounting"]` inteiramente** — só mantém `result.get("calls", [])` (renomeado `"insurance"`) e substitui a medição por SEU PRÓPRIO `t0`/`t1`, que cerca a chamada SSH inteira. **Confirmado por inspeção direta de `piloto_calls.json`: os campos `t_fluxo_seconds`/`phase_accounting` não existem em nenhuma execução.**
- Depois do fluxo real (44 chamadas HTTP + assinatura + verificação + espera explícita, medidos mas descartados): `print(json.dumps(result))` no cliente, capturado via stdout do SSH no controle (mais tempo de rede controle↔cliente proporcional ao payload) + encerramento da sessão SSH (mais RTTs).
- **`orchestrator.py:1472`**: `t1 = datetime.now(timezone.utc)` — só depois que TUDO isso (incluindo o encerramento da conexão SSH) terminou.

**Conclusão do item 1:** SUSTENTADO, com certeza (não é estatística, é leitura direta do código): `start_utc`/`end_utc` (= "T_fluxo" usado em TODO este documento e no relatório oficial) cerca literalmente a chamada SSH inteira, não só as 44 chamadas HTTP — e a lib de medição já teria uma decomposição melhor (`t_fluxo_seconds`/`phase_accounting`) que o orquestrador descarta antes de persistir.

### Item 2 — região do controle e caminho de rede: SUSTENTADO

Confirmado em `thesis/results/v9/campaign_oficial_conta_nova_host_facts.md`: o host de controle está em **`sa-east-1`** (`control | control | sa-east-1 | 172.31.25.65 | ...`). Como `cli.run_ssh()` sempre disca o IP PÚBLICO do alvo (Decisão 43/45, citada no docstring de `run_ssh`), **para 7 das 8 rotas (todas exceto `L0-sa-east-1`, cujo cliente está co-localizado em `sa-east-1`), a chamada SSH de cada uma das 320 execuções atravessa a rede pública até uma região diferente da do controle** — exatamente o caminho que o usuário descreveu.

### Item 3 — excesso (T_fluxo − captura dedicada) ÷ RTT: INCONCLUSIVO (indicador ruidoso) — mas ver item 5 abaixo, que resolve isso de forma mais robusta

Recalculado para TODOS os perfis/rotas disponíveis (não só Classic/L0 como na Etapa 1 original), via `scripts/etapa1_verificacao_artefato_medicao.py` (scapy, offline, todas as capturas dedicadas em `criterio1_capturas/capturas_brutas/`, mediana quando há mais de uma tentativa):

| Perfil/rota | T_fluxo mediano (s) | Captura dedicada (mediana, s) | Excesso (s) |
|---|---:|---:|---:|
| classico/L0-sa-east-1 | 2,358 | 2,417 (n=3) | -0,059 |
| classico/L0-us-east-1 | 3,817 | 3,538 (n=2) | +0,279 |
| classico/L0-ap-northeast-1 | 5,786 | 3,493 (n=2) | +2,293 |
| pqc/L0-sa-east-1 | 2,289 | 3,730 (n=2) | **-1,441** |
| hibrido-v8/L0-sa-east-1 | 2,472 | 4,062 (n=2) | **-1,590** |
| hibrido-and/L0-sa-east-1 | 2,565 | 4,007 (n=2) | **-1,443** |

**Achado honesto, não escondido:** para Classic, o padrão "excesso cresce com a distância de `sa-east-1`" aparece de forma fraca (quase zero em `sa-east-1`, crescente nas outras 2 instalações) — mas para PQC/Hybrid/Control, o excesso em `sa-east-1` é **FORTEMENTE NEGATIVO** (a captura dedicada durou MAIS que a mediana real de 10 execuções cronometradas). Isso significa que a captura dedicada (1-3 amostras não-cronometradas junto com as 320 execuções oficiais, já advertido como limitação na Etapa 1 original) é **ruim demais como comparador** — sinal inconsistente entre perfis, não serve pra estimar com confiança quanto da janela é overhead de SSH especificamente. **Veredito: INCONCLUSIVO por esta via** — não porque não exista overhead (o item 1 já prova que existe), mas porque este indicador específico não tem poder estatístico suficiente pra quantificá-lo. A pergunta é respondida de forma muito mais robusta no item 5.

**RTT controle↔cliente usado como referência, por rota (transparência total sobre o que é real vs. aproximado):**

| Rota | RTT controle↔cliente (ms) | Fonte |
|---|---:|---|
| L0-sa-east-1 | 0,129 | REAL (controle e cliente co-localizados em sa-east-1) |
| L123 | 122,642 | REAL (servidor sa-east-1 co-localizado com o controle) |
| L219 | 220,151 | REAL (idem) |
| L325 | 323,406 | REAL (idem) |
| L14 | 122,642 (derivado) | DERIVADO — cliente de L14 está na MESMA região de L123 (ca-central-1); usa o RTT real de L123 como proxy |
| L0-us-east-1 | sem medição | **APROXIMAÇÃO EXTERNA, não medida nesta campanha**: faixa tipicamente citada publicamente para sa-east-1↔us-east-1, ~105-120ms |
| L0-ap-northeast-1 | sem medição | **APROXIMAÇÃO EXTERNA**: faixa tipicamente citada para sa-east-1↔ap-northeast-1, ~270-300ms |
| L30 | sem medição | **APROXIMAÇÃO EXTERNA**: faixa próxima de sa-east-1↔ap-northeast-1 + o RTT real medido ap-northeast-1↔ap-northeast-2 (33,423ms) |

Como declarado explicitamente na tabela: para `L0-us-east-1`/`L0-ap-northeast-1`/`L30` **não existe nenhuma medição real ou derivável desta campanha** de RTT controle↔cliente (o RTT medido pela campanha é sempre cliente↔servidor; só é um proxy real de controle↔cliente nas rotas onde o SERVIDOR da rota coincide com a região do controle, `sa-east-1`). Nenhum número preciso foi inventado para as 3 rotas sem medição — só uma faixa, claramente rotulada como conhecimento externo.

### Item 4 — a diferença ENTRE PERFIS mora nas chamadas ou no resíduo?

Recalculado com precisão total (sem arredondar antes de subtrair), `scripts/etapa1_verificacao_artefato_medicao.py`:

| Rota | Δ(soma chamadas) PQC−Classic (ms) | Δ(resíduo) PQC−Classic (ms) | Δ(soma chamadas) Hybrid−PQC (ms) | Δ(resíduo) Hybrid−PQC (ms) |
|---|---:|---:|---:|---:|
| L0-sa-east-1 | -27 | -42 | +113 | +163 |
| L0-us-east-1 | -13 | +236 | +72 | +95 |
| L0-ap-northeast-1 | +6 | +456 | +51 | +317 |
| L123 | -12 | +276 | +49 | +157 |
| L219 | -1 | +423 | +54 | +237 |
| L325 | -6 | +584 | +19 | +376 |
| L14 | +21 | +267 | +46 | +124 |
| L30 | -43 | +597 | +107 | +152 |

**Leitura honesta:** para **PQC−Classic**, Δ(soma das chamadas) fica sempre dentro de ±43ms (ruído) em TODAS as 8 rotas — a diferença real (até +597ms) mora **quase inteiramente no resíduo**. Para **Hybrid−PQC**, Δ(soma das chamadas) já é não-trivial (19-113ms, faz sentido: Hybrid literalmente faz mais trabalho criptográfico POR CHAMADA real), mas o resíduo ainda domina (95-376ms).

**O resíduo NÃO é aproximadamente constante entre rotas** — pelo contrário: só nas 3 rotas L0 (RTT cliente-servidor~0 nas 3), Δresíduo(PQC−Classic) varia de -42ms a +456ms, mais de 10x de variação **mesmo com RTT real idêntico (~0) nas 3**. Isso é **inconsistente** com "overhead de orquestração fixo, independente de tudo" — o tamanho do resíduo (e de sua diferença entre perfis) depende claramente da **instalação** (o mesmo efeito já identificado e deixado inconclusivo em H4), não só do perfil.

### Item 5 — resíduo das rotas não-L0 vs. L0 da mesma instalação, contra o RTT real: achado descritivo real, mas CONFUNDIDO (mistura `b` e `c`, não isola nenhum dos dois — ver correção abaixo e a regressão do Item 5b)

Para cada uma das 5 rotas não-L0, perfil Classic (mesma convenção de H4): `(resíduo da rota − resíduo do L0 da MESMA instalação)` dividido pelo **RTT real cliente-servidor** daquela rota (não o controle-cliente — este teste usa só dados reais, sem nenhuma aproximação):

| Rota | Instalação | Δresíduo vs. L0 (s) | RTT real cliente-servidor (ms) | Δresíduo/RTT (ms de resíduo extra por ms de RTT) |
|---|---|---:|---:|---:|
| L123 | sa-east-1 | 3,828 | 122,642 | **31,2** |
| L219 | sa-east-1 | 6,955 | 220,151 | **31,6** |
| L325 | sa-east-1 | 10,571 | 323,406 | **32,7** |
| L14 | us-east-1 | 0,393 | 14,759 | **26,6** |
| L30 | ap-northeast-1 | 1,062 | 33,423 | **31,8** |

**Resultado descritivo:** a razão Δresíduo/RTT fica entre 26,6 e 32,7 nas 5 rotas — mesmo que as rotas tenham RTTs reais completamente diferentes (14,8ms a 323,4ms).

**Correção metodológica (apontada pelo usuário, dupla, mais precisa que a versão anterior deste documento):** a afirmação anterior de que "a rota e seu próprio L0 compartilham exatamente a mesma distância controle↔cliente" estava **imprecisa para os 5 pares, não só para alguns**:

1. **`L123`/`L219`/`L325` vs. `L0-sa-east-1`:** o cliente de `L0-sa-east-1` está co-localizado em `sa-east-1` (RTT controle↔cliente ≈0,129ms, já que o controle também está em `sa-east-1`) — mas os clientes de `L123`/`L219`/`L325` estão em `ca-central-1`/`eu-north-1`/`ap-southeast-1` (RTT controle↔cliente real ≈122,6/220,2/323,4ms, pelo mesmo proxy do item 5b — servidor da rota é `sa-east-1`, co-localizado com o controle). **A distância controle↔cliente NÃO é a mesma entre a rota e seu L0 nestes 3 casos** — e, pela forma como o RTT(controle,cliente) é aproximado nesta investigação (idêntico ao RTT(cliente,servidor) real para essas 3 rotas, já que o servidor é `sa-east-1`), a razão ~31-33 reflete **a soma `b+c`** do modelo do item 5b (`b+c`≈13,17+19,40=**32,57**, batendo com as 3 razões observadas), **não `c` isoladamente** como a versão anterior deste texto afirmava.
2. **`L14` vs. `L0-us-east-1`:** o cliente de `L14` está em `ca-central-1`; o cliente de `L0-us-east-1` (usado como referência "L0 da mesma instalação") está co-localizado em `us-east-1` — **regiões DIFERENTES**. A distância controle↔cliente não é igual entre os dois (≈122,6ms para `L14`, derivado da mesma região de `L123`, vs. ≈112,5ms de aproximação externa para `L0-us-east-1`) — a subtração **NÃO cancela o efeito de SSH de forma exata** para este par; pelo coeficiente `b`≈13,17 do item 5b, a diferença de ≈10,1ms entre essas duas aproximações de RTT controle-cliente explicaria ≈133ms do Δresíduo total de 393ms observado para `L14` — uma fração não-trivial (~1/3).
3. **`L30` vs. `L0-ap-northeast-1`:** mesma situação — cliente de `L30` em `ap-northeast-2`, cliente de `L0-ap-northeast-1` co-localizado em `ap-northeast-1`, regiões diferentes (aproximações externas de ≈290ms e ≈285ms respectivamente, próximas mas não iguais).

**Conclusão honesta:** a subtração `residuo_rota − residuo_L0_mesma_instalação` **não isola de forma limpa nem `b` (SSH) nem `c` (RTT cliente-servidor) em NENHUM dos 5 pares** — para `L123`/`L219`/`L325` mistura os dois (porque, no modo como o RTT controle-cliente é aproximado aqui, eles se movem juntos); para `L14`/`L30` há um vazamento residual do efeito de SSH porque as regiões de cliente não coincidem exatamente com a do L0 de referência. A razão ~27-32 continua sendo um achado descritivo real (existe ALGUM componente que cresce com a distância da rota), mas **a regressão do Item 5b (que ajusta `b` e `c` simultaneamente usando as 8 rotas, não pares isolados) é a única forma rigorosa, nesta investigação, de separar os dois efeitos** — e ela já mostra (abaixo) que ambos são reais.

### Item 5b — regressão para separar o efeito de SSH (RTT controle↔cliente) do efeito de RTT cliente-servidor: SUSTENTADO que AMBOS os efeitos são reais e estatisticamente distintos de zero

Modelo ajustado (`scripts/etapa1_regressao_ssh_vs_rtt.py`, perfil Classic, 8 rotas, mínimos quadrados + IC 95% bootstrap, 10.000 reamostragens, semente `20270102` — mesma já registrada):

**resíduo (ms) = a + b·RTT(controle,cliente) (ms) + c·RTT(cliente,servidor) (ms)**

**RTT(controle,cliente) usado, rota a rota, com a MESMA transparência do item 3** (controle confirmado em `sa-east-1`, item 2):

| Rota | RTT controle↔cliente (ms) | Fonte |
|---|---:|---|
| L0-sa-east-1 | 0,129 | REAL |
| L123 | 122,642 | REAL (servidor da rota é sa-east-1, co-localizado com o controle) |
| L219 | 220,151 | REAL (idem) |
| L325 | 323,406 | REAL (idem) |
| L14 | 122,642 | DERIVADO (cliente de L14 está na MESMA região de L123, `ca-central-1`) |
| L0-us-east-1 | 112,5 | APROXIMAÇÃO EXTERNA (ponto médio da faixa 105-120ms já declarada no item 3, não medida) |
| L0-ap-northeast-1 | 285,0 | APROXIMAÇÃO EXTERNA (ponto médio de 270-300ms, não medida) |
| L30 | 290,0 | APROXIMAÇÃO EXTERNA (ponto médio de 275-305ms, não medida) |

**Nota sobre colinearidade (transparência total):** para `L0-sa-east-1`/`L123`/`L219`/`L325`, RTT(controle,cliente) e RTT(cliente,servidor) são **exatamente iguais** (o servidor dessas 4 rotas é `sa-east-1`, co-localizado com o controle) — colinearidade perfeita nesses 4 pontos. Só os outros 4 (`L0-us-east-1`/`L14`/`L0-ap-northeast-1`/`L30`, onde as duas distâncias divergem) separam de fato `b` de `c`. Com só 8 pontos e metade deles colineares entre os dois preditores, este ajuste é necessariamente frágil — reportado com o IC completo, nunca só o ponto central.

**Resultado:**

| Coeficiente | Estimativa pontual | IC 95% bootstrap |
|---|---:|---:|
| `a` (intercepto, ms) | 1.807,3 | [1.553,7; 1.924,9] |
| `b` (ms de resíduo por ms de RTT controle↔cliente) | 13,17 | [12,20; 15,29] |
| `c` (ms de resíduo por ms de RTT cliente-servidor) | 19,40 | [17,94; 20,43] |

**Pergunta do usuário — `b` é compatível com ~13 viagens de rede (referência de uma sessão SSH nova: handshake TCP + versão SSH + KEX + autenticação por chave pública)?** **SIM, compatível** — o IC 95% de `b` é [12,20; 15,29], que **inclui exatamente o valor de referência 13** (não forçado: o IC foi calculado primeiro, 13 só foi comparado depois). Isso é consistente com (mas não uma contagem direta de pacotes de) uma sessão SSH fresca gastando algo da ordem de 12-15 idas-e-voltas de rede entre controle e cliente — plausível para OpenSSH sem multiplexação (handshake TCP, troca de versão, KEX, userauth publickey, abertura/fechamento de canal, encerramento da conexão), mas este número vem do AJUSTE estatístico, não de uma captura de pacotes SSH reais — não é uma contagem exata confirmada por captura, só compatibilidade estatística.

**Intercepto `a` ≈ 1,81s (IC inclui ~1,9s sugerido pelo usuário):** no modelo, representa o custo que **não escala com NENHUM dos dois RTTs** — ou seja, custo fixo de orquestração que ocorreria mesmo com controle, cliente e servidor todos co-localizados (RTT≈0 nos dois termos). Pelo que o item 1 já confirmou no código, isso inclui pelo menos: cold-start do interpretador Python no cliente + importação de módulos (`opin_flow` carrega `requests`/`urllib3`/`cryptography`/`pyjwt`) + a construção de chave RSA (`latency_automation.py:257`, antes de `t_start`; **corrigido no Item 6-7: ~27ms com a chave RSA-2048 real da campanha, não ~252ms como a primeira versão desta seção assumiu — ver correção**) + qualquer tempo de CPU local (não round-trip) gasto nos handshakes TLS/mTLS reais. O aquecimento RSA é uma fração pequena do total — o resto (~1,78s) do intercepto permanece **não decomposto com os dados disponíveis** (cold-start do Python e import de módulos nunca foram cronometrados separadamente nesta campanha).

**Conclusão honesta do item 5b:** tanto `b` (RTT controle-cliente/SSH) quanto `c` (RTT cliente-servidor) têm IC 95% que **excluem zero** — ambos os efeitos são reais e estatisticamente distintos de zero neste ajuste. O overhead de SSH para o padrão de L0 **NÃO foi refutado pelo item 5** (correção acima) e esta regressão (item 5b) dá, pela primeira vez, uma estimativa direta e com IC de sua magnitude (~13 viagens de rede), compatível com a referência sugerida — mas com um ajuste estatisticamente frágil (n=8, metade colineares), que não substitui uma medição direta (ex. captura de pacotes SSH reais, não feita nesta investigação).

### Item 5c — análise de sensibilidade: o ajuste é robusto à escolha do ponto dentro das 3 faixas aproximadas?

As 3 rotas sem medição real de RTT(controle,cliente) (`L0-us-east-1`, `L0-ap-northeast-1`, `L30`) usaram o PONTO MÉDIO da faixa declarada no item 5b. Para checar se a conclusão depende dessa escolha, `scripts/etapa1_regressao_sensibilidade.py` refaz o ajuste completo (com o mesmo bootstrap, semente `20270102`) usando o **limite inferior** e o **limite superior** de cada faixa, em vez do ponto médio:

| Cenário | `a` (ms) | `b` | `c` |
|---|---|---|---|
| Ponto médio (já reportado) | 1.807,3 [1.553,7;1.924,9] | 13,17 [12,20;15,29] | 19,40 [17,94;20,43] |
| Limite inferior das 3 faixas | 1.792,9 [1.521,3;1.916,1] | 13,96 [12,90;15,94] | 18,67 [17,13;19,74] |
| Limite superior das 3 faixas | 1.822,0 [1.556,8;1.952,7] | 12,45 [11,55;14,65] | 20,06 [18,56;25,46] |

**Conclusão:** nos 3 cenários, `a` fica sempre perto de ~1,8s, `b` sempre entre ~11,5 e ~15,9 (sempre compatível com a referência de ~13 viagens de rede, nunca inclui zero), `c` sempre entre ~17,1 e ~25,5 (nunca inclui zero). **A conclusão central do item 5b (ambos os efeitos são reais) é robusta à incerteza das 3 aproximações externas** — a escolha do ponto dentro da faixa não muda a conclusão qualitativa, só desloca os pontos centrais em poucas unidades.

### Item 6 — custos DEPENDENTES DE PERFIL dentro de t0..t1, fora de t_start..t_end: existem, e são reais (não apenas o intercepto comum `a`)

O item 5b trata `a` como um custo fixo **comum a todos os perfis**. Isso é uma simplificação — alguns dos custos que caem fora de `t_start..t_end` (e portanto, dentro de `a`/resíduo) **dependem do perfil**. Lendo `thesis/scripts/opin_flow.py`, `thesis/scripts/latency_automation.py` e `thesis/results/v9/campaign/scripts/orchestrator.py` linha a linha, para os 4 perfis:

| Operação (dentro de t0..t1, antes de `t_start`) | Classic | PQC | Hybrid (`hibrido-and`) | Control (`hibrido-v8`) | Onde no código |
|---|---|---|---|---|---|
| Conexão SSH completa (controle↔cliente) | comum | comum | comum | comum | `orchestrator.py:1449-1472`, `cli.py:133-153` |
| Cold-start do processo Python + imports | comum | comum | comum | comum | `campaign_client_runner.py:23-29` |
| `of.clear_*_timings()` (negligível) | comum | comum | comum | comum | `latency_automation.py:260-263` |
| `of.load_client_signing_key(crypto_profile)` — reconstrução de chave RSA via `pyjwt.algorithms.RSAAlgorithm.from_jwk()` | **SIM, ~27ms** (RSA-2048 real — ver correção abaixo) | **NÃO, ~0ms** | **SIM, ~27ms** (metade classical do par) | **SIM, ~27ms** (cai no mesmo ramo `else` de Classic) | `opin_flow.py:619-661` (ramo `if`/`elif`/`else`, linhas 623-655); chamado em `latency_automation.py:257` |

**Correção importante (achado da quinta auditoria independente, não capturado na primeira versão desta seção):** `thesis/results/v9/DECISIONS.md`, **Decisão 113** (2026-11-10) — as chaves RSA próprias do `client_one` (as mesmas lidas por `load_client_signing_key()`) foram **rotacionadas de 4096 para 2048 bits, em todos os 4 perfis, ANTES do congelamento**. A campanha oficial real rodou DEPOIS disso (janela `2026-11-15T17:37Z`–`2026-11-16T00:06Z`, Decisões 188/189). **A chave real que `load_client_signing_key()` reconstrói na campanha oficial é RSA-2048, não RSA-4096** — confirmado lendo `DECISIONS.md` (nunca lendo o arquivo de chave privada real em si, que esta investigação não toca). O comentário de código que cita "~252ms" (abaixo) nunca foi atualizado após essa rotação — plausivelmente foi medido quando a chave ainda era RSA-4096. O microbenchmark do Item 7 foi refeito com RSA-2048 (o tamanho real) e dá ~27ms — **a primeira versão desta seção, que usou RSA-4096 (~218-252ms) como base do Item 8, estava descrevendo um cenário que não corresponde à campanha real; a conclusão do Item 8 foi inteiramente recalculada abaixo com o valor correto.**

**Confirmado no código, ramo a ramo** (`opin_flow.py:619-661`, função `load_client_signing_key`): `crypto_profile=="pqc"` (linha 623-627) devolve o JWK bruto sem nenhuma chamada a `RSAAlgorithm.from_jwk()` — custo ~0. `crypto_profile in ("hybrid","hibrido-and")` (linha 628-649) chama `RSAAlgorithm.from_jwk()` para a metade clássica do par (`classic_key`, linha 646) — paga o custo. Qualquer outro valor de `crypto_profile` (inclusive `"hibrido-v8"`, que não tem ramo próprio) cai no `else` (linha 650-655) e também chama `RSAAlgorithm.from_jwk()` (linha 654) — paga o custo. **A memoização (`_SIGNING_KEY_CACHE`) não ajuda aqui**: é um cache em memória do processo, e cada execução real da campanha roda um `python3 campaign_client_runner.py` NOVO via SSH (confirmado no Item 1) — o cache está sempre vazio no início de cada execução, então o custo é pago **a cada execução**, não amortizado.

**Citação exata da origem do número ~252ms (pedido explícito, nunca repetir sem checar):** o comentário de `load_client_signing_key()` (`opin_flow.py`, linhas ~578-594) atribui a "Decision 99" e diz: *"the measured cause of ~500ms of classic/hybrid's own T_fluxo that PQC never paid, confirmed call-for-call against the diagnostic's own real setup_timings (median classic/hybrid ~252ms x2, pqc ~0ms x2)"*. **Busca feita, não assumida:** nenhum outro arquivo deste repositório (`DECISIONS.md` de v9 ou de versões anteriores) contém o "diagnóstico" original com data/hardware especificados — essa é a ÚNICA referência encontrada a este número, dentro do próprio comentário de código, e **ele não especifica o tamanho de chave usado na medição nem foi atualizado após a Decisão 113** (rotação RSA-4096→2048). É plausível que tenha sido medido quando a chave ainda era RSA-4096 (antes de 2026-11-10) — isso **não pode ser confirmado de forma independente** com a documentação disponível, mas explicaria por que o número documentado (~252ms) é ~8x maior que o medido localmente com RSA-2048 (~27ms, Item 7) — proporção muito próxima da razão real entre os custos de RSA-4096 e RSA-2048 (~8x, também medida localmente).

**O que NÃO é profile-dependente neste ponto específico (confirmado, não assumido):** `start_tls_kem_proxy()`/`start_pqc_signer_service()` (que de fato diferem por perfil — curva TLS, container Node) são chamados por `orchestrator.py`'s `start_block()` (linha 2280) **UMA VEZ POR BLOCO** (10 execuções), **ANTES** do laço de `run_execution()` (linhas 2317-2319) — nunca dentro da janela t0..t1 de uma execução individual. O custo de iniciar esses processos é amortizado sobre as execuções do bloco, não pago a cada execução — confirmado lendo o docstring de `campaign_client_runner.py` ("Does NOT manage the TLS proxy / PQC signer service lifecycle -- that is scoped to the whole profile BLOCK") e o ponto de chamada real em `orchestrator.py`.

**O que acontece DENTRO de `t_start..t_end` (não está no intercepto `a`, mas é profile-dependente e seria lido, hoje, como parte do "resíduo" desta investigação, pela forma como o crítico decompõe T_fluxo):** `verify_jwt()`/`decrypt_and_verify_jwt()` (`opin_flow.py:825-895`) são chamados pelos 4 perfis (verificação roteada pelo mesmo serviço Node, por desenho, "for that comparability") via `requests.post` direto (NÃO via `do_call()`, então não entram na soma das 44 chamadas) — o CUSTO de cada chamada depende do perfil (ML-DSA-65 verify é mais caro que PS256 verify). `sign_jwt()` (`opin_flow.py:1560-1627`): Classic assina só em processo (pyjwt, sem chamada de rede); PQC assina via chamada ao serviço Node (`_run_pqc_signer`); Hybrid faz AMBAS (chamada ao Node para a parte ML-DSA-65 + pyjwt em processo para a parte PS256). **Esses custos são trabalho real do perfil (não são um artefato de medição evitável, ao contrário do item da chave RSA) — mas também não são medidos pelas 44 chamadas, então ficam dentro do "resíduo" desta investigação, misturados com o overhead de SSH/orquestração.**

### Item 7 — microbenchmark local dos custos dependentes de perfil (mesmo hardware já declarado) — CORRIGIDO para RSA-2048

`scripts/etapa1_microbench_custos_por_perfil.py` — chaves **geradas localmente para este microbenchmark** (nunca a chave real da campanha `client_one.jwks`, nunca lida nem copiada), 30 repetições de `jwt.algorithms.RSAAlgorithm.from_jwk()` para cada tamanho, mesmo notebook (Intel Core 7 150U) já usado nos microbenchmarks de H3:

| | RSA-2048 (tamanho REAL da campanha, Decisão 113) | RSA-4096 (premissa incorreta da 1ª versão desta seção) |
|---|---:|---:|
| Mediana local (30 repetições) | **27,1ms** | 216,7ms |
| Média local | 27,2ms | 240,3ms |
| Mínimo / máximo local | 25,8ms / 29,8ms | 195,3ms / 402,0ms |
| Razão 4096/2048 (medida) | — | **8,0x** |

**Leitura corrigida:** o custo real pago pela campanha oficial (chave RSA-2048, confirmada pela Decisão 113) é **~27ms**, não ~218-252ms. O valor "~252ms" documentado no comentário do código (Item 6) é ~8x maior que o medido localmente com o tamanho de chave correto — consistente com a hipótese de que aquele comentário nunca foi atualizado após a rotação de chave, e foi medido (ou herdado de uma medição) de quando a chave ainda era RSA-4096.

**Processo do signer Node — confirmado, não assumido, que NÃO reinicia por execução:** ver Item 6 acima — `start_pqc_signer_service()` roda uma vez por bloco (10 execuções), nunca por execução individual. Isso muda completamente a conta pedida: se reiniciasse a cada execução, seu custo de start (`docker run -d`) entraria inteiro no intercepto por execução; como NÃO reinicia, seu custo de start não participa do viés por execução discutido no Item 8 abaixo — só a RECONSTRUÇÃO DE CHAVE (Item 6-7) participa.

### Item 8 — faixa de viés possível nas diferenças PQC−Classic e Hybrid−PQC já publicadas (Seção 5.1 do relatório oficial) — CORRIGIDO, conclusão muda substancialmente

**Faixa de viés usada (CORRIGIDA — RSA-2048, o tamanho real):** 25,8ms a 29,8ms (mín/máx do microbenchmark local do Item 7) — chamada de "~26-30ms" abaixo. Classic/Hybrid/Control pagam esse custo; PQC não (Item 6). **(A primeira versão desta seção usou 218,5-252ms, baseada na premissa incorreta de RSA-4096 — totalmente substituída aqui, nunca reusada.)**

`scripts/etapa1_sensibilidade_vies_rsa.py` aplica esse ajuste aritmético simples (**nunca um reteste estatístico** — isso exigiria dados brutos corrigidos, fora do escopo) aos 16 valores de "Dif (ms)" já publicados na Seção 5.1 do `Consolidated_Metrics_Report_FINAL.md` (citados diretamente da tabela oficial, não reconstruídos): como Classic/Hybrid pagam o custo e PQC não, `Dif_verdadeiro(PQC−Classic) ≈ Dif_observado + viés` e `Dif_verdadeiro(Hybrid−PQC) ≈ Dif_observado − viés`.

| Rota | PQC vs. Classic — Dif observado (ms) | → faixa corrigida (ms) | Hybrid vs. PQC — Dif observado (ms) | → faixa corrigida (ms) |
|---|---:|---:|---:|---:|
| L0-sa-east-1 | -69,0 | [-43,2; -39,2] | 275,7 | [245,9; 249,9] |
| L123 | 263,4 | [289,2; 293,2] | 205,9 | [176,1; 180,1] |
| L219 | 422,3 | [448,1; 452,1] | 290,9 | [261,1; 265,1] |
| L325 | 577,3 | [603,1; 607,1] | 395,1 | [365,3; 369,3] |
| L0-us-east-1 | 223,4 | [249,2; 253,2] | 167,7 | [137,9; 141,9] |
| L14 | 287,9 | [313,7; 317,7] | 170,1 | [140,3; 144,3] |
| L0-ap-northeast-1 | 462,4 | [488,2; 492,2] | 367,7 | [337,9; 341,9] |
| L30 | 554,8 | [580,6; 584,6] | 259,2 | [229,4; 233,4] |

**Leitura honesta (corrigida — conclusão MUITO mais fraca que a versão anterior desta seção):** com a faixa de viés correta (~26-30ms, RSA-2048), **NENHUMA das 16 comparações troca de sinal** — nem `L0-sa-east-1` (PQC vs. Classic), nem `L123`/`L0-us-east-1`/`L14` (Hybrid vs. PQC), que a versão anterior (incorreta, baseada em RSA-4096) tinha identificado como trocando de sinal. O viés é real e confirmado (Classic/Hybrid/Control pagam ~26-30ms que PQC não paga), mas sua magnitude é pequena comparada a TODAS as diferenças já publicadas na Seção 5.1 (a menor, em valor absoluto, é 167,7ms — ainda ~6x maior que o viés). **A correção deste item é, em si, o achado mais importante desta rodada: a primeira versão da análise usou o tamanho de chave errado (RSA-4096, quando a campanha real já usava RSA-2048 desde a Decisão 113) e por isso superestimou o viés em ~8x — superestimando também seu impacto prático sobre o relatório oficial.**

**O que isso significa pra Seção 4.2/5.4 do relatório oficial:** TODAS as tabelas de comparação entre perfis dessas duas seções (e de 4.1/4.3/4.4/5.1/5.2/5.3) usam T_fluxo (ou a mediana/valores de T_fluxo) — **nenhuma delas usa a soma das 44 chamadas isoladamente** como métrica alternativa livre deste viés específico (essa decomposição só existe nesta investigação exploratória, não no relatório oficial). Com o viés correto (~26-30ms), porém, isso tem pouca consequência prática: **todas as 16 comparações já publicadas são robustas em direção** (nenhuma troca de sinal) e a magnitude é deslocada só por uma fração pequena do efeito observado (de ~5% nas maiores diferenças a ~15% nas menores, como `L0-us-east-1`/`L14` de Hybrid vs. PQC). O viés é real e documentado, mas pequeno — bem diferente da conclusão que a primeira versão (incorreta) desta seção tinha chegado.

### Item 9 — os campos ricos (`t_fluxo_seconds`/`phase_accounting`) vazaram para algum log bruto já copiado localmente? NÃO (busca exaustiva, confirmada)

Busca por `t_fluxo_seconds` e `phase_accounting` (strings literais) em TODA a árvore `thesis/results/v9/campaign_oficial_conta_nova_raw/` e `thesis/results/v9/campaign_oficial_conta_nova_organized/` (incluindo `piloto_combined.log`, todos os `.log` de `criterio1_capturas/`, todos os `runs/*.json`): **zero ocorrências de `phase_accounting` em qualquer arquivo real desta campanha** (confirmado por grep recursivo, não assumido). A string `t_fluxo_seconds` aparece só como **rótulo** `"metric": "t_fluxo_seconds"` dentro de `median_metrics.json`/`MEDIAN_REPORT.md` — mas o valor numérico ali é exatamente o T_fluxo SSH-wrapped (`end_utc − start_utc`), não o `t_fluxo_seconds` fino calculado internamente por `latency_automation.run_once_timed()`; é só uma coincidência de nome, confirmado comparando o valor (ex.: `classico/L0-sa-east-1`: `"median": 2.357881` no `median_metrics.json`, idêntico ao T_fluxo SSH-wrapped já usado em todo este documento). **Os campos ricos nunca foram persistidos em nenhum lugar — nem no JSON estruturado, nem em nenhum log bruto já copiado.** (Nota: uma busca mais ampla no repositório inteiro encontrou "phase_accounting" em arquivos da campanha **v8**, versão anterior/diferente do pipeline — esses arquivos NÃO pertencem a esta campanha v9 e incluem diretórios de `warmup/`, que o pré-registro desta investigação proíbe explicitamente ler; não foram abertos.)

**Confirmação exata de onde o descarte acontece** (já identificado no item 1, reconfirmado): `thesis/results/v9/campaign/scripts/orchestrator.py`, método `run_execution`, linha **1469** (`result = json.loads(proc.stdout.strip().splitlines()[-1])` — aqui o dict completo, COM `t_fluxo_seconds`/`phase_accounting`, já está em memória) até a linha **1504** (`return {"insurance": result.get("calls", []), "person": [], ...}` — aqui o dict de retorno é montado e nenhuma dessas duas chaves é copiada; elas são descartadas silenciosamente quando o `result` local sai de escopo ao fim da função).

**Mudança mínima de código que preservaria esses campos numa futura campanha suplementar (descrita apenas, NÃO aplicada agora):** no dict literal retornado por `run_execution` (linha ~1504-1522 de `orchestrator.py`), adicionar duas chaves adicionais, lendo do mesmo `result` já disponível: `"t_fluxo_fino_seconds": result.get("t_fluxo_seconds"), "phase_accounting": result.get("phase_accounting", {})`. É uma mudança puramente aditiva (nenhuma chave existente é removida ou renomeada) — os consumidores atuais do dict (`organize_v9_results.py`, os scripts de consolidação) continuariam funcionando sem alteração, e ganhariam acesso, numa campanha futura, à decomposição fina real (chamadas HTTP/assinatura/verificação/espera/setup/resíduo interno) sem precisar reconstruir nada por subtração.

### Resumo dos vereditos desta verificação

| Item | Veredito |
|---|---|
| 1. T_fluxo inclui operações além das 44 chamadas HTTP | **SUSTENTADO** (confirmado no código: SSH completo + cold-start Python + aquecimento de chave RSA, ordem de ~200-250ms, Classic/Hybrid/Control — ver Itens 6-7 + dados internos ricos descartados) |
| 2. Controle contata outra região via rede (exceto L0-sa-east-1) | **SUSTENTADO** (controle em sa-east-1, confirmado) |
| 3. Overhead de SSH escala com distância controle-cliente (via excesso/pcap) | **INCONCLUSIVO** (indicador ruidoso, sinal inconsistente entre perfis) |
| 4. Resíduo é aprox. constante entre perfis (overhead fixo) | **REFUTADO** (resíduo varia >10x mesmo com RTT real ~0 nas 3 rotas L0; depende de perfil E instalação) |
| 5. Excesso de resíduo (rotas não-L0 vs. L0) isola o efeito de RTT cliente-servidor | **CONFUNDIDO** — razão 26,6-32,7 real, mas mistura `b`+`c` (não isola nenhum dos dois); regiões de cliente de L14/L30 divergem das de seus L0 de referência (correção) — a separação rigorosa é o Item 5b |
| 5b. Regressão separando RTT controle-cliente (SSH) de RTT cliente-servidor | **SUSTENTADO que AMBOS são reais**: `b`≈13,17 (IC [12,20;15,29], compatível com ~13 viagens de rede de uma sessão SSH fresca) e `c`≈19,40 (IC [17,94;20,43]) — nenhum dos dois IC inclui zero |
| 5c. Regressão robusta à escolha dentro das faixas aproximadas de RTT | **SUSTENTADO** — `a`/`b`/`c` ficam estáveis (b sempre 11,5-15,9; c sempre 17,1-25,5) nos cenários de limite inferior/médio/superior |
| 6. Existem custos dependentes de PERFIL dentro de t0..t1 fora de t_start..t_end | **SUSTENTADO** — reconstrução de chave RSA (~27ms, RSA-2048 real, corrigido) paga por Classic/Hybrid/Control, NÃO por PQC (confirmado ramo a ramo no código); custo do processo Node signer NÃO é por execução (confirmado, roda uma vez por bloco) |
| 7. Microbenchmark local confirma a ordem de grandeza do custo de perfil | **SUSTENTADO, CORRIGIDO** — mediana local RSA-2048 (tamanho real, Decisão 113) = 27,1ms; a 1ª versão usou RSA-4096 por engano (~218,5ms), ~8x maior |
| 8. Esse viés muda conclusões já publicadas na Seção 5.1 do relatório oficial | **REFUTADO (corrigido)** — com o viés real (~26-30ms), NENHUMA das 16 comparações troca de sinal; a 1ª versão desta análise (RSA-4096 incorreto) tinha concluído erroneamente que 4/16 trocariam |
| 9. Campos ricos (`t_fluxo_seconds`/`phase_accounting`) vazaram em algum log bruto | **REFUTADO** (busca exaustiva, zero ocorrências reais; só um rótulo de nome coincidente, confirmado não ser o dado fino) |

### Impacto sobre a interpretação do relatório oficial já publicado

**T_fluxo, em TODO este documento e no `Consolidated_Metrics_Report_FINAL.md` (relatório oficial, já publicado), não é "tempo de fluxo cliente-servidor" no sentido estrito — é "tempo de execução ponta-a-ponta via SSH do controle", que inclui overhead de orquestração real (confirmado no item 1) além das 44 chamadas HTTP.** A regressão do item 5b estima que, do resíduo total, uma parte escala com o RTT controle-cliente (overhead de SSH, `b`≈13 viagens de rede) e outra parte com o RTT cliente-servidor (`c`≈19 viagens de rede), além de um custo fixo (`a`≈1,8s) que não escala com nenhum dos dois.

**Correção (itens 6-8 — a frase "comparações entre perfis na mesma rota não são afetadas" NÃO é totalmente sustentável, mas o impacto prático é pequeno):** uma parte do custo fixo `a` **depende do perfil** — a reconstrução de chave RSA (`pyjwt.algorithms.RSAAlgorithm.from_jwk()`) é paga por Classic/Hybrid/Control mas **não** por PQC, a cada execução (confirmado ramo a ramo no código, Item 6). **Correção de tamanho de chave (achado da quinta auditoria independente):** a chave real da campanha é RSA-2048 desde a Decisão 113 (2026-11-10, antes da campanha rodar), não RSA-4096 como a primeira versão desta análise assumiu — o custo real, medido localmente (Item 7), é **~27ms**, não ~218-252ms. Com o viés correto, o Item 8 mostra que **nenhuma das 16 comparações já publicadas na Seção 5.1 troca de sinal** — o viés é real, mas pequeno em relação a todas as diferenças observadas (a menor é ~6x maior que o viés). A sobrecarga de SSH e o cold-start do processo são comuns a todos os perfis (não introduzem viés entre perfis); o custo de preparação de chave NÃO é comum, mas sua magnitude real é pequena o suficiente para não mudar nenhuma conclusão de direção já publicada.

**NÃO EDITO o relatório oficial sem autorização.** (Nesta rodada, autorização explícita foi dada para aplicar uma ressalva curta na Seção 5.4 — ver abaixo, "Alteração aplicada ao relatório oficial".) Texto de ressalva PROPOSTO/aplicado (atualizado após as correções dos itens 5-8 acima):

> **Ressalva metodológica (adicionada após investigação exploratória "Degrau 1" — ver `thesis/results/v9/analise_origem/RELATORIO_ORIGEM.md`):** o campo "T_fluxo" usado neste relatório mede o tempo de execução ponta-a-ponta observado pelo processo orquestrador (via SSH, do host de controle até o host cliente), não apenas o tempo das chamadas HTTP entre cliente e servidor. Essa janela inclui, além das chamadas HTTP medidas individualmente, o estabelecimento/encerramento da conexão SSH (que cruza regiões AWS diferentes para 7 das 8 rotas) e a inicialização do processo Python no cliente — ambos comuns a todos os perfis, não introduzem viés entre perfis. **Também inclui um custo de preparação de chave de assinatura RSA (~27ms, medido localmente para o tamanho de chave RSA-2048 real da campanha, Decisão 113) que depende do perfil: pago por Classic, Hybrid e Control, não pago por PQC, a cada execução** — este custo específico está presente nas diferenças observadas entre perfis (Seções 4.2/5.1), mas sua magnitude é pequena em relação a todas as diferenças já reportadas (a menor delas, 167,7ms, é ~6x maior que o viés) — uma estimativa de sensibilidade (Degrau 1, Item 8) confirma que nenhuma das 16 comparações publicadas troca de sinal ao remover este viés específico.

## O que ainda fica sem explicação

1. **A causa exata do resíduo que varia entre instalações** (item central de H4) — os dados disponíveis localizam ONDE a diferença mora (no resíduo, não nas chamadas) e a verificação adicional de hardware/ambiente (acima) descarta contenção de CPU (steal≈0) e qualquer divergência documentada de SO/kernel/rede (byte-a-byte idênticas), mas não há dado (`/proc/cpuinfo`/`lscpu`/`mpstat` nunca capturados) pra ir além disso — QUAL mecanismo exato dentro do resíduo (handshake TLS em si, setup/teardown do processo de medição, diferença de microarquitetura de CPU não documentada, agendamento do hypervisor, etc.) é responsável permanece sem resposta.
2. **O custo real da pilha de produção (Node.js para ML-DSA-65, Python para RSA/PS256) nunca foi medido** — o microbenchmark desta investigação mediu só a reimplementação em Go dessas primitivas (ver correção de H3 acima); não se sabe se o custo real do runtime de produção se aproxima mais ou menos da diferença observada do que a versão Go testada.
3. **O achado secundário de H1** (tendência de assentamento dentro de 8/32 blocos) não tem uma causa identificada — é descrito, não explicado.
4. Nenhuma das 3 hipóteses de rede/CPU (H1 posição, H2 RTT/initcwnd, H3 CPU) explica a diferença real entre perfis nas rotas L0 — o que **esta investigação não encontrou** é tão relevante quanto H4: a origem dominante da diferença entre perfis permanece, ela mesma, sem explicação mecanística completa a partir dos dados hoje disponíveis.

## O que um experimento controlado ("Degrau 2") resolveria

Descrito aqui apenas como lacuna identificada — **nada disto foi executado nesta investigação**:

- **Instrumentação de fase**: adicionar ao `orchestrator.py`/`opin_flow.py` (autorização explícita separada seria necessária, já que isso edita código de medição) um timestamp real de início/fim do handshake TLS por conexão (não só o total da execução), permitindo decompor o resíduo em handshake vs. setup vs. gaps — resolveria a lacuna do item 1 acima diretamente.
- **Repetição controlada de instalação**: rodar o MESMO perfil (ex.: Classic) na MESMA rota `L0`, em múltiplas instâncias `m7i-flex.large` diferentes na MESMA região/AZ, em janelas de tempo diferentes (manhã/noite, dias diferentes), para separar "efeito de instalação específica" de "efeito de momento/carga transiente da AWS" — isso teria que ser uma campanha nova, pequena e própria para essa pergunta, nunca misturada com a campanha oficial já publicada.
- **Captura de handshake real por execução cronometrada** (não só uma captura dedicada à parte): se o orquestrador capturasse o handshake de TODAS as 320 execuções (ou uma amostra maior, cronometrada junto com o T_fluxo real), a comparação feita aqui com a captura dedicada teria poder estatístico real, em vez da única amostra não-cronometrada usada nesta investigação.

## Reprodutibilidade

Todo número deste documento vem de `scripts/etapa0_inventory.py`, `scripts/etapa1_h1_order.py`, `scripts/etapa1_decomp_h2_h4.py`, `scripts/etapa1_h3_cpu.py`, `scripts/etapa1_verificacoes_adicionais.py` (verificações suplementares de H2/H4 pedidas após a auditoria independente), `scripts/etapa1_verificacao_artefato_medicao.py` (verificação crítica sobre o que T_fluxo mede, usando `scapy` sobre as capturas dedicadas reais em `criterio1_capturas/capturas_brutas/`), `scripts/etapa1_regressao_ssh_vs_rtt.py` (regressão residuo = a + b·RTT_controle_cliente + c·RTT_cliente_servidor, item 5b, mesma semente de bootstrap `20270102`), `scripts/etapa1_regressao_sensibilidade.py` (item 5c, mesma regressão nos limites inferior/superior das 3 faixas aproximadas), `scripts/etapa1_microbench_custos_por_perfil.py` (item 7, chaves RSA-2048/4096 geradas localmente, nunca a chave real da campanha — nem o arquivo `client_one.jwks`, que este script nunca lê), `scripts/etapa1_sensibilidade_vies_rsa.py` (item 8, ajuste aritmético sobre os 16 valores de Dif já publicados na Seção 5.1 do relatório oficial) e dos microbenchmarks Go em `thesis/results/v9/integration/bench/` (já existente no repositório) e `bench_chain/` (novo, criado nesta investigação) — saídas brutas em `data/`. A leitura do código que confirma a composição da janela t0/t1 (item 1 da verificação crítica) foi feita direto em `thesis/results/v9/campaign/scripts/orchestrator.py`, `thesis/results/v9/campaign/scripts/cli.py`, `thesis/scripts/campaign_client_runner.py` e `thesis/scripts/latency_automation.py` — nenhum desses arquivos foi modificado. Sementes fixas: permutação `20270101`, bootstrap `20270102`, ambas registradas no `PLANO.md` antes de qualquer análise rodar (a mesma semente de bootstrap foi reusada na verificação suplementar de H2, por consistência). A composição real da pilha de produção (Go para KEM via `tls_kem_proxy`, Node.js/`node:crypto` para ML-DSA-65 via `pqc-signer`, Python/`pyjwt`+`cryptography` para RSA/PS256) foi confirmada lendo `thesis/scripts/opin_flow.py`, `thesis/scripts/tls_kem_proxy/main.go` e `thesis/scripts/pqc-signer/signer_core.mjs` diretamente — nenhum desses arquivos foi modificado. Nenhum dado de aquecimento foi lido. Nenhum dado bruto/organizado da campanha oficial foi alterado. O tamanho real da chave RSA do `client_one` (RSA-2048) foi confirmado lendo `thesis/results/v9/DECISIONS.md` (Decisão 113) — nunca lendo o arquivo de chave privada real (`mock-service-os/certs/client_one.jwks`), que esta investigação não toca. **`Consolidated_Metrics_Report_FINAL.md` foi editado nesta rodada (autorização explícita do usuário) para adicionar a ressalva metodológica da Seção 5.4** — via o script gerador (`generate_final_report_oficial_conta_nova.py`), nunca o `.md` direto; nenhum outro número do relatório oficial foi alterado (confirmado pelo diff). Commit local apenas, sem push (autorização dada só para commitar).

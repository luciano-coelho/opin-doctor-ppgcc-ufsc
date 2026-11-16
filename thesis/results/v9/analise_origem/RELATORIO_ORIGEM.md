# Degrau 1 — investigação exploratória da origem das diferenças de latência

Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC. Investigação separada do relatório oficial (`Consolidated_Metrics_Report_FINAL.md`, intocado), sem AWS, a partir SOMENTE de dados já salvos localmente. Pré-registro completo em `PLANO.md` (commitado antes de qualquer análise rodar). Scripts e dados brutos das análises em `scripts/` e `data/`.

## Resumo dos vereditos

| Hipótese | Veredito |
|---|---|
| H1 (ordem do bloco / deriva temporal) | **REFUTADA** (claim principal); achado secundário real não previsto (ver abaixo) |
| H2 (viagens de rede extras / initcwnd) | **REFUTADA** |
| H3 (custo de CPU das primitivas) | **REFUTADA** |
| H4 (heterogeneidade entre instalações) | **SUSTENTADA** (existência); **INCONCLUSIVA quanto à causa exata** |

## H1 — ordem do bloco / deriva temporal: REFUTADA

**Previsão:** posição do bloco (1º-4º) correlaciona com T_fluxo mediano, na mesma direção na maioria das 8 rotas.

**Resultado real** (`scripts/etapa1_h1_order.py`, `data/etapa1_h1_order.json`): correlação de Spearman combinada (32 pontos, posição × mediana) = **-0,009** (essencialmente zero); teste de permutação (8 rotas, posições embaralhadas dentro de cada rota, 10.000 permutações, semente `20270101`): **p = 0,7682**. Por rota, os 8 coeficientes de Spearman variam em ambas as direções (de -0,8 a +0,6), nenhum individualmente significativo (n=4 por rota). **A previsão principal não se sustenta: a posição do bloco na ordem da rota não explica o T_fluxo.**

**Achado secundário real, não previsto pela hipótese como formulada:** a tendência **dentro** de cada bloco (as 10 execuções de um perfil/rota, em ordem temporal real confirmada pelo campo `run`) é significativa (τ de Kendall, p<0,05) em **8 das 32 células** — mais do que o ~5% esperado por puro acaso (~1,6/32). Das 8 células significativas, **7 têm tau negativo** (tendência decrescente — execuções mais tardias dentro do bloco ficam mais rápidas, um padrão de "assentamento"): `classico/L219` (τ=-0,556), `classico/L0-us-east-1` (τ=-0,600), `classico/L30` (τ=-0,556), `pqc/L14` (τ=-0,733), `pqc/L0-ap-northeast-1` (τ=-0,644), `hibrido-v8/L0-us-east-1` (τ=-0,733), `hibrido-and/L0-us-east-1` (τ=-0,511); 1 positiva: `pqc/L325` (τ=+0,600). Isso é um fenômeno relacionado mas **distinto** do que H1 propunha (que era sobre a posição do bloco entre perfis, não sobre a ordem interna das 10 execuções de um único bloco) — registrado honestamente aqui, sem forçá-lo a sustentar a hipótese original.

## H2 — viagens de rede extras / initcwnd: REFUTADA

**Previsão:** inclinação de Dif(ms) vs. RTT aproximadamente igual ao número de round-trips extras que o volume de bytes extra exigiria, dado o `cwnd`/MSS reais.

**Parâmetros reais** (critério 2, nunca assumidos): `cwnd` inicial = **10** segmentos, MSS = **1.448 bytes** (primeira janela = 14.480 bytes, confirmado exatamente no dado real). Bytes totais reais por execução: Classic = 121.641B, PQC = 280.900B, Hybrid = 337.149B.

**Resultado real** (`scripts/etapa1_decomp_h2_h4.py`): inclinação PQC−Classic = **0,868** ms/ms de RTT, IC 95% bootstrap (10.000 reamostragens, semente `20270102`) = **[-0,32; 2,14]** — inclui 0. Inclinação Hybrid−PQC = **0,358**, IC = **[-0,79; 0,66]** — também inclui 0. K teórico (round-trips extras pela fórmula de slow-start com os parâmetros reais acima): **3,58** (PQC vs. Classic) e **2,29** (Hybrid vs. PQC) — **fora dos dois ICs observados, em ambos os casos**. **A relação prevista entre RTT e a diferença de T_fluxo não se sustenta** — a diferença entre perfis não cresce com o RTT da forma que round-trips extras por initcwnd preveem.

## H3 — custo de CPU das primitivas: REFUTADA

**Previsão:** nas rotas `L0-*` (RTT~0), a diferença de T_fluxo deve ser da mesma ordem de grandeza (razão entre 0,5x e 2x, declarado a priori) que a diferença de custo de CPU prevista pelo microbenchmark local.

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

**Nenhuma das 6 comparações cai na faixa [0,5x; 2x] declarada a priori** — em 2 dos 6 casos (ambos no par PQC vs. Classic: L0-us-east-1 e L0-ap-northeast-1) a previsão tem até o SINAL errado em relação ao observado. **O custo de CPU das primitivas, pelo microbenchmark local, não explica a diferença observada nas rotas L0** — nem em magnitude, nem (nesses dois casos) em direção.

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

## O que ainda fica sem explicação

1. **A causa exata do resíduo que varia entre instalações** (item central de H4) — os dados disponíveis localizam ONDE a diferença mora (no resíduo, não nas chamadas), mas não QUAL mecanismo dentro do resíduo (handshake TLS em si, setup/teardown do processo de medição, agendamento de CPU da instância, etc.) é responsável.
2. **O achado secundário de H1** (tendência de assentamento dentro de 8/32 blocos) não tem uma causa identificada — é descrito, não explicado.
3. Nenhuma das 3 hipóteses de rede/CPU (H1 posição, H2 RTT/initcwnd, H3 CPU) explica a diferença real entre perfis nas rotas L0 — o que **esta investigação não encontrou** é tão relevante quanto H4: a origem dominante da diferença entre perfis permanece, ela mesma, sem explicação mecanística completa a partir dos dados hoje disponíveis.

## O que um experimento controlado ("Degrau 2") resolveria

Descrito aqui apenas como lacuna identificada — **nada disto foi executado nesta investigação**:

- **Instrumentação de fase**: adicionar ao `orchestrator.py`/`opin_flow.py` (autorização explícita separada seria necessária, já que isso edita código de medição) um timestamp real de início/fim do handshake TLS por conexão (não só o total da execução), permitindo decompor o resíduo em handshake vs. setup vs. gaps — resolveria a lacuna do item 1 acima diretamente.
- **Repetição controlada de instalação**: rodar o MESMO perfil (ex.: Classic) na MESMA rota `L0`, em múltiplas instâncias `m7i-flex.large` diferentes na MESMA região/AZ, em janelas de tempo diferentes (manhã/noite, dias diferentes), para separar "efeito de instalação específica" de "efeito de momento/carga transiente da AWS" — isso teria que ser uma campanha nova, pequena e própria para essa pergunta, nunca misturada com a campanha oficial já publicada.
- **Captura de handshake real por execução cronometrada** (não só uma captura dedicada à parte): se o orquestrador capturasse o handshake de TODAS as 320 execuções (ou uma amostra maior, cronometrada junto com o T_fluxo real), a comparação feita aqui com a captura dedicada teria poder estatístico real, em vez da única amostra não-cronometrada usada nesta investigação.

## Reprodutibilidade

Todo número deste documento vem de `scripts/etapa0_inventory.py`, `scripts/etapa1_h1_order.py`, `scripts/etapa1_decomp_h2_h4.py`, `scripts/etapa1_h3_cpu.py` e dos microbenchmarks Go em `thesis/results/v9/integration/bench/` (já existente no repositório) e `bench_chain/` (novo, criado nesta investigação) — saídas brutas em `data/`. Sementes fixas: permutação `20270101`, bootstrap `20270102`, ambas registradas no `PLANO.md` antes de qualquer análise rodar. Nenhum dado de aquecimento foi lido. Nenhum dado bruto/organizado da campanha oficial nem o `Consolidated_Metrics_Report_FINAL.md` foram alterados.

# Degrau 2 — pré-registro da campanha suplementar de latência com cronômetro fino

Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC. Fase SUPLEMENTAR, autorizada separadamente do relatório oficial já publicado (`Consolidated_Metrics_Report_FINAL.md`, **intocado nesta fase**) e da investigação exploratória "Degrau 1" (`thesis/results/v9/analise_origem/RELATORIO_ORIGEM.md`, também intocada). Dados em diretório separado — remoto: `~/campaign-data/v9/degrau2`; local: `thesis/results/v9/degrau2/`. **Este documento é committed ANTES de qualquer análise rodar ou qualquer dado novo ser coletado** — nenhum número abaixo vem de dados do Degrau 2 (todos os valores de `a`/`b`/`c` citados vêm do Degrau 1, já publicado, nunca recalculados aqui antes da coleta).

**Fora de escopo, explícito:** o perfil Control (`hibrido-v8`) NÃO entra nesta campanha suplementar. Nenhuma ação na AWS nesta Etapa 0 (tudo abaixo é local). A Etapa 1 (ações reais na AWS) só começa com autorização explícita e presença confirmada do usuário, **sub-etapa por sub-etapa** — a presença confirmada hoje não é uma autorização geral para todas as sub-etapas futuras.

## Motivação

O Degrau 1 confirmou, lendo o código (`latency_automation.run_once_timed()`), que a biblioteca já calcula internamente um T_fluxo FINO (`t_fluxo_seconds`) e uma decomposição por fase (`phase_accounting`: chamadas HTTP, assinatura, verificação, espera explícita, setup, resíduo interno) — mas esses campos são descartados por `orchestrator.py` antes de serem persistidos. Toda a investigação do Degrau 1 (H1-H4, itens 1-10) trabalhou só com o T_fluxo do ORQUESTRADOR ("parede": `end_utc - start_utc`, que inclui a chamada SSH completa + cold-start do Python + aquecimento de chave). O Degrau 2 persiste os dois campos (mudança aditiva, Etapa 0, item 2) e roda uma campanha nova, pequena, pra separar os dois de verdade — com RTT(controle,cliente) MEDIDO de verdade (não aproximado externamente, como no Degrau 1) via `probe_overhead.py`.

## Sementes fixas (registradas ANTES de qualquer coleta)

- **Rodada 1:** semente `20261117`.
- **Rodada 2:** semente `20261118`.
- Usadas para: sorteio da ordem de perfis por rota e por rodada (gravado no manifesto, mesma convenção do Degrau 1/campanha oficial), e qualquer bootstrap estatístico feito na Etapa 2 (Hodges-Lehmann, IC 95%, `numpy.random.default_rng`, 10.000 reamostragens — mesma convenção de todo o Degrau 1).

## Testes exatos (declarados agora, nunca escolhidos depois de ver os dados)

- Mann-Whitney U exato bilateral (`scipy.stats.mannwhitneyu`, `method="exact"`) para comparações entre 2 grupos (n=15 por grupo nesta campanha, não n=10 como na campanha oficial).
- Correção de Holm sobre a família de testes de cada hipótese (D1: 3 testes/instalação; D3/D4: por célula, famílias separadas de D1).
- Hodges-Lehmann (mediana das diferenças pareadas) com IC 95% via bootstrap (semente da rodada correspondente, 10.000 reamostragens).
- Nenhum teste novo introduzido depois de ver os dados reais do Degrau 2.

## As 5 hipóteses

### D1 — a heterogeneidade entre instalações (H4 do Degrau 1) é artefato do orquestrador?

**Previsão numérica:** no T_fluxo PAREDE (Degrau 1, Classic, L0), as 3 instalações diferiam em até ~145% entre si (sa-east-1 mediana 2.357,9ms vs. ap-northeast-1 mediana 5.786,2ms). Se essa heterogeneidade for, no todo ou majoritariamente, um artefato do overhead de orquestração (SSH+cold-start, que o Item 5b do Degrau 1 já estimou como dependente do RTT controle-cliente), as medianas de T_fluxo FINO (`t_fluxo_seconds`) das 3 instalações devem ficar **dentro de ~10-15% umas das outras** (ordem de grandeza do que resta depois de remover ~1,8s+ de overhead fixo mais o termo `b×RTT_cc` de cada uma).

**Teste exato:** Mann-Whitney exato bilateral, 3 pares (sa-east-1×us-east-1, sa-east-1×ap-northeast-1, us-east-1×ap-northeast-1), perfil Classic, rotas L0, T_fluxo FINO, n=15 por grupo por rodada (testado separadamente em cada rodada E nos dados agrupados das 2 rodadas, n=30). Holm sobre os 3 pares.

**Critério de decisão:** **REFUTADA** (H4 era majoritariamente artefato de medição) se os 3 pares perderem significância (p Holm ≥ 0,05) E as medianas ficarem dentro de ~15% umas das outras. **SUSTENTADA** (a heterogeneidade real persiste, não é só artefato) se pelo menos 1 dos 3 pares continuar significativo (p Holm < 0,05) com diferença de mediana >15%. **O que direi se os dados não sustentarem nenhum dos dois extremos:** relato explícito dos p-valores e das diferenças de mediana reais, sem forçar um dos dois rótulos — "parcialmente explicada" só se a redução de diferença for clara (ex. de ~145% pra <50%) mas a significância persistir.

### D2 — o overhead (parede − fino) segue a regressão do Item 5b do Degrau 1?

**Modelo (já estimado no Degrau 1, nunca reajustado aqui antes de ver dados novos):** `overhead_previsto_ms = a + b × RTT(controle,cliente)_ms`, com `a ≈ 1.807,3ms` (IC 95% publicado `[1.553,7; 1.924,9]`) e `b ≈ 13,17` (IC 95% publicado `[12,20; 15,29]`), ambos do `RELATORIO_ORIGEM.md`, Item 5b.

**RTT(controle,cliente) usado:** REAL, medido por `probe_overhead.py` (mediana de 30 conexões TCP novas à porta 22, Etapa 1) para `L0-us-east-1`/`L0-ap-northeast-1` — pela primeira vez sem aproximação externa. Para `L0-sa-east-1` e `L123`, o valor real já é conhecido do Degrau 1 (controle e servidor dessas rotas co-localizados em `sa-east-1`): `0,129ms` e `122,642ms` respectivamente — mas serão RECONFIRMADOS pelo mesmo `probe_overhead.py` nesta campanha, nunca só reaproveitados sem checar.

**Previsão numérica (fórmula declarada agora; valor exato finalizado de forma puramente mecânica quando `probe_overhead.py` rodar — isso não é ajustar a hipótese depois de ver resultados, é computar a mesma fórmula com o RTT real medido em vez do aproximado):**
- `L0-sa-east-1`: `1.807,3 + 13,17×0,129 ≈ 1.809,0ms`
- `L123`: `1.807,3 + 13,17×122,642 ≈ 3.422,3ms`
- `L0-us-east-1`/`L0-ap-northeast-1`: `1.807,3 + 13,17×RTT_cc_medido` (RTT_cc a determinar por `probe_overhead.py`).

**Critério de decisão:** **SUSTENTADA** se o overhead mediano observado (T_fluxo parede mediano − T_fluxo fino mediano) em cada uma das 4 células cair dentro do IC 95% do modelo (usando os extremos já publicados do IC de `a`/`b`: `[a_lo+b_lo×RTT; a_hi+b_hi×RTT]`) OU dentro de ±30% do ponto central — o que for mais permissivo — em pelo menos 3 das 4 células. **REFUTADA** se 3 ou mais células caírem fora dos dois critérios. **INCONCLUSIVA** no meio (exatamente 2 de 4 dentro, 2 fora).

### D3 — a ordem Classic<PQC<Hybrid e a inversão de L0-sa-east-1 persistem no T_fluxo fino?

**Previsão numérica:** no relatório oficial (T_fluxo parede), a ordem é `Classic<PQC<Hybrid` em `L123`/`L0-us-east-1`/`L0-ap-northeast-1` e `PQC<Classic<Hybrid` (inversão) em `L0-sa-east-1`. Como o overhead de orquestração é majoritariamente comum entre perfis (Degrau 1, item de impacto — exceto o viés pequeno de chave RSA, 26-45ms, já mostrado incapaz de trocar nenhum sinal), a previsão é que **a MESMA ordem persista no T_fluxo fino nas 4 células**, já que a causa da ordem (trabalho real de assinatura/verificação, Degrau 1 item 6) acontece DENTRO do T_fluxo fino, não fora dele.

**Teste exato:** comparação direta das medianas de T_fluxo fino por perfil, nas 4 células, mesma convenção de ordem do relatório oficial (Seção 4.2).

**Critério de decisão:** **SUSTENTADA** se a ordem persistir em ≥3 das 4 células. **REFUTADA** se divergir em ≥3 das 4 células. **INCONCLUSIVA** se exatamente 2 de 4 persistirem.

### D4 — onde mora a diferença ENTRE PERFIS no T_fluxo fino?

**Previsão numérica:** pela leitura de código já feita no Degrau 1 (item 6: PQC assina via despacho de rede ao serviço Node `pqc-signer`; Hybrid faz as duas coisas; verificação roteada pelo mesmo serviço nos 3 perfis), a previsão é que **Δ(signing_seconds + verification_seconds) entre PQC/Hybrid e Classic responda por ≥60% de Δ(T_fluxo fino)** em cada uma das 4 células, com **Δ(http_calls_seconds) <20%**.

**Teste exato:** decomposição direta de `phase_accounting` (`http_calls_seconds`, `signing_seconds`, `verification_seconds`, `explicit_wait_seconds`, `setup_seconds`, `residual_seconds`), medianas por perfil/célula, Δ calculado por subtração (nunca por mediana de diferenças por execução — mesma convenção de precisão usada no Degrau 1).

**Critério de decisão:** **SUSTENTADA** se a previsão (≥60% signing+verification, <20% http_calls) se confirmar em ≥3 das 4 células (para os 2 pares PQC-Classic e Hybrid-PQC, 8 comparações no total — "≥3 de 4" lido por célula, considerando os 2 pares daquela célula juntos). **REFUTADA** se a maior fração estiver em outro componente (ex. `residual_seconds` ou `setup_seconds`) em ≥3 das 4 células. **O que direi se a decomposição apontar pro `residual_seconds` interno da lib:** reportarei isso honestamente como um NOVO achado não previsto (o resíduo interno, que o próprio código documenta como "o hop do TLS-KEM-proxy e o handshake mTLS/KEM" — mecanismo já discutido no Degrau 1, item 5b, `c`≈19,40), sem forçá-lo a confirmar D4 como formulada.

### D5 — o T_fluxo fino em L123 cresce com o RTT real na magnitude que `c`≈19,40 prevê?

**Previsão numérica:** `Δresiduo_fino(L123 − L0-sa-east-1, Classic) / RTT_real(L123, medido por probe_overhead.py ou reconfirmado do Degrau 1 ≈122,642ms) ≈ c ≈ 19,40` — mesma faixa de tolerância do Degrau 1/H3 (metade a dobro: **9,70 a 38,80**).

**Teste exato:** `residuo_fino = t_fluxo_seconds − soma(latency_ms das chamadas HTTP reais)` (mesma decomposição do Degrau 1, mas sobre o T_fluxo FINO em vez do parede), mediana por célula, perfil Classic, razão `Δresiduo_fino / RTT_real`.

**Critério de decisão:** **SUSTENTADA** se a razão cair dentro de `[9,70; 38,80]`. **REFUTADA** se cair fora dessa faixa — sem categoria "inconclusiva" (mesma convenção do H3 original, pra manter o critério simétrico e não inflar categorias intermediárras).

## Resumo das previsões (tabela única, pra conferência rápida na Etapa 2)

| Hipótese | Previsão numérica | Critério SUSTENTADA | Critério REFUTADA |
|---|---|---|---|
| D1 | Medianas fino das 3 instalações dentro de ~10-15% entre si (vs. ~145% no parede) | 3 pares perdem significância (Holm) E dif. mediana <15% | ≥1 par mantém significância E dif. mediana >15% |
| D2 | `a+b×RTT_cc` por célula (ver valores acima) | ≥3/4 células dentro do IC/±30% | ≥3/4 células fora |
| D3 | Mesma ordem Classic/PQC/Hybrid do parede, inversão de L0-sa-east-1 incluída | Ordem persiste em ≥3/4 células | Ordem diverge em ≥3/4 células |
| D4 | signing+verification ≥60% de Δfino; http_calls <20% | confirmado em ≥3/4 células | maior fração em outro componente em ≥3/4 células |
| D5 | razão Δresiduo_fino/RTT entre 9,70 e 38,80 | dentro da faixa | fora da faixa |

## Reprodutibilidade

Nenhum dado de aquecimento (5 por célula, descartados) será lido nas análises da Etapa 2 — mesma regra do Degrau 1. Scripts da Etapa 0 (`probe_overhead.py`, script de coleta de `lscpu`/CPU) descritos no relatório da Etapa 0, nunca tocam nos scripts de medição existentes além da mudança aditiva já descrita (Etapa 0, item 2). Todo número das Etapas 1-2 virá de script, nunca digitado à mão.

# Degrau 1 — plano de investigação exploratória da origem das diferenças de latência

Pré-registro real: este documento é escrito e commitado **antes** de qualquer análise da Etapa 1 ser rodada. As hipóteses, previsões e critérios de decisão abaixo não podem ser alterados depois de ver os resultados — qualquer desvio encontrado depois será registrado explicitamente como desvio do plano, nunca silenciosamente incorporado.

Escopo: investigação exploratória ("Degrau 1"), sem AWS, sem alterar `campaign_oficial_conta_nova_raw/`, `campaign_oficial_conta_nova_organized/` nem `Consolidated_Metrics_Report_FINAL.md` (intocados). Um possível "Degrau 2" (experimento controlado) é mencionado no relatório final só como lacuna identificada, nunca executado aqui.

## Etapa 0 — inventário real dos campos disponíveis

Script: `scripts/etapa0_inventory.py`; saída completa: `data/etapa0_inventory.json`. Resumo do que foi **confirmado existir** (nunca assumido):

- **Nível de execução** (`piloto_calls.json`, 320 execuções, campos constantes nas 320): `profile`, `route`, `run`, `insurance` (44 chamadas), `person`, `start_utc`, `end_utc`, `cpu_client`, `cpu_server`, `retry_attempts`, `retry_failures`, `network_transport_retries`, `handshake_bytes_per_connection`, `n_client_facing_handshakes`.
- **Nível de chamada** (44/execução, campos constantes): `endpoint`, `full_uri`, `method`, `src`, `participant`, `request_bytes`, `response_bytes`, `total_bytes`, **`latency_ms`**, `start_utc`, `end_utc`, `pool_label`, `authorization_header`, `jwts`, `jwt_sizes`, `jwt_sig_breakdown`, `jwk_sizes`, `status_code`.
- **Achado real, documentado, não contornado:** `cpu_client`/`cpu_server` só têm `steal_pct`/`util_pct` (uso agregado da instância na janela da execução) — **não existe nenhum campo de tempo de CPU por fase** (signing/verification/setup, como existia em versões anteriores desta linha de pesquisa). Isso limita H3 a usar o microbenchmark LOCAL (Etapa 1, item 5) como única fonte de custo de CPU por primitiva — nunca um campo já existente nos dados da campanha.
- **`median_metrics.json`** (32 células, 4 perfis × 8 rotas): `metric`, `n`, `median`, `mean`, `stdev`, `min`, `max`, `values` (os 10 T_fluxo reais, segundos).
- **`criterio2_initcwnd_<rota>_<direção>.json`** (16 arquivos, 8 rotas × 2 direções, UM perfil por rota — `classico`, já que o `initcwnd` é propriedade do kernel/gateway, não do perfil criptográfico): `bytes_sent_total`, `bytes_sent_within_first_rtt_window`, `rtt_ms_used_for_window`, `mss_bytes`, `ss_ti_cwnd` (confirmado real: 10, em todas as amostras verificadas), `ss_ti_mss` (1448). Esses números vêm de medição real (`ss -i` + pcap), não de suposição.
- **`criterio7_rtt_por_rota.json`**: `rtt_ms_probe`, `rtt_ms_pcap`, `n_samples_probe` por rota (já usado no relatório oficial, Seção 6.1).
- **32 capturas dedicadas** (`campaign_oficial_conta_nova_organized/artifacts/<perfil>/<rota>/`): `.pcap` (tráfego real), `.log` (tamanhos por mensagem do tshark), `.keylog` (local apenas, nunca commitado). Lidas aqui com `scapy` (instalado localmente nesta sessão, só para análise offline de arquivo — nenhuma captura ao vivo, nenhuma conexão de rede).
- **`manifest.json`**: `route_orders` (ordem real dos 4 blocos por rota) e `seed=20261107` (semente da randomização da campanha, não desta análise).
- **Aquecimentos:** existem (`aquecimento_execucoes.json`) mas **não serão lidos em nenhuma análise desta investigação** — mesma regra já em vigor no relatório oficial.

## As 4 hipóteses, previsões concretas, testes e critérios de decisão

Sementes fixas desta investigação (novas, distintas das do relatório oficial — `20261116`/`20261116` eram do relatório; aqui usamos sementes próprias para manter a linhagem rastreável): **permutação = `20270101`**, **bootstrap = `20270102`**, ambas via `numpy.random.default_rng`, 10.000 iterações onde aplicável.

### H1 — ordem do bloco / deriva temporal dentro da rota
**Previsão concreta:** a posição de um perfil na ordem sequencial de blocos de uma rota (1º a 4º, `route_orders`) correlaciona com o T_fluxo mediano daquele bloco — blocos mais tardios sistematicamente mais lentos (ou mais rápidos) que blocos mais precoces, na mesma direção na maioria das 8 rotas. Adicionalmente, dentro de um mesmo bloco (as 10 execuções de um perfil/rota, em ordem temporal real — campo `run`), deve haver uma tendência monotônica (crescente ou decrescente) ao longo das 10.
**Teste exato:** (a) correlação de Spearman entre posição (1-4) e T_fluxo mediano do bloco, por rota (8 valores de rho) + teste de permutação (embaralha os rótulos de posição dentro de cada rota, recalcula a correlação combinada das 8 rotas, 10.000 permutações, semente `20270101`) para o p-valor da direção combinada. (b) Para cada uma das 32 células, tau de Kendall entre a ordem temporal (1-10, campo `run`) e o T_fluxo da execução, com p-valor de permutação (mesma semente) célula a célula.
**O que direi se os dados NÃO sustentarem:** se a correlação combinada não for significativa (p≥0,05) OU se a direção divergir entre rotas sem um padrão dominante, declaro H1 **REFUTADA** ou **INCONCLUSIVA** explicitamente — nunca vou reportar "uma tendência fraca" como se fosse evidência de deriva temporal.

### H2 — viagens de rede extras por volume de bytes (efeito initcwnd)
**Previsão concreta:** a inclinação de Dif(PQC−Classic) e Dif(Hybrid−PQC) (ms) contra o RTT real medido por rota deve ser aproximadamente um múltiplo inteiro do RTT (indicando K round-trips extras), e esse K deve ser compatível com o número de segmentos extras que o volume de bytes a mais de PQC/Hybrid exigiria dado o `cwnd` inicial REAL (10, confirmado no critério 2) e o MSS real (1448B) — calculado pela fórmula de slow-start, nunca assumido.
**Teste exato:** regressão linear simples (mínimos quadrados) de Dif_ms contra RTT_medido (pcap), 8 pontos, com IC 95% da inclinação via bootstrap (reamostragem dos 8 pares rota↔ponto, com reposição, 10.000 iterações, semente `20270102`). Comparação do IC da inclinação contra o K teórico (calculado a partir de bytes reais de handshake+payload por perfil, já conhecidos do relatório oficial, e do `cwnd`/MSS reais do critério 2).
**O que direi se os dados NÃO sustentarem:** se o IC da inclinação incluir 0 (sem relação com RTT) ou for incompatível com o K teórico (ordem de grandeza muito diferente), declaro H2 **REFUTADA** para a parte "RTT explica a diferença via round-trips extras" — mesmo que a diferença absoluta exista por outro motivo (ex.: CPU, H3).

### H3 — custo de CPU das primitivas criptográficas
**Previsão concreta:** nas rotas `L0-*` (RTT efetivamente zero, co-localizadas), a diferença de T_fluxo entre perfis deve ser da mesma ordem de grandeza que a diferença de custo de CPU previsto pelo microbenchmark local (Etapa 1, item 5), multiplicado pelo número real de operações que o fluxo executa por perfil (6 conexões mTLS, 26 assinaturas não-JWE, etc., já conhecidos do relatório oficial).
**Teste exato:** comparação direta (sem teste de hipótese formal — é uma comparação de ordem de grandeza) entre a diferença observada (mediana real, Seção 5.1 do relatório oficial, rotas L0) e a diferença prevista (soma das operações de CPU × contagem real de cada uma, do microbenchmark). "Mesma ordem de grandeza" definido aqui como razão entre 0,5x e 2x — declarado ANTES de ver os números.
**O que direi se os dados NÃO sustentarem:** se a diferença prevista por CPU for muito menor que a observada (razão fora de [0,5;2]), declaro H3 **REFUTADA** (ou, se a observada for muito menor que a prevista, igualmente REFUTADA) e deixo explícito que o microbenchmark local roda em hardware/condições diferentes da AWS real (ressalva de generalização), nunca comparando como se fosse 1:1.

### H4 — heterogeneidade entre as 3 instalações físicas
**Previsão concreta:** o T_fluxo do perfil Classic nas 3 rotas `L0-*` (uma por instalação: `sa-east-1`, `us-east-1`, `ap-northeast-1`) difere significativamente entre si, mesmo sendo o MESMO perfil sob RTT efetivamente igual (~0) nas 3 — indicando diferença de hardware/condições de instalação, não efeito do perfil criptográfico.
**Teste exato:** Mann-Whitney exato bilateral, as 3 comparações par a par entre as 3 instalações (Classic, L0, n=10 cada), com correção de Holm sobre essa família de 3 testes (família própria, nunca misturada com os 32 testes do relatório oficial). Complementado por uma decomposição real: para cada instalação, `T_fluxo − soma(latency_ms das 44 chamadas)` = resíduo (inclui handshake+setup+gaps não capturados por chamada individual) — comparar esse resíduo entre as 3 instalações pra localizar ONDE a diferença mora.
**O que direi se os dados NÃO sustentarem:** se as 3 comparações não mostrarem diferença significativa após Holm, declaro H4 **REFUTADA**. Se mostrarem diferença mas a decomposição não conseguir localizar a origem dentro dos campos disponíveis (achado real da Etapa 0: não há tempo de CPU por fase), declaro **INCONCLUSIVA quanto à causa exata**, nunca atribuo a um componente específico (ex.: "é a CPU da instância") sem evidência direta disso nos dados.

## Etapa 1 — análises a rodar (todas a partir de dados locais já existentes)
1. H1: permutação (posição do bloco) + tendência dentro do bloco (32 células).
2. Decomposição do T_fluxo por componente real disponível (soma das 44 `latency_ms` vs. resíduo), por célula — nunca estimando um componente sem dado real por trás (achado da Etapa 0 limita isso à soma-vs-resíduo, não a um breakdown handshake/TTFB/transferência mais fino, que exigiria campos que não existem).
3. H2: regressão Dif vs. RTT + comparação com K teórico via `cwnd`/MSS reais do critério 2.
4. H4: decomposição nas 3 rotas L0 + Mann-Whitney 3x.
5. H3 + microbenchmark LOCAL em Go (reusa `thesis/results/v9/integration/bench/main.go`, já existente no repositório, mesma toolchain `mockopin-v9-toolchain` via Docker — roda na máquina local do operador, nunca na AWS) + benchmark NOVO de validação de cadeia de certificados por perfil (não cobrado pelo `bench/main.go` existente), usando os certificados reais já commitados em `thesis/results/v9/certs/generated/` (só os `.crt`, nunca as chaves privadas).
6. Aquecimentos nunca lidos.

## Etapa 2 — relatório
Para cada hipótese: veredito SUSTENTADA/REFUTADA/INCONCLUSIVA com os números reais, lacunas remanescentes listadas explicitamente, e o tipo de experimento controlado que resolveria cada lacuna (descrito, nunca executado).

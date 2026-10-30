# ANALYSIS_PLAN.md (v8) -- pré-registro, antes da coleta oficial

Este documento declara, antes de qualquer janela oficial rodar, as
regras de aquecimento e os critérios de aceitação que serão aplicados
aos dados -- para que nenhuma escolha metodológica seja feita depois de
olhar os resultados.

## Aquecimento (Decision 102, 2026-10-30)

- **Política: K=5 execuções extras de aquecimento por célula**
  (instalação x perfil x cenário), descartadas de toda estatística,
  declaradas ANTES da coleta -- não ajustadas depois de olhar os
  resultados.
- Gravadas em `warmup/w{janela:02d}_warm{01..05}.json`, dentro do
  próprio diretório da célula -- nunca em `runs/`, nunca contadas por
  `already_done()`/pelo consolidador.
- Adicional ao aquecimento de bloco já existente (`switch_crypto_
  profile.py`'s 5 execuções de settling, por troca de perfil) e ao
  único aquecimento por célula já existente (`run_warmup()`,
  `run00_warmup_window{NN}.json`) -- este K=5 não substitui nenhum dos
  dois, soma-se a eles.
- **Por quê K=5**: achado real no Piloto 3 (24 células, janela única,
  2026-10-29) -- Mann-Kendall por célula mostrou tendência de queda
  significativa em 10/24 células (41,7%), todas na mesma direção.
  Testando onde cada célula estabiliza (menor K tal que o Mann-Kendall
  nas execuções restantes deixe de ser significativo): mediana K=0,
  máximo K=5 (sa-east-1/pqc/L123). K=3 cobre 87,5% das células; **K=5
  cobre 100%** -- escolhido para não deixar nenhuma célula com
  resíduo de tendência conhecido.
- **Comparação com a v7**: a v7 usou exatamente **1** execução de
  aquecimento por célula (`run00_warmup.json`, confirmado em `thesis/
  results/v7/DECISIONS.md`) -- igual ao padrão da v8 antes desta
  decisão. O achado do Piloto 3 mostra que 1 execução não bastava para
  uma fração relevante das células; v7 nunca testou isso diretamente
  (dado antigo, sem o diagnóstico do Piloto 3 disponível na época).

## Calendário e política de janelas (Decision 102)

- Sem horário fixo (23:00/07:00/15:00 UTC cancelado) -- janelas
  compactas, sem pausas internas (`CAMPAIGN_ALERT_ONLY_BUDGET=1`).
- Intervalo fixo de 30 minutos entre o fim de uma janela e o início da
  próxima -- só para puxar dados, gerar manifesto, escanear segredos e
  commitar; nenhum tráfego de coleta nesse intervalo.
- Janela seguinte é **automática** se a anterior terminou com **zero
  erros E steal médio < 5%** (`compute_window_health()`,
  `campaign_run.py`) -- qualquer outro resultado cai no portão manual
  já existente (`wait_for_operator_gate()`), nunca avança sozinho
  sobre um problema real.
- Teto cumulativo de custo: **US$80**, parar-e-perguntar em **US$72**.

## Critérios de aceitação (resumo -- ver pilot_acceptance.py para a
lista completa dos 11 critérios)

- `BASELINE_BYTES`/`V8_OPINSIZE` por perfil, tolerâncias e testes
  estatísticos (Shapiro-Wilk, Mann-Whitney, bootstrap) -- inalterados
  por este documento, ver `pilot_acceptance.py`.
- Consolidação (`consolidate_v8.py`) roda por perfil (`profiles ->
  perfil -> instalação -> cenário`) e produz uma visão cruzada entre
  perfis (`cross_profile_t_fluxo_comparisons`) -- não um "global" único
  separado, a visão cruzada já cobre esse papel.

## Reduções de overhead aprovadas (Decision 105, 2026-10-30)

Aprovadas pelo Luciano, com ele presente, antes de qualquer coleta
oficial -- cada uma com o dado real que a justifica:

- **(a) Aquecimentos extras sem pcap nem coletores**: já implementado
  (Decision 103, `run_extra_warmups()`) -- grava só o JSON do fluxo,
  nunca inicia tcpdump/sampler de CPU. Não toca no que é medido porque
  aquecimento nunca entrou na estatística.
- **(b) Remoção do ping de referência** (`ping -c 10`, cliente ->
  servidor, dentro de cada execução): achado real (Decision 104) --
  ICMP está sempre bloqueado pelo security group, o ping sempre espera
  os ~9,3s completos sem nunca retornar um RTT real (`rtt_avg_ms` já
  vinha `null` por causa disso). RTT/jitter continuam vindo do próprio
  pcap (`rtt_jitter_ms`, Decision 94) e do novo pré-flight TCP (porta
  443, uma vez por cliente, antes de qualquer janela --
  `preflight_tcp.py`, roda a partir do PRÓPRIO cliente via SSH, não de
  control, porque o caminho de rede é diferente). Implementado:
  `run_one_execution()` não chama mais `ping`, não grava mais
  `{label}_ping.json`.
- **(c) As 3 instalações em paralelo**: seguro porque cada instalação
  tem seu próprio servidor dedicado (nenhum cliente de uma fala com o
  servidor de outra, confirmado no `inventory.json`), e
  `_SERVER_LOCKS[installation]` (já existia, `threading.Lock` real) já
  impede duas execuções simultâneas NO MESMO servidor -- paralelizar
  por instalação nunca pode violar essa regra. `CAMPAIGN_PARALLEL_
  INSTALLATIONS=1` (padrão desligado) ativa isso tanto na validação de
  24 execuções quanto nas janelas reais.

**Critério de aceite da validação em paralelo**: as 24 células (1
execução cada) devem cair dentro do IC95% real do piloto 3 para
aquela mesma célula (`PILOT3_T_FLUXO_CI95`, hardcoded a partir de
`consolidated.json`) E zero erros. Se falhar, o próprio código desarma
`CAMPAIGN_PARALLEL_INSTALLATIONS` e as janelas reais rodam
sequenciais -- sem intervenção manual.

## Decomposição por participante

`bytes_by_participant()` (`consolidate_v8.py`) já existe e já roda
como parte da consolidação normal -- não é um script separado pendente.

---

Este arquivo deve ser commitado com uma tag `v8-prereg` ANTES de
qualquer janela oficial começar -- o próprio sentido de um pré-registro
é existir antes da coleta, não depois.

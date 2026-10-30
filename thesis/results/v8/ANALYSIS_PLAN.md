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

## Decomposição por participante

`bytes_by_participant()` (`consolidate_v8.py`) já existe e já roda
como parte da consolidação normal -- não é um script separado pendente.

---

Este arquivo deve ser commitado com uma tag `v8-prereg` ANTES de
qualquer janela oficial começar -- o próprio sentido de um pré-registro
é existir antes da coleta, não depois.

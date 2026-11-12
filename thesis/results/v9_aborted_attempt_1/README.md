# Tentativa abortada da campanha oficial v9 -- NAO usar nesta analise final

Esta pasta e um arquivamento da PRIMEIRA tentativa de execucao real da campanha
oficial v9, interrompida por queda do orquestrador (nao concluida).

- **Lancada:** 2026-11-12T16:13:10Z (codigo congelado no commit `4a1210ea`,
  tag local `v9-campanha-oficial-congelada`).
- **Interrompida (crash):** entre 2026-11-12T19:28Z e 2026-11-12T19:34Z,
  descoberta ao checar o andamento.
- **Causa real:** `RuntimeError` em `_tcp_preflight` -- o cliente da rota L14
  (ca-central-1, IP 16.52.219.70) ficou inalcancavel por SSH porque seu
  proprio dead man's switch (heartbeat) ja tinha expirado e parado a
  instancia com seguranca (`stop`). Raiz do problema: a renovacao em lote
  (`renew_all_safety_timers`, no inicio da janela) da 3h de margem a TODOS os
  hosts de uma vez, mas a renovacao PER-ROTA (`renew_safety_timers`) so toca
  cada host quando o laco principal chega naquela rota -- numa janela real de
  ~5,2h (mais que as 3h de margem inicial), uma rota perto do FIM da ordem de
  execucao pode ter seu prazo original vencido antes do laco chegar nela.
  Ver Decisao 138 em `thesis/results/v9/DECISIONS.md` para o registro
  completo, a correcao do heartbeat (processo/thread de renovacao propria,
  independente do laco principal) e a decisao de reiniciar do zero.
- **Estado no momento da queda:** 200 de 320 execucoes medidas (62%), 100 de
  160 aquecimentos, 20 de 32 capturas dedicadas, **0 falhas de execucao**
  (a queda foi do PROCESSO, nunca de uma celula/medicao invalida). Custo
  estimado no momento ≈US$30,64 (relogio desde 2026-11-11T22:11:25Z).
- **Frota:** nenhuma instancia foi terminada/destruida em nenhum momento
  (so `stop`, confirmado via AWS real apos a queda) -- as 12 instancias e os
  12 EIPs permanecem intactos.

`oficial_out/` dentro desta pasta e uma copia INTOCADA do diretorio de saida
real do orquestrador no controle no momento da queda (runs_raw/,
criterio1_capturas/, manifest_partial.json, etc.) -- nunca movida/alterada,
so copiada. A campanha oficial foi relancada do ZERO (janela unica nova,
novo commit/tag) apos esta queda; os dados aqui NUNCA entram na analise/
organizacao final de `thesis/results/v9/`.

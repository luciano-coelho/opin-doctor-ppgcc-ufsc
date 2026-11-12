# Segunda tentativa abortada da campanha oficial v9 -- NAO usar nesta analise final

Esta pasta e um arquivamento da SEGUNDA tentativa de execucao real da campanha
oficial v9, interrompida por queda do orquestrador (nao concluida). Ver
tambem `thesis/results/v9_aborted_attempt_1/` (primeira queda, causa
diferente) e Decisao 139 em `thesis/results/v9/DECISIONS.md`.

- **Lancada:** 2026-11-12T20:05:38Z (codigo congelado no commit `beced991`,
  tag local `v9-campanha-oficial-congelada-v2` -- ja incluia a correcao do
  heartbeat da Decisao 138).
- **Interrompida (crash):** descoberta ao checar o andamento as
  ~2026-11-12T20:20Z-21:40Z.
- **Causa real:** `RuntimeError` em `run_execution` -- timeout de SSH
  transitorio pro cliente da rota L123 (ca-central-1, IP 15.175.74.137)
  durante a 3a execucao da celula `classico/L123`. **O heartbeat corrigido
  (Decisao 138) funcionou corretamente desta vez** -- confirmado: as 12
  instancias continuaram `running`, nenhuma se autoparou. O host L123
  estava acessivel normalmente poucos minutos depois (uptime continuo,
  nunca parou) -- um blip transitorio de rede/SSH, nao um problema
  persistente. Causa raiz: `run_execution` nao tinha nenhuma logica de
  retry -- uma unica falha transitoria matava o processo inteiro mesmo com
  os hosts saudaveis. Lacuna do codigo congelado ORIGINAL (nunca introduzida
  nesta sessao) -- corrigida na Decisao 139 (retry so pra excecoes de
  transporte, ver DECISIONS.md).
- **Estado no momento da queda:** 40 de 320 execucoes medidas (12%), 20 de
  160 aquecimentos, 4 de 32 capturas dedicadas, **0 falhas de
  execucao/medicao invalida** (a queda foi do PROCESSO, nunca de uma
  celula/medicao invalida).
- **Frota:** nenhuma instancia foi parada, terminada ou destruida por esta
  queda -- todas as 12 continuaram `running` o tempo todo (heartbeat
  corrigido funcionando). So os containers orfaos do cliente L123
  (`pqc_signer_service_run`, `tls_kem_proxy_run`, da execucao interrompida)
  foram removidos manualmente antes do relancamento -- nenhuma instancia/
  volume/EIP/chave/security group tocado.

`oficial_out/` dentro desta pasta e uma copia INTOCADA do diretorio de saida
real do orquestrador no controle no momento da queda -- nunca movida/
alterada, so copiada. A campanha oficial foi relancada do ZERO (terceira
tentativa, janela unica nova, novo commit/tag v3, com retry em
`run_execution`) apos esta queda; os dados aqui NUNCA entram na analise/
organizacao final de `thesis/results/v9/`.

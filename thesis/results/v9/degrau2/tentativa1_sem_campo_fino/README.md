# Tentativa 1 — Rodadas 1 e 2 do Degrau 2, sem T_fluxo fino (arquivado)

Dados reais das duas primeiras rodadas da campanha suplementar (sementes `20261117`/`20261118`, 360 execucoes + 120 aquecimentos, 0 falhas, coletados e sha256-verificados). **Nao apagar, nao misturar com dados de rodadas futuras.**

**Causa:** a mudanca aditiva da Etapa 0 (commit `02b1fa9d`) tocou so o dict de retorno de `run_execution()` em `orchestrator.py`. Uma segunda camada de serializacao dentro de `run_pilot()` (`aquecimento_entry`/`execucao_entry` -- os dicts que de fato persistem em disco) tinha sua propria lista fixa de chaves, que nunca incluia `t_fluxo_fino_seconds`/`phase_accounting`, descartando-os silenciosamente. Detalhe completo: `thesis/results/v9/DECISIONS.md`, Decisao 212.

**Impacto:** nenhum dos 480 registros aqui contem T_fluxo fino ou `phase_accounting`. As 7 analises (D1, D2, D2b, D3, D4a, D4b, D5) de `PLANO_DEGRAU2.md` + Emenda 1 dependem de pelo menos um dos dois campos -- nenhuma pode ser feita com estes dados. Todos os campos PAREDE (`start_utc`/`end_utc`/`insurance`/`cpu_*`/etc.) permanecem validos e intactos -- so os 2 campos novos estao ausentes.

**Correcao:** `orchestrator.py` corrigido no mesmo commit em que este achado foi registrado (`fe532c9e`) -- `aquecimento_entry`/`execucao_entry` agora repassam as 2 chaves. Rodada 3 (dados em `thesis/results/v9/degrau2/campaign_data/`, fora deste diretorio de arquivamento) repete o mesmo plano com o codigo corrigido.

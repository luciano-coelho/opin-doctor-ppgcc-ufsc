# Degrau 2 — estado final desta sessão

Atualizado em `2026-11-17T11:30Z` aproximadamente. Substitui o checkpoint anterior (abaixo, mantido como histórico) — Etapa 2 foi concluída.

## O que foi feito até aqui

1. **Achado crítico (Decisão 212):** as 2 rodadas originais do Degrau 2 (`tentativa1_sem_campo_fino/`) não continham `t_fluxo_fino_seconds`/`phase_accounting` em nenhum registro — bug de serialização em `orchestrator.py` (segunda camada, `execucao_entry`/`aquecimento_entry`, nunca tocada pela mudança aditiva original). Corrigido localmente (commit `fe532c9e`), sem nenhuma ação na AWS.
2. **Teste de fumaça:** passou integralmente (1 execução + 1 aquecimento, caminho completo até o disco, todos os campos presentes e não-nulos).
3. **Porta de segurança (gate_watcher.py):** implementada, roda em paralelo a cada rodada, confere o primeiro `run01.json` real. **Passou nas duas rodadas** (`ok: true`), nunca abortou nada.
4. **Rodada 3 completa — repetição do plano pré-registrado com o código corrigido:**
   - Round1 (seed `20261117`): 180/180 execuções, 60/60 aquecimentos, exit code 0, custo ~US$2,86. 2/12 capturas dedicadas falharam (categoria "decifragem incompleta", não-fatal, autotratada).
   - Round2 (seed `20261118`): 180/180 execuções, 60/60 aquecimentos, exit code 0, custo ~US$2,77. **12/12 capturas dedicadas falharam** — mesma categoria textual/estrutural ("decifragem incompleta em 3 tentativas", nunca "divergência de tamanho"), padrão uniforme nas 3 tentativas em todas as 12 células inspecionadas — **mas com taxa de falha muito maior que a Rodada 1 (100% vs 17%), sugerindo causa sistêmica da janela da Rodada 2, não aleatoriedade por execução. Isso NÃO afeta `t_fluxo_fino_seconds`/`phase_accounting` (campos centrais do Degrau 2) — é uma falha ortogonal, do critério 1 (verificação de tamanho de certificado via captura TLS dedicada), não do cronômetro fino.** Fica registrado como achado a investigar separadamente, não bloqueia D1-D5.
   - Nenhum outro tipo de falha (transporte, assinatura, Traceback não-tratado) em nenhuma das duas rodadas.
   - Custo total Rodada 3: **~US$5,63** (bem abaixo do limite de US$12).

## Estado atual confirmado agora (re-verificado do zero, não assumido)

- **Processos:** nenhum `orchestrator.py`/`gate_watcher.py` ativo em controle (`pgrep` limpo); `launch_persistent.py status` confirma `alive: false` para as duas rodadas.
- **Frota:** os 8 hosts necessários estão `running` (confirmado via `describe-instances` de leitura, 4 regiões). **Nenhum `stop-instances`/`terminate-instances` foi executado em nenhum momento desta sessão.**
- **Deadline:** ~0,96h (58min) restantes nos 8 hosts, contando sem renovação desde o fim da Rodada 2 (o heartbeat do orquestrador para quando o processo termina).

## O que foi concluído depois deste checkpoint

- **Coleta de dados:** Rodada 1 -- 376 arquivos verificados por sha256; Rodada 2 -- 346 arquivos verificados por sha256 (`collect_artifacts.py`).
- **Verificação de campos obrigatórios:** nos 480 registros reais (360 execuções + 120 aquecimentos) -- 0 problemas. `t_fluxo_fino_seconds`, os 6 componentes de `phase_accounting`, `start_utc`/`end_utc`, `insurance[].latency_ms` presentes em 100% dos arquivos.
- **Deadline encurtado** para `2026-11-17T11:24:49Z` (agora+10min) nos 8 hosts, escrita atômica com leitura de confirmação -- frota se desliga sozinha via dead-man's-switch. Nenhum `stop-instances`/`terminate-instances` chamado.
- **Etapa 2 concluída:** as 7 análises (D1, D2, D2b, D3, D4a, D4b, D5) rodadas conforme `PLANO_DEGRAU2.md` + Emenda 1, sem alterar critérios/testes/sementes/regras de agregação. Regra das 2 rodadas aplicada primeiro -- 0/28 divergências, pooling permitido em todas as análises. Resultado completo: `RELATORIO_ETAPA2_D1_D5.md` (rascunho para revisão, não final/publicado) + `ETAPA2_RESULTADOS.json` (todos os números).
  - **Resumo dos vereditos:** D1 SUSTENTADA, D2 REFUTADA (margem pequena na inclinação), D3 SUSTENTADA (mas a inversão de L0-sa-east-1 NÃO persiste no T_fluxo fino), D4a REFUTADA, D4b PARCIAL, D5 SUSTENTADA.
- **Auditoria independente** (agente separado, nunca leu arquivo de chave) encontrou 1 achado de alta severidade (denominador não-declarado em D4a/D4b) e outros menores -- todos corrigidos antes deste relatório ser tratado como pronto para revisão (nenhum veredito final mudou, só números de suporte). Detalhe completo das correções: seção própria no `RELATORIO_ETAPA2_D1_D5.md`.
- Tudo commitado localmente (sem push, sem force, sem mover tags) -- commits `42a3b175` (Rodada 3 + dados) e o commit desta Etapa 2.

**Frota confirmada `stopped` nos 8 hosts** (checagem de leitura `describe-instances`, 4 regiões, feita ~11min depois do deadline) -- todos com `Reason: "User initiated"` (o dead-man's-switch roda `shutdown -h now` dentro do guest, nunca uma chamada de API AWS de stop/terminate). **Nenhum `stop-instances`/`terminate-instances` foi chamado em nenhum momento desta sessão.**

## O que depende do usuário agora

Revisar `RELATORIO_ETAPA2_D1_D5.md` -- é um rascunho, explicitamente marcado como não-final. Decidir se investiga separadamente o achado da taxa de falha de captura dedicada 100% na Rodada 2 (não bloqueia nada, mas é um achado real não explicado).

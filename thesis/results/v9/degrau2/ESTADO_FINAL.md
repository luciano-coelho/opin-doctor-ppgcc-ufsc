# Degrau 2 — estado atual (checkpoint, ainda não final)

Checkpoint escrito em `2026-11-17T10:03Z` aproximadamente, a pedido do coordenador, após travamento de stream (watchdog) durante a transição entre a verificação do gate da Rodada 2 e a coleta de dados.

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

## O que falta (em andamento agora, nesta mesma sessão)

- Coleta de dados da Rodada 3 (`collect_artifacts.py`, sha256) — **ainda não iniciada** no momento deste checkpoint.
- Verificação dos campos exigidos (item 2 do prompt anterior) nos dados coletados.
- Decisão sobre encurtar o deadline para agora+10min — **só se a verificação acima passar integralmente.**
- Etapa 2 (análises D1-D5) — não iniciada.

## O que depende do usuário agora

Nada neste momento — autorização de autonomia condicional já concedida cobre os próximos passos (coleta, verificação, Etapa 2), desde que nenhum novo gatilho de parada apareça. Este arquivo será atualizado novamente ao final.

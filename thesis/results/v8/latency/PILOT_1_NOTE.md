# Piloto 1: fluxo sem verificação de assinatura (42 chamadas), não usado no artigo

Os dados nesta pasta (`thesis/results/v8/latency/`) vêm do primeiro
piloto real na AWS (sa-east-1, `L0`/`L325`, 60/60 execuções). O
`opin_flow.py` que os gerou não verificava nenhuma assinatura recebida
(`verify_signature: False` em todo lugar) e fazia 42 chamadas por
execução, não 44.

Preservados sem alteração -- serviram para validar a infraestrutura
real da AWS (entrega, orquestrador, conectividade, pull/verificação de
manifesto). **Os números em si não são os dados do artigo.**

Os dados do artigo virão do piloto 2 (fluxo completo, verificação de
assinatura ativa nos 3 perfis, 44 chamadas por execução) -- ver
`thesis/results/v8/campaign/PILOT_RUNBOOK.md` e `thesis/results/v8/
DECISIONS.md` (Decisions 87/88).

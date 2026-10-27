# Piloto 1: fluxo sem verificação de assinatura (42 chamadas), não usado no artigo

Os dados nesta pasta (`thesis/results/v8/latency-pilot1-no-verification/`,
movida para este nome próprio 2026-10-27 quando o piloto 2 passou a
existir de verdade -- antes vivia em `thesis/results/v8/latency/`) vêm
do primeiro piloto real na AWS (sa-east-1, `L0`/`L325`, 60/60
execuções). O `opin_flow.py` que os gerou não verificava nenhuma
assinatura recebida (`verify_signature: False` em todo lugar) e fazia
42 chamadas por execução, não 44.

Preservados sem alteração -- serviram para validar a infraestrutura
real da AWS (entrega, orquestrador, conectividade, pull/verificação de
manifesto). **Os números em si não são os dados do artigo.**

Os dados do artigo são os do piloto 2 (fluxo completo, verificação de
assinatura ativa nos 3 perfis, 44 chamadas por execução), em
`thesis/results/v8/latency-pilot2-full-flow/` -- ver
`thesis/results/v8/campaign/PILOT_RUNBOOK.md` e `thesis/results/v8/
DECISIONS.md` (Decisions 87/88/89).

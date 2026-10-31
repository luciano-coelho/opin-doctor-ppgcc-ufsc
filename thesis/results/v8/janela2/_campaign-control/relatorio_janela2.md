# Relatório — Janela 2 (hybrid/pqc/classic, seed=0)

1. **240/240 execuções, 0 erros, steal médio 0,01%** — saudável, avanço automático.
2. **Deriva (Mann-Kendall, 24 células): 4/24 (16,7%), todas em queda** — similar à janela 1 (3/24), residual baixo mesmo com K=5.
3. **Checagem confirmatória (Decision 111) contra a janela 2**: k contém 56 nos 3 perfis (PASSOU); Hybrid `a`>0 não cruza zero (PASSOU); **PQC `a` NÃO cruza zero desta vez (+32,33ms, IC [+15,34;+53,14]ms) — a previsão 3 FALHOU**; **PQC `b` também não cruza zero (-0,1611, IC [-0,2860;-0,0277]) — a previsão 4 FALHOU para PQC** (Hybrid `b` ainda cruza zero, essa parte passou); ordem Hybrid>Classic 8/8 (passou), PQC>Classic 7/8 (ainda sem direção fixa forte).
4. **Achado real, não forçado**: PQC mostra um custo fixo pequeno mas real na janela 2 (ausente na janela 1) e um `b` negativo significativo (ficando relativamente mais rápido que Classic em RTTs maiores) — não replica a janela 1, reportado honestamente.
5. **Pronto para a janela 3** (pqc/classic/hybrid) — sem trava acionada, commit feito antes do início.

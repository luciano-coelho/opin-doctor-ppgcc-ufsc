# Relatório — Janela 3 (pqc/classic/hybrid, seed=0)

1. **240/240 execuções, 0 erros, steal médio 0,01%** — saudável, última janela da campanha.
2. **Deriva (Mann-Kendall, 24 células): 3/24 (12,5%), todas em queda** — similar às janelas 1 (3/24) e 2 (4/24), residual baixo mesmo com K=5.
3. **Checagem confirmatória (Decision 111) contra a janela 3, isoladamente**: k contém 56 só para Hybrid (PASSOU); Classic e PQC ficam fora por pouco (IC [56,12;56,60] e [56,01;56,83] — **previsão 1 FALHOU para Classic e PQC nesta janela isolada**); Hybrid `a`>0 não cruza zero (PASSOU); **PQC `a` volta a cruzar zero** (-1,66ms, IC [-19,77;+16,47]ms — previsão 3 PASSOU, ao contrário da janela 2); `b` indistinguível de zero nos dois perfis (PASSOU para Hybrid e para PQC, ao contrário da janela 2); ordem Hybrid>Classic 8/8 (passou), PQC>Classic 7/8.
4. **Combinado (janelas 1+2+3, 30 execuções/célula)**: k contém 56 para Classic e Hybrid (PASSOU), fica fora por pouco para PQC (IC [56,03;56,58] — FALHOU); Hybrid `a`=+87,88ms IC95%=[+79,85;+96,27]ms não cruza zero (PASSOU); PQC `a`=+13,74ms IC95%=[-1,26;+31,20]ms cruza zero (PASSOU); `b` indistinguível de zero nos dois perfis (PASSOU); ordem Hybrid>Classic 8/8, PQC>Classic 7/8.
5. **Achado real, não forçado**: PQC oscila entre janelas (sem custo fixo detectável nas janelas 1 e 3, com custo fixo pequeno só na janela 2) — no combinado de 30 execuções/célula a previsão 3 (PQC `a`≈0) e a previsão 4 (`b`≈0) voltam a passar, e só a previsão 1 (k=56) falha por uma margem pequena para PQC. Reportado honestamente, sem forçar consistência entre janelas.

Campanha de 3 janelas oficiais concluída: 720 execuções reais, 0 erros em qualquer janela.

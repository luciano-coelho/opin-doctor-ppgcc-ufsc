# Relatório — Janela 1 (classic/hybrid/pqc, seed=0)

1. **240/240 execuções, 0 erros, steal médio 0,01%** — saudável, avanço automático confirmado pelo próprio orquestrador.
2. **Deriva (Mann-Kendall, 24 células): 3/24 (12,5%) com tendência significativa, todas em queda** — bem abaixo dos 10/24 (41,7%) do piloto 3, consistente com o K=5 funcionando.
3. **Razões entre perfis vs. piloto 3**: Hybrid/Classic desvio médio -0,46% (máx. 2,54%); PQC/Classic desvio médio -0,67% (máx. 3,40%) — ambas bem dentro de 5%.
4. **Custo/tempo**: ~6,9h de execução real, dentro do teto de US$40 desta subida.
5. **Pronto para a janela 2** (hybrid/pqc/classic) — sem trava acionada, commit feito antes do início.

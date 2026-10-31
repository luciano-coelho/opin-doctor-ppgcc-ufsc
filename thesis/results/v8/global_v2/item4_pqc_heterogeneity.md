# Item 4 (Luciano, 2026-10-31) -- PQC: k com duas leituras + teste de heterogeneidade

## k com as duas leituras (combinado, 30 execuções/célula)

| perfil  | k      | IC95% de k        | IC contém 56? | k dentro de 56±1? |
|---------|--------|--------------------|---------------|---------------------|
| classic | 56,03  | [55,91; 56,78]     | **sim**       | sim                 |
| pqc     | 56,13  | [56,03; 57,52]     | **não**       | **sim**             |
| hybrid  | 55,99  | [55,91; 56,55]     | **sim**       | sim                 |

PQC passa pela leitura mais permissiva (ponto estimado dentro de
56±1) mas falha pela leitura do intervalo de confiança (o IC95% não
cruza 56, ficando inteiramente acima) -- as duas leituras são
reportadas, nenhuma escondida.

## Teste de heterogeneidade entre janelas (custo fixo `a`, PQC vs. Classic)

Estimativas por janela (já no Decision 113/114, repetidas aqui com o
erro-padrão derivado do IC95% bootstrap, `se = (hi-lo)/(2*1.96)`):

| janela | a        | IC95%              | se      |
|--------|----------|---------------------|---------|
| 1      | +5,36ms  | [-29,84; +35,09]ms  | 16,56ms |
| 2      | +32,33ms | [+15,26; +52,30]ms  | 9,45ms  |
| 3      | -1,66ms  | [-18,44; +16,15]ms  | 8,82ms  |

**Teste par a par** (Z = (a_i - a_j) / sqrt(se_i² + se_j²)):

| par              | Z     | p      | resultado          |
|------------------|-------|--------|---------------------|
| janela1 vs janela2 | -1,41 | 0,1574 | não significativo  |
| janela1 vs janela3 | +0,37 | 0,7084 | não significativo  |
| **janela2 vs janela3** | **+2,63** | **0,0086** | **SIGNIFICATIVO** |

**Teste omnibus (Cochran's Q, meta-análise de efeitos fixos)**:
Q = 7,160, df = 2, **p = 0,0279** -- heterogeneidade significativa
entre as 3 janelas.

## Conclusão -- correção ao texto da Decision 114

A Decision 114 dizia "isso sugere que o achado da janela 2 era mais
provavelmente ruído de amostra". **Este teste não sustenta essa
afirmação como estava escrita.** O par janela2-vs-janela3 é
significativo (p=0,0086) e o teste omnibus entre as 3 janelas também
é (p=0,0279) -- a variação do custo fixo do PQC entre janelas é
estatisticamente detectável, não apenas visualmente diferente. Isso
não prova qual é a causa (ordem dos perfis dentro de cada janela,
efeito de hardware/rede real ao longo do tempo, ou uma real não-
estacionariedade do próprio PQC), mas descarta a leitura de "ruído
de amostra puro" sem qualificação. Registrado honestamente como
achado aberto -- não investigado a fundo aqui por escopo de tempo.

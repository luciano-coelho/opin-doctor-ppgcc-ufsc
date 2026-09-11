# Latency Report (pqc, 30ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 25.6640s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 25.773780 | 0.171274 | não |
| 2 | 26.314036 | 0.368982 | não |
| 3 | 26.023564 | 0.078510 | não |
| 4 | 25.683598 | 0.261456 | não |
| 5 | 26.867573 | 0.922519 | não |
| 6 | 29.803029 | 3.857975 | não |
| 7 | 27.094458 | 1.149404 | não |
| 8 | 25.866544 | 0.078510 | não |
| 9 | 25.634922 | 0.310132 | não |
| 10 | 25.093431 | 0.851623 | não |

## Valores ordenados (ordem crescente)

25.093431, 25.634922, 25.683598, 25.773780, 25.866544, 26.023564, 26.314036, 26.867573, 27.094458, 29.803029

## Mediana e dispersão

- Mediana: **25.945054s**
- Mínimo: 25.093431s
- Máximo: 29.803029s
- Média: 26.415494s
- Desvio padrão (amostral): 1.329604s
- Spread (min/max): 18.7683%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 18.7683% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

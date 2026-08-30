# Latency Report (pqc, 225ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 46.4858s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 45.973481 | 0.098663 | não |
| 2 | 45.778616 | 0.096202 | não |
| 3 | 46.046172 | 0.171354 | não |
| 4 | 45.816040 | 0.058778 | não |
| 5 | 45.919914 | 0.045096 | não |
| 6 | 45.800727 | 0.074091 | não |
| 7 | 45.891021 | 0.016203 | não |
| 8 | 46.240289 | 0.365471 | não |
| 9 | 45.730924 | 0.143894 | não |
| 10 | 45.858614 | 0.016204 | não |

## Valores ordenados (ordem crescente)

45.730924, 45.778616, 45.800727, 45.816040, 45.858614, 45.891021, 45.919914, 45.973481, 46.046172, 46.240289

## Mediana e dispersão

- Mediana: **45.874818s**
- Mínimo: 45.730924s
- Máximo: 46.240289s
- Média: 45.905580s
- Desvio padrão (amostral): 0.150800s
- Spread (min/max): 1.1138%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 1.1138% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

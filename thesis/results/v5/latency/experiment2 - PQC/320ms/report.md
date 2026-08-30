# Latency Report (pqc, 320ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 62.9989s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 62.535255 | 0.144807 | não |
| 2 | 62.419683 | 0.029235 | não |
| 3 | 62.477588 | 0.087140 | não |
| 4 | 62.361213 | 0.029235 | não |
| 5 | 62.345407 | 0.045041 | não |
| 6 | 62.340700 | 0.049748 | não |
| 7 | 62.682853 | 0.292405 | não |
| 8 | 62.305608 | 0.084840 | não |
| 9 | 62.567246 | 0.176798 | não |
| 10 | 62.284609 | 0.105839 | não |

## Valores ordenados (ordem crescente)

62.284609, 62.305608, 62.340700, 62.345407, 62.361213, 62.419683, 62.477588, 62.535255, 62.567246, 62.682853

## Mediana e dispersão

- Mediana: **62.390448s**
- Mínimo: 62.284609s
- Máximo: 62.682853s
- Média: 62.432016s
- Desvio padrão (amostral): 0.130237s
- Spread (min/max): 0.6394%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 0.6394% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

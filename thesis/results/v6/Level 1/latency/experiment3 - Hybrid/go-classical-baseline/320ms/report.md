# Latency Report (hybrid, 320ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 60.7309s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 60.697887 | 0.389649 | não |
| 2 | 61.322387 | 0.234851 | não |
| 3 | 61.612968 | 0.525432 | não |
| 4 | 62.116290 | 1.028754 | não |
| 5 | 60.747807 | 0.339729 | não |
| 6 | 61.071418 | 0.016118 | não |
| 7 | 61.173747 | 0.086211 | não |
| 8 | 60.811268 | 0.276268 | não |
| 9 | 60.859840 | 0.227696 | não |
| 10 | 61.103654 | 0.016118 | não |

## Valores ordenados (ordem crescente)

60.697887, 60.747807, 60.811268, 60.859840, 61.071418, 61.103654, 61.173747, 61.322387, 61.612968, 62.116290

## Mediana e dispersão

- Mediana: **61.087536s**
- Mínimo: 60.697887s
- Máximo: 62.116290s
- Média: 61.151727s
- Desvio padrão (amostral): 0.441176s
- Spread (min/max): 2.3368%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 2.3368% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

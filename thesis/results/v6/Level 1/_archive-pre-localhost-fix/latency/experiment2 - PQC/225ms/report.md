# Latency Report (pqc, 225ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 56.8193s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 56.406632 | 0.510460 | não |
| 2 | 57.602867 | 0.685775 | não |
| 3 | 56.993292 | 0.076200 | não |
| 4 | 56.570251 | 0.346841 | não |
| 5 | 57.424923 | 0.507831 | não |
| 6 | 56.840893 | 0.076199 | não |
| 7 | 57.026483 | 0.109391 | não |
| 8 | 56.815926 | 0.101166 | não |
| 9 | 56.805441 | 0.111651 | não |
| 10 | 57.381579 | 0.464487 | não |

## Valores ordenados (ordem crescente)

56.406632, 56.570251, 56.805441, 56.815926, 56.840893, 56.993292, 57.026483, 57.381579, 57.424923, 57.602867

## Mediana e dispersão

- Mediana: **56.917092s**
- Mínimo: 56.406632s
- Máximo: 57.602867s
- Média: 56.986829s
- Desvio padrão (amostral): 0.383325s
- Spread (min/max): 2.1207%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 2.1207% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

# Latency Report (pqc, 0ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 21.1031s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 20.831286 | 0.041931 | não |
| 2 | 20.460261 | 0.329094 | não |
| 3 | 20.226651 | 0.562704 | não |
| 4 | 20.081101 | 0.708254 | não |
| 5 | 23.000162 | 2.210807 | não |
| 6 | 21.534091 | 0.744736 | não |
| 7 | 20.747424 | 0.041931 | não |
| 8 | 21.499370 | 0.710015 | não |
| 9 | 23.538313 | 2.748958 | não |
| 10 | 20.032738 | 0.756617 | não |

## Valores ordenados (ordem crescente)

20.032738, 20.081101, 20.226651, 20.460261, 20.747424, 20.831286, 21.499370, 21.534091, 23.000162, 23.538313

## Mediana e dispersão

- Mediana: **20.789355s**
- Mínimo: 20.032738s
- Máximo: 23.538313s
- Média: 21.195140s
- Desvio padrão (amostral): 1.218338s
- Spread (min/max): 17.4992%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 17.4992% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

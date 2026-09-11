# Latency Report (hybrid, 225ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 46.2357s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 45.552280 | 0.073099 | não |
| 2 | 45.365219 | 0.113962 | não |
| 3 | 45.406083 | 0.073099 | não |
| 4 | 45.313474 | 0.165708 | não |
| 5 | 45.035595 | 0.443587 | não |
| 6 | 45.360019 | 0.119163 | não |
| 7 | 46.096890 | 0.617708 | não |
| 8 | 49.284000 | 3.804818 | não |
| 9 | 49.554121 | 4.074939 | não |
| 10 | 46.389141 | 0.909959 | não |

## Valores ordenados (ordem crescente)

45.035595, 45.313474, 45.360019, 45.365219, 45.406083, 45.552280, 46.096890, 46.389141, 49.284000, 49.554121

## Mediana e dispersão

- Mediana: **45.479182s**
- Mínimo: 45.035595s
- Máximo: 49.554121s
- Média: 46.335682s
- Desvio padrão (amostral): 1.673902s
- Spread (min/max): 10.0332%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 10.0332% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

# Latency Report (pqc, 0ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 16.5170s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 10.935299 | 0.803127 | não |
| 2 | 10.127523 | 0.004649 | não |
| 3 | 10.386451 | 0.254279 | não |
| 4 | 10.110513 | 0.021659 | não |
| 5 | 9.713507 | 0.418665 | não |
| 6 | 10.143860 | 0.011688 | não |
| 7 | 10.395026 | 0.262854 | não |
| 8 | 9.961689 | 0.170483 | não |
| 9 | 10.136821 | 0.004649 | não |
| 10 | 9.974408 | 0.157764 | não |

## Valores ordenados (ordem crescente)

9.713507, 9.961689, 9.974408, 10.110513, 10.127523, 10.136821, 10.143860, 10.386451, 10.395026, 10.935299

## Mediana e dispersão

- Mediana: **10.132172s**
- Mínimo: 9.713507s
- Máximo: 10.935299s
- Média: 10.188510s
- Desvio padrão (amostral): 0.329462s
- Spread (min/max): 12.5783%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 12.5783% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

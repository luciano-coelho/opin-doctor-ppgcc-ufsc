# Latency Report (pqc, 140ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 30.3695s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 30.061058 | 0.158301 | não |
| 2 | 29.824581 | 0.078176 | não |
| 3 | 29.904789 | 0.002032 | não |
| 4 | 29.523906 | 0.378851 | não |
| 5 | 31.518051 | 1.615294 | não |
| 6 | 29.740484 | 0.162273 | não |
| 7 | 29.769108 | 0.133649 | não |
| 8 | 29.900724 | 0.002033 | não |
| 9 | 29.907957 | 0.005200 | não |
| 10 | 29.913123 | 0.010366 | não |

## Valores ordenados (ordem crescente)

29.523906, 29.740484, 29.769108, 29.824581, 29.900724, 29.904789, 29.907957, 29.913123, 30.061058, 31.518051

## Mediana e dispersão

- Mediana: **29.902757s**
- Mínimo: 29.523906s
- Máximo: 31.518051s
- Média: 30.006378s
- Desvio padrão (amostral): 0.549832s
- Spread (min/max): 6.7543%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 6.7543% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

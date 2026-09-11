# Latency Report (pqc, 140ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 43.6337s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 42.802089 | 0.470908 | não |
| 2 | 43.780329 | 0.507332 | não |
| 3 | 43.254275 | 0.018722 | não |
| 4 | 43.754069 | 0.481072 | não |
| 5 | 45.687967 | 2.414970 | não |
| 6 | 42.959617 | 0.313380 | não |
| 7 | 43.291719 | 0.018722 | não |
| 8 | 43.420750 | 0.147753 | não |
| 9 | 42.882539 | 0.390458 | não |
| 10 | 43.239981 | 0.033016 | não |

## Valores ordenados (ordem crescente)

42.802089, 42.882539, 42.959617, 43.239981, 43.254275, 43.291719, 43.420750, 43.754069, 43.780329, 45.687967

## Mediana e dispersão

- Mediana: **43.272997s**
- Mínimo: 42.802089s
- Máximo: 45.687967s
- Média: 43.507334s
- Desvio padrão (amostral): 0.834519s
- Spread (min/max): 6.7424%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 6.7424% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

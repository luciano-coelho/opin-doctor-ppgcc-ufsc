# Latency Report (pqc, 320ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 59.8349s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 60.396500 | 0.827283 | não |
| 2 | 59.207754 | 0.361463 | não |
| 3 | 59.941350 | 0.372132 | não |
| 4 | 61.389651 | 1.820434 | não |
| 5 | 59.113488 | 0.455730 | não |
| 6 | 59.518081 | 0.051136 | não |
| 7 | 59.450429 | 0.118789 | não |
| 8 | 59.620354 | 0.051136 | não |
| 9 | 60.014310 | 0.445093 | não |
| 10 | 59.368776 | 0.200442 | não |

## Valores ordenados (ordem crescente)

59.113488, 59.207754, 59.368776, 59.450429, 59.518081, 59.620354, 59.941350, 60.014310, 60.396500, 61.389651

## Mediana e dispersão

- Mediana: **59.569218s**
- Mínimo: 59.113488s
- Máximo: 61.389651s
- Média: 59.802069s
- Desvio padrão (amostral): 0.682367s
- Spread (min/max): 3.8505%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 3.8505% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

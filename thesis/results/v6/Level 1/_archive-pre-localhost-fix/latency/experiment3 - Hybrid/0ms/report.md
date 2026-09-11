# Latency Report (hybrid, 0ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 22.0721s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 23.061915 | 0.424392 | não |
| 2 | 22.468155 | 0.169367 | não |
| 3 | 22.409018 | 0.228504 | não |
| 4 | 22.858440 | 0.220918 | não |
| 5 | 22.423827 | 0.213696 | não |
| 6 | 22.684027 | 0.046505 | não |
| 7 | 23.225210 | 0.587688 | não |
| 8 | 22.915900 | 0.278378 | não |
| 9 | 22.591018 | 0.046505 | não |
| 10 | 22.466231 | 0.171291 | não |

## Valores ordenados (ordem crescente)

22.409018, 22.423827, 22.466231, 22.468155, 22.591018, 22.684027, 22.858440, 22.915900, 23.061915, 23.225210

## Mediana e dispersão

- Mediana: **22.637522s**
- Mínimo: 22.409018s
- Máximo: 23.225210s
- Média: 22.710374s
- Desvio padrão (amostral): 0.290391s
- Spread (min/max): 3.6422%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 3.6422% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

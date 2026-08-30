# Latency Report (hybrid, 0ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 15.1069s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 10.980175 | 0.250725 | não |
| 2 | 10.722479 | 0.006971 | não |
| 3 | 10.936096 | 0.206646 | não |
| 4 | 10.736420 | 0.006970 | não |
| 5 | 10.468293 | 0.261157 | não |
| 6 | 10.678557 | 0.050893 | não |
| 7 | 10.696530 | 0.032920 | não |
| 8 | 10.971033 | 0.241583 | não |
| 9 | 10.918060 | 0.188610 | não |
| 10 | 10.656708 | 0.072742 | não |

## Valores ordenados (ordem crescente)

10.468293, 10.656708, 10.678557, 10.696530, 10.722479, 10.736420, 10.918060, 10.936096, 10.971033, 10.980175

## Mediana e dispersão

- Mediana: **10.729450s**
- Mínimo: 10.468293s
- Máximo: 10.980175s
- Média: 10.776435s
- Desvio padrão (amostral): 0.168223s
- Spread (min/max): 4.8898%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 4.8898% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

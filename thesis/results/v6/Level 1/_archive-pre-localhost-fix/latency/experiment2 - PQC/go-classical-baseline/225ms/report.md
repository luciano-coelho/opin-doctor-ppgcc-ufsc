# Latency Report (pqc, 225ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 57.1038s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 57.325721 | 0.064688 | não |
| 2 | 57.087539 | 0.173494 | não |
| 3 | 57.350519 | 0.089486 | não |
| 4 | 57.196345 | 0.064688 | não |
| 5 | 57.501008 | 0.239975 | não |
| 6 | 57.364955 | 0.103922 | não |
| 7 | 56.820215 | 0.440818 | não |
| 8 | 56.980209 | 0.280824 | não |
| 9 | 57.835430 | 0.574397 | não |
| 10 | 56.908908 | 0.352125 | não |

## Valores ordenados (ordem crescente)

56.820215, 56.908908, 56.980209, 57.087539, 57.196345, 57.325721, 57.350519, 57.364955, 57.501008, 57.835430

## Mediana e dispersão

- Mediana: **57.261033s**
- Mínimo: 56.820215s
- Máximo: 57.835430s
- Média: 57.237085s
- Desvio padrão (amostral): 0.304820s
- Spread (min/max): 1.7867%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 1.7867% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

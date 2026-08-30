# Latency Report (hybrid, 225ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 51.5046s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 47.351363 | 0.003925 | não |
| 2 | 47.343514 | 0.003924 | não |
| 3 | 47.189498 | 0.157940 | não |
| 4 | 47.277263 | 0.070175 | não |
| 5 | 47.258175 | 0.089263 | não |
| 6 | 47.565514 | 0.218076 | não |
| 7 | 47.222602 | 0.124836 | não |
| 8 | 49.467852 | 2.120414 | não |
| 9 | 52.148634 | 4.801196 | não |
| 10 | 48.820351 | 1.472913 | não |

## Valores ordenados (ordem crescente)

47.189498, 47.222602, 47.258175, 47.277263, 47.343514, 47.351363, 47.565514, 48.820351, 49.467852, 52.148634

## Mediana e dispersão

- Mediana: **47.347438s**
- Mínimo: 47.189498s
- Máximo: 52.148634s
- Média: 48.164477s
- Desvio padrão (amostral): 1.603559s
- Spread (min/max): 10.5090%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 10.5090% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

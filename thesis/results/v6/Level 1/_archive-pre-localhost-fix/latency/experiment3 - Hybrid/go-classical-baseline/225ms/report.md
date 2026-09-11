# Latency Report (hybrid, 225ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 59.7019s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 59.274081 | 1.223306 | não |
| 2 | 57.452146 | 0.598629 | não |
| 3 | 58.071376 | 0.020601 | não |
| 4 | 57.756532 | 0.294243 | não |
| 5 | 57.843962 | 0.206813 | não |
| 6 | 57.825201 | 0.225574 | não |
| 7 | 64.072961 | 6.022186 | não |
| 8 | 60.723811 | 2.673036 | não |
| 9 | 58.030174 | 0.020601 | não |
| 10 | 58.381528 | 0.330753 | não |

## Valores ordenados (ordem crescente)

57.452146, 57.756532, 57.825201, 57.843962, 58.030174, 58.071376, 58.381528, 59.274081, 60.723811, 64.072961

## Mediana e dispersão

- Mediana: **58.050775s**
- Mínimo: 57.452146s
- Máximo: 64.072961s
- Média: 58.943177s
- Desvio padrão (amostral): 2.043780s
- Spread (min/max): 11.5241%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 11.5241% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

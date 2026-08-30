# Latency Report (hybrid, 320ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 64.9400s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 64.412850 | 0.075880 | não |
| 2 | 64.117095 | 0.219875 | não |
| 3 | 64.167196 | 0.169774 | não |
| 4 | 64.439979 | 0.103009 | não |
| 5 | 64.221940 | 0.115030 | não |
| 6 | 64.180901 | 0.156069 | não |
| 7 | 64.331419 | 0.005551 | não |
| 8 | 64.342521 | 0.005551 | não |
| 9 | 64.494370 | 0.157400 | não |
| 10 | 64.342592 | 0.005622 | não |

## Valores ordenados (ordem crescente)

64.117095, 64.167196, 64.180901, 64.221940, 64.331419, 64.342521, 64.342592, 64.412850, 64.439979, 64.494370

## Mediana e dispersão

- Mediana: **64.336970s**
- Mínimo: 64.117095s
- Máximo: 64.494370s
- Média: 64.305086s
- Desvio padrão (amostral): 0.127292s
- Spread (min/max): 0.5884%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 0.5884% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

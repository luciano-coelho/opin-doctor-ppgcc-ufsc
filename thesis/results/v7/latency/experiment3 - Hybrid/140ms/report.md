# Latency Report (hybrid, 140ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 32.5527s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 31.529365 | 0.828824 | não |
| 2 | 32.044034 | 0.314155 | não |
| 3 | 33.055423 | 0.697234 | não |
| 4 | 32.024554 | 0.333635 | não |
| 5 | 34.167672 | 1.809483 | não |
| 6 | 32.273982 | 0.084207 | não |
| 7 | 32.442397 | 0.084208 | não |
| 8 | 32.271902 | 0.086287 | não |
| 9 | 32.507940 | 0.149751 | não |
| 10 | 32.513480 | 0.155291 | não |

## Valores ordenados (ordem crescente)

31.529365, 32.024554, 32.044034, 32.271902, 32.273982, 32.442397, 32.507940, 32.513480, 33.055423, 34.167672

## Mediana e dispersão

- Mediana: **32.358189s**
- Mínimo: 31.529365s
- Máximo: 34.167672s
- Média: 32.483075s
- Desvio padrão (amostral): 0.712548s
- Spread (min/max): 8.3678%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 8.3678% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

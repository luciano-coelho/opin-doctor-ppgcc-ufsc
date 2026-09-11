# Latency Report (hybrid, 0ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 22.3038s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 23.207323 | 0.501164 | não |
| 2 | 23.106447 | 0.400288 | não |
| 3 | 23.135285 | 0.429126 | não |
| 4 | 22.388420 | 0.317739 | não |
| 5 | 22.794534 | 0.088375 | não |
| 6 | 22.077656 | 0.628502 | não |
| 7 | 22.320260 | 0.385898 | não |
| 8 | 22.973064 | 0.266906 | não |
| 9 | 22.617783 | 0.088376 | não |
| 10 | 22.002880 | 0.703278 | não |

## Valores ordenados (ordem crescente)

22.002880, 22.077656, 22.320260, 22.388420, 22.617783, 22.794534, 22.973064, 23.106447, 23.135285, 23.207323

## Mediana e dispersão

- Mediana: **22.706159s**
- Mínimo: 22.002880s
- Máximo: 23.207323s
- Média: 22.662365s
- Desvio padrão (amostral): 0.447551s
- Spread (min/max): 5.4740%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 5.4740% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

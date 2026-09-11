# Latency Report (hybrid, 320ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 61.9064s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 62.011363 | 0.823082 | não |
| 2 | 60.868295 | 0.319986 | não |
| 3 | 61.489656 | 0.301375 | não |
| 4 | 61.569276 | 0.380995 | não |
| 5 | 61.038510 | 0.149771 | não |
| 6 | 62.161157 | 0.972876 | não |
| 7 | 60.569355 | 0.618926 | não |
| 8 | 60.912342 | 0.275939 | não |
| 9 | 61.338052 | 0.149771 | não |
| 10 | 60.791588 | 0.396693 | não |

## Valores ordenados (ordem crescente)

60.569355, 60.791588, 60.868295, 60.912342, 61.038510, 61.338052, 61.489656, 61.569276, 62.011363, 62.161157

## Mediana e dispersão

- Mediana: **61.188281s**
- Mínimo: 60.569355s
- Máximo: 62.161157s
- Média: 61.274959s
- Desvio padrão (amostral): 0.532148s
- Spread (min/max): 2.6281%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 2.6281% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

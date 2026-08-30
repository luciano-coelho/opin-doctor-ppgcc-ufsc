# Latency Report (classic, 320ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 58.0027s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 57.519801 | 0.040372 | não |
| 2 | 57.554663 | 0.005510 | não |
| 3 | 57.590385 | 0.030212 | não |
| 4 | 57.593947 | 0.033774 | não |
| 5 | 57.565684 | 0.005510 | não |
| 6 | 57.479734 | 0.080439 | não |
| 7 | 57.495389 | 0.064784 | não |
| 8 | 57.639658 | 0.079484 | não |
| 9 | 57.668976 | 0.108803 | não |
| 10 | 57.535700 | 0.024473 | não |

## Valores ordenados (ordem crescente)

57.479734, 57.495389, 57.519801, 57.535700, 57.554663, 57.565684, 57.590385, 57.593947, 57.639658, 57.668976

## Mediana e dispersão

- Mediana: **57.560173s**
- Mínimo: 57.479734s
- Máximo: 57.668976s
- Média: 57.564394s
- Desvio padrão (amostral): 0.060542s
- Spread (min/max): 0.3292%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 0.3292% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

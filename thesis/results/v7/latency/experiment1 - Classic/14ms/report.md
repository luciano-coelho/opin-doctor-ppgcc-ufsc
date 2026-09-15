# Latency Report (classic, 14ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 4.7042s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 4.718007 | 0.024795 | não |
| 2 | 4.846345 | 0.153133 | não |
| 3 | 4.670076 | 0.023136 | não |
| 4 | 4.726420 | 0.033208 | não |
| 5 | 4.558583 | 0.134629 | não |
| 6 | 4.665885 | 0.027327 | não |
| 7 | 4.499482 | 0.193730 | não |
| 8 | 4.651421 | 0.041791 | não |
| 9 | 4.716348 | 0.023136 | não |
| 10 | 4.827919 | 0.134707 | não |

## Valores ordenados (ordem crescente)

4.499482, 4.558583, 4.651421, 4.665885, 4.670076, 4.716348, 4.718007, 4.726420, 4.827919, 4.846345

## Mediana e dispersão

- Mediana: **4.693212s**
- Mínimo: 4.499482s
- Máximo: 4.846345s
- Média: 4.688049s
- Desvio padrão (amostral): 0.106597s
- Spread (min/max): 7.7090%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 7.7090% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

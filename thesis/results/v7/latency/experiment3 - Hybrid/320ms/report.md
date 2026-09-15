# Latency Report (hybrid, 320ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 62.0933s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 61.081127 | 0.356440 | não |
| 2 | 61.170159 | 0.267408 | não |
| 3 | 61.932612 | 0.495045 | não |
| 4 | 60.950068 | 0.487499 | não |
| 5 | 61.153109 | 0.284458 | não |
| 6 | 63.469621 | 2.032054 | não |
| 7 | 63.130752 | 1.693185 | não |
| 8 | 61.490605 | 0.053038 | não |
| 9 | 61.500332 | 0.062765 | não |
| 10 | 61.384528 | 0.053038 | não |

## Valores ordenados (ordem crescente)

60.950068, 61.081127, 61.153109, 61.170159, 61.384528, 61.490605, 61.500332, 61.932612, 63.130752, 63.469621

## Mediana e dispersão

- Mediana: **61.437567s**
- Mínimo: 60.950068s
- Máximo: 63.469621s
- Média: 61.726291s
- Desvio padrão (amostral): 0.877766s
- Spread (min/max): 4.1338%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 4.1338% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

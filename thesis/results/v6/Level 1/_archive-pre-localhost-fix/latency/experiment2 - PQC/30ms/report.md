# Latency Report (pqc, 30ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 25.4518s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 25.287328 | 0.310204 | não |
| 2 | 25.431730 | 0.165802 | não |
| 3 | 25.646320 | 0.048788 | não |
| 4 | 25.454759 | 0.142773 | não |
| 5 | 25.767004 | 0.169472 | não |
| 6 | 25.609926 | 0.012394 | não |
| 7 | 25.998576 | 0.401044 | não |
| 8 | 26.539903 | 0.942371 | não |
| 9 | 25.585137 | 0.012395 | não |
| 10 | 25.389054 | 0.208478 | não |

## Valores ordenados (ordem crescente)

25.287328, 25.389054, 25.431730, 25.454759, 25.585137, 25.609926, 25.646320, 25.767004, 25.998576, 26.539903

## Mediana e dispersão

- Mediana: **25.597532s**
- Mínimo: 25.287328s
- Máximo: 26.539903s
- Média: 25.670974s
- Desvio padrão (amostral): 0.367262s
- Spread (min/max): 4.9534%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 4.9534% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

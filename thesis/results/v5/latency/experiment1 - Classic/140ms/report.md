# Latency Report (classic, 140ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 27.3279s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 27.083944 | 0.280380 | não |
| 2 | 26.716286 | 0.087278 | não |
| 3 | 26.771524 | 0.032040 | não |
| 4 | 26.846693 | 0.043129 | não |
| 5 | 26.788036 | 0.015528 | não |
| 6 | 26.900888 | 0.097324 | não |
| 7 | 26.687322 | 0.116242 | não |
| 8 | 26.835315 | 0.031751 | não |
| 9 | 26.819091 | 0.015527 | não |
| 10 | 26.620743 | 0.182821 | não |

## Valores ordenados (ordem crescente)

26.620743, 26.687322, 26.716286, 26.771524, 26.788036, 26.819091, 26.835315, 26.846693, 26.900888, 27.083944

## Mediana e dispersão

- Mediana: **26.803564s**
- Mínimo: 26.620743s
- Máximo: 27.083944s
- Média: 26.806984s
- Desvio padrão (amostral): 0.127758s
- Spread (min/max): 1.7400%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 1.7400% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

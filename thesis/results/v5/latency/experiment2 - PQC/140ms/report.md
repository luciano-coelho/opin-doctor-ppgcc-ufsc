# Latency Report (pqc, 140ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 32.8760s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 31.636078 | 0.050569 | não |
| 2 | 35.964445 | 4.378936 | não |
| 3 | 37.094958 | 5.509449 | não |
| 4 | 36.497585 | 4.912076 | não |
| 5 | 31.534939 | 0.050570 | não |
| 6 | 32.411704 | 0.826195 | não |
| 7 | 31.001001 | 0.584508 | não |
| 8 | 31.506807 | 0.078702 | não |
| 9 | 31.247380 | 0.338129 | não |
| 10 | 31.480250 | 0.105259 | não |

## Valores ordenados (ordem crescente)

31.001001, 31.247380, 31.480250, 31.506807, 31.534939, 31.636078, 32.411704, 35.964445, 36.497585, 37.094958

## Mediana e dispersão

- Mediana: **31.585509s**
- Mínimo: 31.001001s
- Máximo: 37.094958s
- Média: 33.037515s
- Desvio padrão (amostral): 2.443480s
- Spread (min/max): 19.6573%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 19.6573% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

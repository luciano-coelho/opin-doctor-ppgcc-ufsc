# Latency Report (hybrid, 30ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 15.1968s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 14.434301 | 0.374535 | não |
| 2 | 15.205234 | 0.396399 | não |
| 3 | 14.041250 | 0.767586 | não |
| 4 | 15.328211 | 0.519375 | não |
| 5 | 14.570958 | 0.237878 | não |
| 6 | 15.046713 | 0.237877 | não |
| 7 | 14.509196 | 0.299640 | não |
| 8 | 13.998518 | 0.810318 | não |
| 9 | 15.673382 | 0.864546 | não |
| 10 | 15.244746 | 0.435910 | não |

## Valores ordenados (ordem crescente)

13.998518, 14.041250, 14.434301, 14.509196, 14.570958, 15.046713, 15.205234, 15.244746, 15.328211, 15.673382

## Mediana e dispersão

- Mediana: **14.808836s**
- Mínimo: 13.998518s
- Máximo: 15.673382s
- Média: 14.805251s
- Desvio padrão (amostral): 0.572834s
- Spread (min/max): 11.9646%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 11.9646% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

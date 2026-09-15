# Latency Report (pqc, 225ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 44.0002s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 43.683387 | 0.644182 | não |
| 2 | 44.401500 | 0.073931 | não |
| 3 | 43.341162 | 0.986407 | não |
| 4 | 43.641516 | 0.686053 | não |
| 5 | 44.100072 | 0.227497 | não |
| 6 | 44.253639 | 0.073930 | não |
| 7 | 44.834493 | 0.506924 | não |
| 8 | 44.469912 | 0.142343 | não |
| 9 | 44.909329 | 0.581760 | não |
| 10 | 46.098282 | 1.770713 | não |

## Valores ordenados (ordem crescente)

43.341162, 43.641516, 43.683387, 44.100072, 44.253639, 44.401500, 44.469912, 44.834493, 44.909329, 46.098282

## Mediana e dispersão

- Mediana: **44.327569s**
- Mínimo: 43.341162s
- Máximo: 46.098282s
- Média: 44.373329s
- Desvio padrão (amostral): 0.792429s
- Spread (min/max): 6.3614%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 6.3614% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

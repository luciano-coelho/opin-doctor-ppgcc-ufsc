# Latency Report (hybrid, 30ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 15.4629s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 14.690800 | 0.023290 | não |
| 2 | 14.280953 | 0.386557 | não |
| 3 | 14.246373 | 0.421137 | não |
| 4 | 14.285542 | 0.381968 | não |
| 5 | 14.415667 | 0.251843 | não |
| 6 | 14.778529 | 0.111019 | não |
| 7 | 15.023455 | 0.355945 | não |
| 8 | 16.145301 | 1.477791 | não |
| 9 | 15.174500 | 0.506990 | não |
| 10 | 14.644221 | 0.023289 | não |

## Valores ordenados (ordem crescente)

14.246373, 14.280953, 14.285542, 14.415667, 14.644221, 14.690800, 14.778529, 15.023455, 15.174500, 16.145301

## Mediana e dispersão

- Mediana: **14.667510s**
- Mínimo: 14.246373s
- Máximo: 16.145301s
- Média: 14.768534s
- Desvio padrão (amostral): 0.578798s
- Spread (min/max): 13.3292%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 13.3292% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

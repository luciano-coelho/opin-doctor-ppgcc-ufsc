# Latency Report (pqc, 320ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 72.5500s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 72.670343 | 0.181931 | não |
| 2 | 72.451296 | 0.037116 | não |
| 3 | 72.685675 | 0.197263 | não |
| 4 | 72.319192 | 0.169220 | não |
| 5 | 72.821961 | 0.333549 | não |
| 6 | 72.525528 | 0.037116 | não |
| 7 | 72.751161 | 0.262749 | não |
| 8 | 72.138031 | 0.350381 | não |
| 9 | 72.432466 | 0.055946 | não |
| 10 | 71.969865 | 0.518547 | não |

## Valores ordenados (ordem crescente)

71.969865, 72.138031, 72.319192, 72.432466, 72.451296, 72.525528, 72.670343, 72.685675, 72.751161, 72.821961

## Mediana e dispersão

- Mediana: **72.488412s**
- Mínimo: 71.969865s
- Máximo: 72.821961s
- Média: 72.476552s
- Desvio padrão (amostral): 0.274282s
- Spread (min/max): 1.1840%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 1.1840% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

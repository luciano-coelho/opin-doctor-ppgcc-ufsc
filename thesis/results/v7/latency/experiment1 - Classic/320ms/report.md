# Latency Report (classic, 320ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 54.0186s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 53.720716 | 0.051141 | não |
| 2 | 53.636480 | 0.033095 | não |
| 3 | 53.661080 | 0.008495 | não |
| 4 | 53.691098 | 0.021523 | não |
| 5 | 53.673268 | 0.003693 | não |
| 6 | 53.692116 | 0.022541 | não |
| 7 | 53.611204 | 0.058371 | não |
| 8 | 53.606035 | 0.063540 | não |
| 9 | 53.677687 | 0.008112 | não |
| 10 | 53.665882 | 0.003693 | não |

## Valores ordenados (ordem crescente)

53.606035, 53.611204, 53.636480, 53.661080, 53.665882, 53.673268, 53.677687, 53.691098, 53.692116, 53.720716

## Mediana e dispersão

- Mediana: **53.669575s**
- Mínimo: 53.606035s
- Máximo: 53.720716s
- Média: 53.663557s
- Desvio padrão (amostral): 0.036408s
- Spread (min/max): 0.2139%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 0.2139% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

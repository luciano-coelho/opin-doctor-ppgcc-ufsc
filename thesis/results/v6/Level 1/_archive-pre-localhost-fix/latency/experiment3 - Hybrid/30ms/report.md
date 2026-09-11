# Latency Report (hybrid, 30ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 26.9363s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 26.971960 | 0.011273 | não |
| 2 | 26.653737 | 0.306950 | não |
| 3 | 27.091105 | 0.130418 | não |
| 4 | 27.295045 | 0.334357 | não |
| 5 | 26.969052 | 0.008365 | não |
| 6 | 28.605145 | 1.644458 | não |
| 7 | 26.691440 | 0.269247 | não |
| 8 | 26.826264 | 0.134424 | não |
| 9 | 26.911266 | 0.049421 | não |
| 10 | 26.952323 | 0.008364 | não |

## Valores ordenados (ordem crescente)

26.653737, 26.691440, 26.826264, 26.911266, 26.952323, 26.969052, 26.971960, 27.091105, 27.295045, 28.605145

## Mediana e dispersão

- Mediana: **26.960687s**
- Mínimo: 26.653737s
- Máximo: 28.605145s
- Média: 27.096734s
- Desvio padrão (amostral): 0.561293s
- Spread (min/max): 7.3213%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 7.3213% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

# Latency Report (classic, 0ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 3.9466s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 4.216863 | 0.398281 | não |
| 2 | 3.612926 | 0.205656 | não |
| 3 | 3.872877 | 0.054295 | não |
| 4 | 4.393070 | 0.574488 | não |
| 5 | 3.395827 | 0.422755 | não |
| 6 | 3.249405 | 0.569177 | não |
| 7 | 3.748383 | 0.070199 | não |
| 8 | 4.086336 | 0.267754 | não |
| 9 | 3.764288 | 0.054294 | não |
| 10 | 4.117052 | 0.298470 | não |

## Valores ordenados (ordem crescente)

3.249405, 3.395827, 3.612926, 3.748383, 3.764288, 3.872877, 4.086336, 4.117052, 4.216863, 4.393070

## Mediana e dispersão

- Mediana: **3.818582s**
- Mínimo: 3.249405s
- Máximo: 4.393070s
- Média: 3.845703s
- Desvio padrão (amostral): 0.364827s
- Spread (min/max): 35.1961%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 35.1961% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**

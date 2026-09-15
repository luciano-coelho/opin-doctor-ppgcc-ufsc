# Latency Report (classic, 0ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 2.8810s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 3.236346 | 0.345087 | não |
| 2 | 2.928489 | 0.037230 | não |
| 3 | 3.034042 | 0.142783 | não |
| 4 | 2.647786 | 0.243473 | não |
| 5 | 2.848475 | 0.042784 | não |
| 6 | 2.854028 | 0.037231 | não |
| 7 | 2.573236 | 0.318023 | não |
| 8 | 3.112332 | 0.221073 | não |
| 9 | 3.119234 | 0.227975 | não |
| 10 | 2.677057 | 0.214202 | não |

## Valores ordenados (ordem crescente)

2.573236, 2.647786, 2.677057, 2.848475, 2.854028, 2.928489, 3.034042, 3.112332, 3.119234, 3.236346

## Mediana e dispersão

- Mediana: **2.891259s**
- Mínimo: 2.573236s
- Máximo: 3.236346s
- Média: 2.903103s
- Desvio padrão (amostral): 0.223562s
- Spread (min/max): 25.7695%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 25.7695% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**

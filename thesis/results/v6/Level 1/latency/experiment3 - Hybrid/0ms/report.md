# Latency Report (hybrid, 0ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 10.5654s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 11.212198 | 0.563237 | não |
| 2 | 10.873980 | 0.225019 | não |
| 3 | 10.192777 | 0.456184 | não |
| 4 | 11.335964 | 0.687003 | não |
| 5 | 10.342423 | 0.306538 | não |
| 6 | 10.675666 | 0.026705 | não |
| 7 | 9.982603 | 0.666358 | não |
| 8 | 10.064541 | 0.584420 | não |
| 9 | 10.639190 | 0.009771 | não |
| 10 | 10.658733 | 0.009772 | não |

## Valores ordenados (ordem crescente)

9.982603, 10.064541, 10.192777, 10.342423, 10.639190, 10.658733, 10.675666, 10.873980, 11.212198, 11.335964

## Mediana e dispersão

- Mediana: **10.648961s**
- Mínimo: 9.982603s
- Máximo: 11.335964s
- Média: 10.597808s
- Desvio padrão (amostral): 0.459738s
- Spread (min/max): 13.5572%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 13.5572% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

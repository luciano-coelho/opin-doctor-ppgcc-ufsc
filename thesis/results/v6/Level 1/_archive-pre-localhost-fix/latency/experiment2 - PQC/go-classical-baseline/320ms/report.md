# Latency Report (pqc, 320ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 73.1033s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 72.305925 | 0.032265 | não |
| 2 | 72.506047 | 0.232387 | não |
| 3 | 72.333321 | 0.059661 | não |
| 4 | 72.188039 | 0.085621 | não |
| 5 | 72.241394 | 0.032266 | não |
| 6 | 72.874450 | 0.600790 | não |
| 7 | 72.155033 | 0.118627 | não |
| 8 | 72.175355 | 0.098305 | não |
| 9 | 71.989418 | 0.284242 | não |
| 10 | 72.440525 | 0.166865 | não |

## Valores ordenados (ordem crescente)

71.989418, 72.155033, 72.175355, 72.188039, 72.241394, 72.305925, 72.333321, 72.440525, 72.506047, 72.874450

## Mediana e dispersão

- Mediana: **72.273660s**
- Mínimo: 71.989418s
- Máximo: 72.874450s
- Média: 72.320951s
- Desvio padrão (amostral): 0.244480s
- Spread (min/max): 1.2294%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 1.2294% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

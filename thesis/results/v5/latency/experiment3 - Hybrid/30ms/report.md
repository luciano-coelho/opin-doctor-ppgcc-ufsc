# Latency Report (hybrid, 30ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 15.2832s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 14.319473 | 0.328031 | não |
| 2 | 14.653534 | 0.006030 | não |
| 3 | 14.197446 | 0.450059 | não |
| 4 | 15.167127 | 0.519623 | não |
| 5 | 14.520719 | 0.126786 | não |
| 6 | 14.641475 | 0.006030 | não |
| 7 | 14.497666 | 0.149838 | não |
| 8 | 14.848237 | 0.200732 | não |
| 9 | 15.032821 | 0.385317 | não |
| 10 | 14.659117 | 0.011613 | não |

## Valores ordenados (ordem crescente)

14.197446, 14.319473, 14.497666, 14.520719, 14.641475, 14.653534, 14.659117, 14.848237, 15.032821, 15.167127

## Mediana e dispersão

- Mediana: **14.647505s**
- Mínimo: 14.197446s
- Máximo: 15.167127s
- Média: 14.653761s
- Desvio padrão (amostral): 0.299494s
- Spread (min/max): 6.8300%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 6.8300% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

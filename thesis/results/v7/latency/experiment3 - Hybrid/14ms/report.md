# Latency Report (hybrid, 14ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 12.5383s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 12.034517 | 0.240683 | não |
| 2 | 12.266025 | 0.009174 | não |
| 3 | 12.213491 | 0.061708 | não |
| 4 | 13.788387 | 1.513188 | não |
| 5 | 12.592585 | 0.317386 | não |
| 6 | 12.014760 | 0.260439 | não |
| 7 | 12.032244 | 0.242955 | não |
| 8 | 12.324459 | 0.049259 | não |
| 9 | 14.404796 | 2.129596 | não |
| 10 | 12.284374 | 0.009175 | não |

## Valores ordenados (ordem crescente)

12.014760, 12.032244, 12.034517, 12.213491, 12.266025, 12.284374, 12.324459, 12.592585, 13.788387, 14.404796

## Mediana e dispersão

- Mediana: **12.275199s**
- Mínimo: 12.014760s
- Máximo: 14.404796s
- Média: 12.595564s
- Desvio padrão (amostral): 0.822632s
- Spread (min/max): 19.8925%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 19.8925% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

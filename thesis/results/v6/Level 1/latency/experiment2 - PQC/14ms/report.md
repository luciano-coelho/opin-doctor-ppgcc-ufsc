# Latency Report (pqc, 14ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 11.3557s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 12.126849 | 0.052875 | não |
| 2 | 11.986798 | 0.087176 | não |
| 3 | 12.199387 | 0.125413 | não |
| 4 | 11.771516 | 0.302458 | não |
| 5 | 11.923957 | 0.150017 | não |
| 6 | 12.846994 | 0.773020 | não |
| 7 | 12.697939 | 0.623965 | não |
| 8 | 11.134521 | 0.939453 | não |
| 9 | 12.021099 | 0.052875 | não |
| 10 | 12.737293 | 0.663319 | não |

## Valores ordenados (ordem crescente)

11.134521, 11.771516, 11.923957, 11.986798, 12.021099, 12.126849, 12.199387, 12.697939, 12.737293, 12.846994

## Mediana e dispersão

- Mediana: **12.073974s**
- Mínimo: 11.134521s
- Máximo: 12.846994s
- Média: 12.144635s
- Desvio padrão (amostral): 0.516659s
- Spread (min/max): 15.3799%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 15.3799% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

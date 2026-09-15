# Latency Report (pqc, 14ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 10.7149s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 11.273439 | 0.120518 | não |
| 2 | 12.380511 | 1.227590 | não |
| 3 | 10.936508 | 0.216413 | não |
| 4 | 11.269066 | 0.116145 | não |
| 5 | 11.906190 | 0.753269 | não |
| 6 | 11.741589 | 0.588668 | não |
| 7 | 11.036776 | 0.116145 | não |
| 8 | 10.663501 | 0.489420 | não |
| 9 | 10.600567 | 0.552354 | não |
| 10 | 10.959902 | 0.193019 | não |

## Valores ordenados (ordem crescente)

10.600567, 10.663501, 10.936508, 10.959902, 11.036776, 11.269066, 11.273439, 11.741589, 11.906190, 12.380511

## Mediana e dispersão

- Mediana: **11.152921s**
- Mínimo: 10.600567s
- Máximo: 12.380511s
- Média: 11.276805s
- Desvio padrão (amostral): 0.571321s
- Spread (min/max): 16.7910%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 16.7910% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

# Latency Report (pqc, 14ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 23.5025s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 22.998304 | 0.047003 | não |
| 2 | 23.304314 | 0.259007 | não |
| 3 | 22.914466 | 0.130841 | não |
| 4 | 22.680890 | 0.364417 | não |
| 5 | 23.041690 | 0.003618 | não |
| 6 | 23.202420 | 0.157113 | não |
| 7 | 23.011250 | 0.034057 | não |
| 8 | 23.048925 | 0.003618 | não |
| 9 | 23.347561 | 0.302253 | não |
| 10 | 23.641152 | 0.595845 | não |

## Valores ordenados (ordem crescente)

22.680890, 22.914466, 22.998304, 23.011250, 23.041690, 23.048925, 23.202420, 23.304314, 23.347561, 23.641152

## Mediana e dispersão

- Mediana: **23.045307s**
- Mínimo: 22.680890s
- Máximo: 23.641152s
- Média: 23.119097s
- Desvio padrão (amostral): 0.266046s
- Spread (min/max): 4.2338%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 4.2338% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

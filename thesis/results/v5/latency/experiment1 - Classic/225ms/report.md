# Latency Report (classic, 225ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 41.4745s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 40.745265 | 0.480960 | não |
| 2 | 41.237666 | 0.011441 | não |
| 3 | 41.237366 | 0.011141 | não |
| 4 | 41.220600 | 0.005625 | não |
| 5 | 41.231850 | 0.005625 | não |
| 6 | 41.323800 | 0.097575 | não |
| 7 | 41.177335 | 0.048890 | não |
| 8 | 41.219568 | 0.006657 | não |
| 9 | 41.241671 | 0.015446 | não |
| 10 | 41.195991 | 0.030234 | não |

## Valores ordenados (ordem crescente)

40.745265, 41.177335, 41.195991, 41.219568, 41.220600, 41.231850, 41.237366, 41.237666, 41.241671, 41.323800

## Mediana e dispersão

- Mediana: **41.226225s**
- Mínimo: 40.745265s
- Máximo: 41.323800s
- Média: 41.183111s
- Desvio padrão (amostral): 0.158521s
- Spread (min/max): 1.4199%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 1.4199% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

# Latency Report (pqc, 0ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 9.9305s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 9.534794 | 0.051601 | não |
| 2 | 11.134470 | 1.548075 | não |
| 3 | 10.133467 | 0.547072 | não |
| 4 | 9.737889 | 0.151494 | não |
| 5 | 9.847844 | 0.261449 | não |
| 6 | 9.576845 | 0.009550 | não |
| 7 | 9.503090 | 0.083305 | não |
| 8 | 9.595944 | 0.009549 | não |
| 9 | 9.541022 | 0.045373 | não |
| 10 | 8.920976 | 0.665419 | não |

## Valores ordenados (ordem crescente)

8.920976, 9.503090, 9.534794, 9.541022, 9.576845, 9.595944, 9.737889, 9.847844, 10.133467, 11.134470

## Mediana e dispersão

- Mediana: **9.586395s**
- Mínimo: 8.920976s
- Máximo: 11.134470s
- Média: 9.752634s
- Desvio padrão (amostral): 0.574011s
- Spread (min/max): 24.8122%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 24.8122% entre as 10 execuções. **Spread elevado -- investigar antes de aceitar este cenário como concluído.**

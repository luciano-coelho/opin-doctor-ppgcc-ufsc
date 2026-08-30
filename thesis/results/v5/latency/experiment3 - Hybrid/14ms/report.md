# Latency Report (hybrid, 14ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 12.4672s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 11.883657 | 0.381726 | não |
| 2 | 12.011016 | 0.254367 | não |
| 3 | 12.714001 | 0.448618 | não |
| 4 | 12.218501 | 0.046882 | não |
| 5 | 12.241216 | 0.024167 | não |
| 6 | 12.034725 | 0.230658 | não |
| 7 | 12.426858 | 0.161475 | não |
| 8 | 12.289550 | 0.024167 | não |
| 9 | 13.234040 | 0.968657 | não |
| 10 | 12.567041 | 0.301658 | não |

## Valores ordenados (ordem crescente)

11.883657, 12.011016, 12.034725, 12.218501, 12.241216, 12.289550, 12.426858, 12.567041, 12.714001, 13.234040

## Mediana e dispersão

- Mediana: **12.265383s**
- Mínimo: 11.883657s
- Máximo: 13.234040s
- Média: 12.362061s
- Desvio padrão (amostral): 0.398629s
- Spread (min/max): 11.3634%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 11.3634% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

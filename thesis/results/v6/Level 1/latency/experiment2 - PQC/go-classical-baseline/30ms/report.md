# Latency Report (pqc, 30ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 13.1593s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 13.502732 | 0.231002 | não |
| 2 | 13.205336 | 0.066394 | não |
| 3 | 12.996413 | 0.275317 | não |
| 4 | 12.804465 | 0.467265 | não |
| 5 | 12.818388 | 0.453342 | não |
| 6 | 13.338124 | 0.066394 | não |
| 7 | 14.129283 | 0.857553 | não |
| 8 | 13.202510 | 0.069220 | não |
| 9 | 13.338709 | 0.066979 | não |
| 10 | 13.722975 | 0.451245 | não |

## Valores ordenados (ordem crescente)

12.804465, 12.818388, 12.996413, 13.202510, 13.205336, 13.338124, 13.338709, 13.502732, 13.722975, 14.129283

## Mediana e dispersão

- Mediana: **13.271730s**
- Mínimo: 12.804465s
- Máximo: 14.129283s
- Média: 13.305893s
- Desvio padrão (amostral): 0.408038s
- Spread (min/max): 10.3465%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 10.3465% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

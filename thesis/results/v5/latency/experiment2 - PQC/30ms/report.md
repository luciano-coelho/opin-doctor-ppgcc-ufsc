# Latency Report (pqc, 30ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 14.4751s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 14.270914 | 0.540954 | não |
| 2 | 13.723415 | 0.006545 | não |
| 3 | 13.736504 | 0.006545 | não |
| 4 | 13.587146 | 0.142813 | não |
| 5 | 13.617349 | 0.112610 | não |
| 6 | 13.516274 | 0.213686 | não |
| 7 | 14.034385 | 0.304426 | não |
| 8 | 13.584763 | 0.145196 | não |
| 9 | 13.831957 | 0.101997 | não |
| 10 | 14.582710 | 0.852751 | não |

## Valores ordenados (ordem crescente)

13.516274, 13.584763, 13.587146, 13.617349, 13.723415, 13.736504, 13.831957, 14.034385, 14.270914, 14.582710

## Mediana e dispersão

- Mediana: **13.729959s**
- Mínimo: 13.516274s
- Máximo: 14.582710s
- Média: 13.848542s
- Desvio padrão (amostral): 0.346760s
- Spread (min/max): 7.8900%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 7.8900% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

# Latency Report (hybrid, 225ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **225ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 51.3241s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 47.559651 | 0.394265 | não |
| 2 | 48.438223 | 1.272837 | não |
| 3 | 46.999373 | 0.166013 | não |
| 4 | 46.234739 | 0.930647 | não |
| 5 | 48.540428 | 1.375042 | não |
| 6 | 47.331400 | 0.166014 | não |
| 7 | 46.956645 | 0.208741 | não |
| 8 | 47.599376 | 0.433990 | não |
| 9 | 46.102183 | 1.063204 | não |
| 10 | 46.111947 | 1.053439 | não |

## Valores ordenados (ordem crescente)

46.102183, 46.111947, 46.234739, 46.956645, 46.999373, 47.331400, 47.559651, 47.599376, 48.438223, 48.540428

## Mediana e dispersão

- Mediana: **47.165386s**
- Mínimo: 46.102183s
- Máximo: 48.540428s
- Média: 47.187396s
- Desvio padrão (amostral): 0.885358s
- Spread (min/max): 5.2888%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 5.2888% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

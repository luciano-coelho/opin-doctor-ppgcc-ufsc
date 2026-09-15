# Latency Report (hybrid, 30ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 14.8292s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 14.461954 | 0.030264 | não |
| 2 | 14.229589 | 0.262629 | não |
| 3 | 14.526915 | 0.034697 | não |
| 4 | 14.265968 | 0.226250 | não |
| 5 | 14.662406 | 0.170188 | não |
| 6 | 14.930001 | 0.437783 | não |
| 7 | 14.304280 | 0.187938 | não |
| 8 | 14.522483 | 0.030264 | não |
| 9 | 14.207280 | 0.284938 | não |
| 10 | 15.810934 | 1.318715 | não |

## Valores ordenados (ordem crescente)

14.207280, 14.229589, 14.265968, 14.304280, 14.461954, 14.522483, 14.526915, 14.662406, 14.930001, 15.810934

## Mediana e dispersão

- Mediana: **14.492218s**
- Mínimo: 14.207280s
- Máximo: 15.810934s
- Média: 14.592181s
- Desvio padrão (amostral): 0.482978s
- Spread (min/max): 11.2876%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 11.2876% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

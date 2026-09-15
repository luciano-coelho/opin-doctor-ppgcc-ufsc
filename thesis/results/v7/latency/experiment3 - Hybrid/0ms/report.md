# Latency Report (hybrid, 0ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 10.0825s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 10.043509 | 0.226222 | não |
| 2 | 10.342141 | 0.072410 | não |
| 3 | 10.321473 | 0.051742 | não |
| 4 | 10.375782 | 0.106051 | não |
| 5 | 10.097896 | 0.171835 | não |
| 6 | 10.217989 | 0.051742 | não |
| 7 | 9.824694 | 0.445037 | não |
| 8 | 10.404311 | 0.134580 | não |
| 9 | 10.639472 | 0.369741 | não |
| 10 | 10.125640 | 0.144091 | não |

## Valores ordenados (ordem crescente)

9.824694, 10.043509, 10.097896, 10.125640, 10.217989, 10.321473, 10.342141, 10.375782, 10.404311, 10.639472

## Mediana e dispersão

- Mediana: **10.269731s**
- Mínimo: 9.824694s
- Máximo: 10.639472s
- Média: 10.239291s
- Desvio padrão (amostral): 0.227772s
- Spread (min/max): 8.2932%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 8.2932% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

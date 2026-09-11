# Latency Report (hybrid, 140ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 33.0914s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 32.200464 | 0.698242 | não |
| 2 | 33.283745 | 0.385039 | não |
| 3 | 32.892134 | 0.006572 | não |
| 4 | 32.972669 | 0.073963 | não |
| 5 | 35.355165 | 2.456459 | não |
| 6 | 32.167214 | 0.731492 | não |
| 7 | 32.905278 | 0.006572 | não |
| 8 | 33.760042 | 0.861336 | não |
| 9 | 32.662118 | 0.236588 | não |
| 10 | 32.042351 | 0.856355 | não |

## Valores ordenados (ordem crescente)

32.042351, 32.167214, 32.200464, 32.662118, 32.892134, 32.905278, 32.972669, 33.283745, 33.760042, 35.355165

## Mediana e dispersão

- Mediana: **32.898706s**
- Mínimo: 32.042351s
- Máximo: 35.355165s
- Média: 33.024118s
- Desvio padrão (amostral): 0.976647s
- Spread (min/max): 10.3389%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 10.3389% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

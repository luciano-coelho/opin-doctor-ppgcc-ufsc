# Latency Report (hybrid, 140ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 45.0619s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 46.402574 | 0.967291 | não |
| 2 | 45.224047 | 0.211236 | não |
| 3 | 45.281595 | 0.153688 | não |
| 4 | 43.916962 | 1.518321 | não |
| 5 | 46.566281 | 1.130998 | não |
| 6 | 48.389746 | 2.954463 | não |
| 7 | 45.862164 | 0.426881 | não |
| 8 | 45.002256 | 0.433027 | não |
| 9 | 44.095631 | 1.339652 | não |
| 10 | 45.588971 | 0.153688 | não |

## Valores ordenados (ordem crescente)

43.916962, 44.095631, 45.002256, 45.224047, 45.281595, 45.588971, 45.862164, 46.402574, 46.566281, 48.389746

## Mediana e dispersão

- Mediana: **45.435283s**
- Mínimo: 43.916962s
- Máximo: 48.389746s
- Média: 45.633023s
- Desvio padrão (amostral): 1.295900s
- Spread (min/max): 10.1846%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 10.1846% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

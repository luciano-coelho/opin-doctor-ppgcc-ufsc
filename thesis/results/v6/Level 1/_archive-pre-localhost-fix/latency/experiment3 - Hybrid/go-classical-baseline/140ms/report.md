# Latency Report (hybrid, 140ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 44.7730s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 43.923420 | 0.378650 | não |
| 2 | 44.607395 | 0.305325 | não |
| 3 | 44.120403 | 0.181666 | não |
| 4 | 44.030112 | 0.271957 | não |
| 5 | 44.608057 | 0.305988 | não |
| 6 | 44.082275 | 0.219794 | não |
| 7 | 44.729863 | 0.427793 | não |
| 8 | 44.189782 | 0.112288 | não |
| 9 | 44.581383 | 0.279314 | não |
| 10 | 44.414357 | 0.112288 | não |

## Valores ordenados (ordem crescente)

43.923420, 44.030112, 44.082275, 44.120403, 44.189782, 44.414357, 44.581383, 44.607395, 44.608057, 44.729863

## Mediana e dispersão

- Mediana: **44.302070s**
- Mínimo: 43.923420s
- Máximo: 44.729863s
- Média: 44.328705s
- Desvio padrão (amostral): 0.291480s
- Spread (min/max): 1.8360%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 1.8360% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

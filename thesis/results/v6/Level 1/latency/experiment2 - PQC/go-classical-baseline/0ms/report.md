# Latency Report (pqc, 0ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **0ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 9.7625s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 10.271528 | 0.463798 | não |
| 2 | 9.730513 | 0.077217 | não |
| 3 | 9.315238 | 0.492492 | não |
| 4 | 10.035237 | 0.227507 | não |
| 5 | 9.239603 | 0.568127 | não |
| 6 | 9.526071 | 0.281659 | não |
| 7 | 9.317095 | 0.490635 | não |
| 8 | 10.280991 | 0.473261 | não |
| 9 | 10.114127 | 0.306397 | não |
| 10 | 9.884947 | 0.077217 | não |

## Valores ordenados (ordem crescente)

9.239603, 9.315238, 9.317095, 9.526071, 9.730513, 9.884947, 10.035237, 10.114127, 10.271528, 10.280991

## Mediana e dispersão

- Mediana: **9.807730s**
- Mínimo: 9.239603s
- Máximo: 10.280991s
- Média: 9.771535s
- Desvio padrão (amostral): 0.403996s
- Spread (min/max): 11.2709%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 11.2709% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

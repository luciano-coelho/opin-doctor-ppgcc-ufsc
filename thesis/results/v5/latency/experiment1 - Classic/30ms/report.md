# Latency Report (classic, 30ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 7.8171s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 8.080668 | 0.003835 | não |
| 2 | 7.729735 | 0.347098 | não |
| 3 | 7.786352 | 0.290481 | não |
| 4 | 8.327847 | 0.251015 | não |
| 5 | 7.980675 | 0.096158 | não |
| 6 | 8.471138 | 0.394305 | não |
| 7 | 8.139439 | 0.062606 | não |
| 8 | 7.762250 | 0.314583 | não |
| 9 | 8.072997 | 0.003835 | não |
| 10 | 8.151826 | 0.074993 | não |

## Valores ordenados (ordem crescente)

7.729735, 7.762250, 7.786352, 7.980675, 8.072997, 8.080668, 8.139439, 8.151826, 8.327847, 8.471138

## Mediana e dispersão

- Mediana: **8.076833s**
- Mínimo: 7.729735s
- Máximo: 8.471138s
- Média: 8.050293s
- Desvio padrão (amostral): 0.243602s
- Spread (min/max): 9.5916%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 9.5916% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

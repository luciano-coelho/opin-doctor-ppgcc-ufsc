# Latency Report (classic, 30ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **30ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 7.3044s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 7.111269 | 0.065377 | não |
| 2 | 7.182522 | 0.005876 | não |
| 3 | 7.481675 | 0.305029 | não |
| 4 | 7.154975 | 0.021671 | não |
| 5 | 7.170770 | 0.005876 | não |
| 6 | 7.215858 | 0.039212 | não |
| 7 | 7.149905 | 0.026741 | não |
| 8 | 7.151269 | 0.025377 | não |
| 9 | 7.215659 | 0.039013 | não |
| 10 | 7.377737 | 0.201091 | não |

## Valores ordenados (ordem crescente)

7.111269, 7.149905, 7.151269, 7.154975, 7.170770, 7.182522, 7.215659, 7.215858, 7.377737, 7.481675

## Mediana e dispersão

- Mediana: **7.176646s**
- Mínimo: 7.111269s
- Máximo: 7.481675s
- Média: 7.221164s
- Desvio padrão (amostral): 0.116854s
- Spread (min/max): 5.2087%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 5.2087% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

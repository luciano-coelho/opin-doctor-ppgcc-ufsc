# Latency Report (hybrid, 320ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **320ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 74.2834s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 74.233588 | 0.203997 | não |
| 2 | 73.478130 | 0.551461 | não |
| 3 | 74.601912 | 0.572321 | não |
| 4 | 73.892760 | 0.136831 | não |
| 5 | 74.257313 | 0.227722 | não |
| 6 | 73.336120 | 0.693471 | não |
| 7 | 74.396936 | 0.367345 | não |
| 8 | 74.069975 | 0.040384 | não |
| 9 | 73.590481 | 0.439110 | não |
| 10 | 73.989207 | 0.040384 | não |

## Valores ordenados (ordem crescente)

73.336120, 73.478130, 73.590481, 73.892760, 73.989207, 74.069975, 74.233588, 74.257313, 74.396936, 74.601912

## Mediana e dispersão

- Mediana: **74.029591s**
- Mínimo: 73.336120s
- Máximo: 74.601912s
- Média: 73.984642s
- Desvio padrão (amostral): 0.413061s
- Spread (min/max): 1.7260%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

1 execução(ões) inteira(s) descartada(s) e refeita(s) do zero (race reentrante auth<->mock_mtls, Decision 9 -- não é a mesma coisa que o retry parcial acima):

- run03, tentativa 1: HTTPError: 400 Client Error: Bad Request for url: https://localhost:8443/token

## Observações

Spread de 1.7260% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

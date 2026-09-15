# Latency Report (classic, 140ms, 10 runs)

Experimento (perfil): **classic**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 25.1908s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 24.859146 | 0.000115 | não |
| 2 | 24.871958 | 0.012697 | não |
| 3 | 24.830757 | 0.028504 | não |
| 4 | 24.840031 | 0.019230 | não |
| 5 | 24.913245 | 0.053984 | não |
| 6 | 24.941145 | 0.081884 | não |
| 7 | 24.817256 | 0.042005 | não |
| 8 | 24.859376 | 0.000115 | não |
| 9 | 24.791771 | 0.067490 | não |
| 10 | 24.914169 | 0.054908 | não |

## Valores ordenados (ordem crescente)

24.791771, 24.817256, 24.830757, 24.840031, 24.859146, 24.859376, 24.871958, 24.913245, 24.914169, 24.941145

## Mediana e dispersão

- Mediana: **24.859261s**
- Mínimo: 24.791771s
- Máximo: 24.941145s
- Média: 24.863885s
- Desvio padrão (amostral): 0.047238s
- Spread (min/max): 0.6025%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 0.6025% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

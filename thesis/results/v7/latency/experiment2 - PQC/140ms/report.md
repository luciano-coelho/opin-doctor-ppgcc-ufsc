# Latency Report (pqc, 140ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 33.7857s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 29.934914 | 0.172576 | não |
| 2 | 30.215425 | 0.107935 | não |
| 3 | 30.122711 | 0.015221 | não |
| 4 | 30.092269 | 0.015221 | não |
| 5 | 29.640727 | 0.466763 | não |
| 6 | 31.312588 | 1.205098 | não |
| 7 | 30.146971 | 0.039481 | não |
| 8 | 30.044717 | 0.062773 | não |
| 9 | 31.771838 | 1.664348 | não |
| 10 | 30.047209 | 0.060281 | não |

## Valores ordenados (ordem crescente)

29.640727, 29.934914, 30.044717, 30.047209, 30.092269, 30.122711, 30.146971, 30.215425, 31.312588, 31.771838

## Mediana e dispersão

- Mediana: **30.107490s**
- Mínimo: 29.640727s
- Máximo: 31.771838s
- Média: 30.332937s
- Desvio padrão (amostral): 0.665244s
- Spread (min/max): 7.1898%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 7.1898% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

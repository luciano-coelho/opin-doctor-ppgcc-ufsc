# Latency Report (pqc, 140ms, 10 runs)

Experimento (perfil): **pqc**
Latência aplicada (cenário): **140ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 34.2500s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 35.504207 | 5.265819 | não |
| 2 | 30.031309 | 0.207079 | não |
| 3 | 35.038657 | 4.800269 | não |
| 4 | 31.651156 | 1.412768 | não |
| 5 | 30.129232 | 0.109156 | não |
| 6 | 29.948847 | 0.289541 | não |
| 7 | 30.286150 | 0.047762 | não |
| 8 | 30.190625 | 0.047763 | não |
| 9 | 30.031065 | 0.207323 | não |
| 10 | 30.477955 | 0.239567 | não |

## Valores ordenados (ordem crescente)

29.948847, 30.031065, 30.031309, 30.129232, 30.190625, 30.286150, 30.477955, 31.651156, 35.038657, 35.504207

## Mediana e dispersão

- Mediana: **30.238388s**
- Mínimo: 29.948847s
- Máximo: 35.504207s
- Média: 31.328920s
- Desvio padrão (amostral): 2.137452s
- Spread (min/max): 18.5495%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 18.5495% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

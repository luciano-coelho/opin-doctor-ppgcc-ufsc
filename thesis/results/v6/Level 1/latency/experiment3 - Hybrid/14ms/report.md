# Latency Report (hybrid, 14ms, 10 runs)

Experimento (perfil): **hybrid**
Latência aplicada (cenário): **14ms**

Warmup (execução 0, descartada, não entra em nenhuma estatística): T_fluxo = 12.0843s, sem retry.

## As 10 execuções -- valores individuais (ordem coletada)

| # | T_fluxo (s) | Desvio absoluto da mediana (s) | Retry? |
|---|---|---|---|
| 1 | 12.031950 | 0.196044 | não |
| 2 | 11.910632 | 0.317362 | não |
| 3 | 11.443032 | 0.784961 | não |
| 4 | 13.018529 | 0.790535 | não |
| 5 | 12.321603 | 0.093609 | não |
| 6 | 12.374229 | 0.146235 | não |
| 7 | 12.134384 | 0.093609 | não |
| 8 | 12.056844 | 0.171150 | não |
| 9 | 12.831909 | 0.603915 | não |
| 10 | 12.667169 | 0.439175 | não |

## Valores ordenados (ordem crescente)

11.443032, 11.910632, 12.031950, 12.056844, 12.134384, 12.321603, 12.374229, 12.667169, 12.831909, 13.018529

## Mediana e dispersão

- Mediana: **12.227994s**
- Mínimo: 11.443032s
- Máximo: 13.018529s
- Média: 12.279028s
- Desvio padrão (amostral): 0.469043s
- Spread (min/max): 13.7682%

## Anomalias

Nenhuma execução precisou de retry (PAR TTL ou login race) neste cenário.

## Observações

Spread de 13.7682% entre as 10 execuções. Dentro do esperado para medição de tempo real (rede/SO), não achatado artificialmente -- nenhum outlier foi removido do cálculo da mediana.

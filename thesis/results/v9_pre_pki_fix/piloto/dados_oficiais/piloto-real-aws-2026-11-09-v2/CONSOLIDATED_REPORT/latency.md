# Secao (c) -- Latencia por perfil/rota

**Descritivo apenas -- N=5 execucoes por celula (perfil x rota). SEM teste de significancia estatistica (pre-registro v9 nunca definiu nenhum; diferente da v8, que usa N=30 e bootstrap/Mann-Kendall).**

## T_fluxo (segundos, por perfil x rota)
| Perfil/Rota | median | p95 | min | max | n |
|---|---|---|---|---|---|
| classico/L0 | 2.149 | 2.384 | 2.014 | 2.384 | 5 |
| classico/L219 | 14.452 | 14.56 | 14.317 | 14.56 | 5 |
| classico/L325 | 20.555 | 20.878 | 20.451 | 20.878 | 5 |
| hibrido-and/L0 | 2.264 | 2.454 | 2.219 | 2.454 | 5 |
| hibrido-and/L219 | 14.636 | 14.826 | 14.465 | 14.826 | 5 |
| hibrido-and/L325 | 20.684 | 21.038 | 20.337 | 21.038 | 5 |
| hibrido-v8/L0 | 2.271 | 2.51 | 2.215 | 2.51 | 5 |
| hibrido-v8/L219 | 14.544 | 14.723 | 14.47 | 14.723 | 5 |
| hibrido-v8/L325 | 20.52 | 20.911 | 20.199 | 20.911 | 5 |
| pqc/L0 | 2.207 | 2.282 | 2.073 | 2.282 | 5 |
| pqc/L219 | 14.445 | 14.588 | 14.386 | 14.588 | 5 |
| pqc/L325 | 20.67 | 21.136 | 20.213 | 21.136 | 5 |

## Latencia por endpoint (ms, amostra -- ver consolidated.json para a lista completa)
| Perfil/Rota/Endpoint | median | p95 | min | max | n |
|---|---|---|---|---|---|
| classico/L0//auth | 0.0 | 0.0 | 0.0 | 0.0 | 10 |
| classico/L0//auth/0NGoMmeeFMzkqPRq8W2HHZV_k_iAiq39grnSDKVgWLw | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/4g2mfhmmbHW-bIIiWlveJMzUeOMq1fe-38_zami7VNt | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/51MjzUMPUiq5uVz0e1hRMz9gVbYv4blyz1Mo09go16s | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/6wyyJnHAoHgmm-E7aQOOsn8cbL9a0YbBFjrosWrIc9A | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/77YK_9LCIgPn6pBiVtzoQ0ZxCczRdZc9dCZZxNUrN10 | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/AAC79y7c8EHCl2pJfZe4SDpymmPGm1oYBArMP6iuFyy | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/BNeJYvJM7g4o5l-C5q3hJMzmWBL6WIn5Z8o-vmnl04F | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/BijUZoSwdQqYKRJBLGHU5qpCPZXgz0Nlwx-5QVsXRdD | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/KbHcIgdeF48fnozjdqQ7Oo3HGnYy72tzlH-NOuCxJBf | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/MhbqV32uZRS_XFfsR4fl9npHOR-m5FSmWWq5E8I3b0z | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/S8Y9k4pUps008cS4GZORFI9u8va0DDyGdTlAuZN34x8 | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/UKev1tULc-kmkIE5253LWAPy9JjFwXMLATxKT3hOkOO | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/X-7CZGbdRk7n1ea8OHJUxSwDwOn8SYbRu-7UJC4hHr0 | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/gQQ2exGMV0SXZt9r_lIVd5UVaw0pYWJChvSKpLsgmC_ | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/gySi_5dIfO3WpTKjv0nefy17mW77_e1cLZmhbMKKV-L | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/hggMO29EKY-RXw0gha638gx50aYLhEBhN_7r7ITu5RN | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/jS_-j5TlQU31PtEMKHdE7ABaqXb34Z0k-WPOc-o7RtC | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/kMwXoiiSZw3qiPXNhtGqMHL_YUaRTJURkEmHZ9d8EvI | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
| classico/L0//auth/ucwCGVfBo7Y454pw_jVeOaZ9G0EIvzBeySyQcLNR_zi | 0.0 | 0.0 | 0.0 | 0.0 | 1 |
(+952 linhas adicionais em consolidated.json)

## RTT nominal vs medido (ambos os canais) e initcwnd/MSS reais
| Rota | nominal (ms) | medido via probe (ms) | medido via pcap (ms) | consistente? |
|---|---|---|---|---|
| L0 | 0 | 0.148 | 0.098 | True |
| L219 | 219 | 219.889 | 220.048 | True |
| L325 | 325 | 330.196 | 330.859 | True |

initcwnd/MSS medidos REALMENTE apenas para **classico/L219** (unica combinacao que o probe dedicado do criterio 2 cobriu neste piloto -- ver `REQUISITOS_CAMPANHA_OFICIAL.md` item (a) para o gap conhecido): cwnd=10, mss=1448B, bytes enviados na 1a janela de RTT=14480B (RTT usado: 219.945ms). As demais 11 combinacoes de perfil x rota: **não verificado**.

# Relatorio Consolidado de Metricas Experimentais: campanha oficial real multi-regiao AWS

**Migracao pos-quantica do ecossistema OPIN: Classic, PQC puro, Hybrid (duas cadeias, secao 3.3) e Controle -- rede real, uma janela, 320 execucoes**
Luciano Figueiredo Coelho | PPGCC/LabSEC/UFSC

Todo numero deste documento vem dos dados brutos da campanha oficial em `thesis/results/v9/campaign/oficial_raw/oficial_out/` ou dos arquivos ja organizados em `thesis/results/v9/`, recomputado por `thesis/scripts/verify_consolidated_report_v9.py` (Secao 7). Nenhum numero foi estimado nem copiado de outra fonte.

## Resumo executivo

A campanha oficial mediu 320 execucoes reais (4 perfis x 8 rotas x 10 execucoes), em multiplas regioes AWS reais, com zero falhas e zero necessidade de repeticao. Os 4 perfis sao Classic, PQC puro, **Hybrid** (perfil `hibrido-and`, duas cadeias de certificado independentes -- RSA-2048 e ML-DSA-65 -- com `CertificateVerify` carregando as duas assinaturas, modo strict com dual obrigatorio, o desenho da secao 3.3 desta tese) e **Controle** (uma unica cadeia com a assinatura ML-DSA-65 embutida como extensao X.509, verificada offline, nunca assinada ao vivo). OPINsize na variante de TOKEN COMPLETO (3 termos, sem PKI): Classic 57.443,12B; PQC 294.118,92B (5,12x Classic); Hybrid 357.794,96B (6,23x); Controle 315.008,96B (5,48x). Na variante complementar de so-assinatura: Classic 30.245,88B; PQC 229.585,92B; Hybrid 253.328,08B; Controle 210.542,08B. T_fluxo (mediana) na rota mais distante (L325, RTT nominal 325ms): Classic 25,438s; PQC 26,114s; Hybrid 26,335s; Controle 26,294s. RTT real medido (critério 2, canal servidor-cliente, `ss -ti`, coleta complementar posterior, 5 rotas) bate com o nominal dentro de ~16ms. Auditoria de recomputo: 0 divergencias. Esta campanha rodou uma UNICA janela, N=10 por celula -- onde uma secao nao tem dado equivalente medido, este documento diz "nao medido nesta campanha" e o motivo, nunca preenche com um numero estimado.

## 1. Escopo desta campanha

4 perfis (Classic, PQC, Hybrid, Controle), 8 rotas reais (`L0-sa-east-1`, `L0-us-east-1`, `L0-ap-northeast-1` co-localizadas, RTT nominal 0; `L14`, `L30`, `L123`, `L219`, `L325`, RTT nominal 14/30/123/219/325ms), 10 execucoes medidas por celula (320 total), 5 aquecimentos por celula (160 total, descartados da analise, nunca lidos por nenhuma estatistica deste documento) e 32 capturas dedicadas (4 perfis x 8 rotas, uma por celula). Lancada em 2026-11-12T21:54:53Z, terminada em 2026-11-13T04:04:02Z (~6h09min, incluindo as capturas dedicadas integradas no mesmo laco por rota).

**Infraestrutura.** Instancias de servidor e cliente: `m7i-flex.large`. Instancia de controle (so orquestracao, nunca parte de nenhum fluxo medido): `t4g.micro`. Um unico binario de gateway (Go) usado pelos 4 perfis -- sha256 esperado `33f3871b31c33b6b9ec3cfa32948fe37228def1eaefd8aa299d06d5dc716fe18`, verificado em TODAS as verificacoes reais do manifesto desta janela, `pin_matched=True` em 100% delas (recomputado por `verify_consolidated_report_v9.py`).

**Pre-registro.** Os 7 criterios desta propria campanha (Secao 9) foram pre-registrados antes do lancamento, como condicao de ir/nao-ir -- os resultados, incluindo os FAIL, sao reportados integralmente na Secao 9, nenhum escondido ou revertido pela investigacao posterior da Secao 10.

Todo numero deste documento e lido ou computado de `thesis/results/v9/campaign/oficial_raw/oficial_out/piloto_calls.json`, `piloto_combined.log`, `criterio1_capturas/` e `manifest.json`, recomputado por `thesis/scripts/verify_consolidated_report_v9.py` (Secao 7).

### 1.1. Os 4 perfis

| Perfil | Assinaturas | Troca de chaves TLS | Canal interno AS<->RS |
|---|---|---|---|
| Classic | RSA-PSS (PS256) | ECDHE, curva P-384 pura | Classico |
| PQC | ML-DSA-65 puro (FIPS 204) em tokens, chaves, e assinatura de toda a cadeia de CA (incluindo a raiz) | ML-KEM-1024 puro (FIPS 203) | Classico |
| **Hybrid** (perfil `hibrido-and`) | RSA-PSS E ML-DSA-65, **duas cadeias de certificado independentes**, ambas verificadas, modo strict | SecP384r1MLKEM1024 | Classico |
| **Controle** | RSA-PSS ao vivo; ML-DSA-65 so como extensao X.509 estatica, verificada offline | SecP384r1MLKEM1024 | Classico |

**Cadeia de CA do PQC, confirmada no gerador real de certificados** (`thesis/results/v9/certs/main.go:593-595`):
```go
pqcCA, pqcCAKey := generateMLDSACA("pqc_ca", outDir)
pqcServer, _ := generateMLDSALeaf("pqc_server", pqcCA, pqcCAKey, x509.ExtKeyUsageServerAuth, serverSANs, outDir)
pqcClient, _ := generateMLDSALeaf("pqc_client", pqcCA, pqcCAKey, x509.ExtKeyUsageClientAuth, clientSANs, outDir)
```
A CA do perfil PQC e gerada por `generateMLDSACA` (ML-DSA-65, autoassinada) e as folhas (servidor e cliente) sao assinadas por essa MESMA chave ML-DSA-65 da CA -- a cadeia e ML-DSA-65 ponta a ponta, nunca RSA em nenhum nivel.

## 2. Perfis e a matriz de camadas -- evidencia real de codigo

**Hybrid (perfil `hibrido-and`)** -- `thesis/results/v9/integration/gateway/main.go:271-272,300-330`:
```go
case "hibrido-and":
    cfg, err = dualServerConfig(certDir)
// dualServerConfig carrega DOIS tls.Certificate distintos (RSA e ML-DSA-65),
// com DUAS CAs separadas, via tls.Config.Dual (*tls.DualConfig)
```
Comentario real no codigo: `"STRICT (...): Hibrido-AND has always meant strict in this project"`. `main.go:150`: `if profile == "hibrido-and" && !cs.DualAuthenticated { r.Error = ... }` -- exige dual autenticado, erro caso contrario.

**Controle** -- `main.go:268-270`, `thesis/results/v9/integration/gateway/hybridVerification.go:134-164`: UMA cadeia (`singleChainServerConfig`), com um callback customizado (`hybridVerifyPeerCertificateFunc`) que verifica a extensao `AltSignatureValue` do certificado OFFLINE, nunca via assinatura ao vivo. O log real do callback confirma a verificacao offline das duas assinaturas (RSA e ML-DSA-65) sem reproduzir o identificador interno aqui.

**Composicao real do handshake, mensagem por mensagem (capturas dedicadas, rota L0-ap-northeast-1, stream 0 -- recomputado por `verify_consolidated_report_v9.py`), com a soma da captura, o total do gateway e a diferenca entre os dois mostradas explicitamente:**

| Mensagem | Classic | PQC | **Hybrid** | **Controle** |
|---|---:|---:|---:|---:|
| ClientHello | 304 | 1.775 | 1.854 | 1.872 |
| ServerHello+EncryptedExtensions+CertificateRequest | 183+6+105=294 | 1.654+6+100=1.760 | 1.751+6+94=1.851 | 1.751+6+107=1.864 |
| Certificate (servidor) | 909 | 5.628 | **6.578** (2 cadeias) | **6.251** (1 cadeia, extensao maior) |
| CertificateVerify+Finished (servidor) | 260+32=292 | 3.313+32=3.345 | **3.571+32=3.603** (RSA-PSS 256B + ML-DSA-65 3.309B) | **260+32=292** (so RSA-PSS) |
| Certificate (cliente) | 796 | 5.515 | 6.352 | 6.140 |
| CertificateVerify+Finished (cliente) | 260+32=292 | 3.313+32=3.345 | 3.603 | 292 |
| **Soma das mensagens (captura, tshark)** | **2.887** | **21.368** | **23.841** | **16.711** |
| **Total do gateway (handshakeBytesIn+Out, autoritativo)** | **3.125** | **21.606** | **24.080** | **16.949** |
| **Diferenca (gateway - captura)** | **238** | **238** | **239** | **238** |

O `CertificateVerify` do Hybrid (3.571B) e a soma literal de uma assinatura RSA-PSS (256B) e uma ML-DSA-65 (3.309B) mais ~6B de enquadramento -- as DUAS assinaturas, ambas verificadas ao vivo, exatamente o desenho da secao 3.3. O Controle evita a assinatura ML-DSA-65 ao vivo (so 260B, RSA-PSS), pagando em troca um certificado maior (a extensao estatica) -- por isso o Controle sai numericamente menor que o Hybrid e ate que o PQC, apesar de carregar os dois tipos de chave: a operacao de assinatura PQC em tempo real (paga duas vezes pelo PQC puro, uma vez pelo Hybrid em cada lado) custa mais bytes que uma extensao estatica maior. A diferenca constante de ~238B entre a soma da captura (so `tls.handshake.length`, sem cabecalhos) e o total do gateway e CONFIRMADA na Secao 10 como overhead de protocolo (cabecalho de registro TLS, ChangeCipherSpec, etiqueta de autenticacao) nunca contado pela soma da captura -- nao e um gap nao-identificado.

## 3. Resultados de tamanho: a equacao OPINsize

```
OPINsize = N_mTLS x handshake_bytes + N_JWT x JWT_size + N_JWK x JWK_size [+ N_PKI x PKI_bytes]
```

Contagens reais, recomputadas (constantes nos 4 perfis e nas 320 execucoes -- `verify_consolidated_report_v9.py`): **N_mTLS=6** (streams TCP reais com SNI "mtls" nas capturas dedicadas), **N_JWT=28**, **N_JWK=4** (quatro consultas reais a `/jwks` medidas por execucao), **N_PKI=4** (`/root-ca.pem`+`/issuer-ca.pem`, 2+2).

As quatro consultas a `/jwks` se dao em 2 sessoes de cliente distintas (`pool_label`, confirmado nos dados reais) x 2 destinos de servidor cada -- o servidor de autorizacao (`host_header=AUTH_HOST`) e o servidor de recursos (`host_header=API_HOST`), confirmado no codigo real em `thesis/scripts/opin_flow.py:2117` (chamada com `AUTH_HOST`) e `thesis/scripts/opin_flow.py:2204` (chamada com `API_HOST`).

`handshake_bytes` vem do log do proprio gateway (`handshakeBytesIn`+`handshakeBytesOut`), fonte autoritativa por decisao explicita (Secao 10). `JWT_size` e reportado em duas variantes: **o token completo transmitido (definicao principal desta tese)** e, como complemento, so a assinatura crua.

| Termo | Classic | PQC | **Hybrid** | **Controle** |
|---|---:|---:|---:|---:|
| handshake_bytes (por conexao, N_mTLS=6) | 3.125 | 21.606 | **24.080** | **16.949** |
| JWT_size token-completo (media, N_JWT=28) | 1.209,04 | 5.377,39 | 7.041,32 | 7.041,32 |
| JWT_size so-assinatura (media, N_JWT=28) | 237,71 | 3.072,64 | 3.310,36 | 3.310,36 |
| JWK_size (media de resposta, N_JWK=4) | 1.210 | 3.479 | 4.039,5 | 4.039,5 |
| PKI_bytes (media, N_PKI=4) | 2.213 | 8.110 | **2.213** | **9.442** |

**OPINsize, 3 termos, TOKEN COMPLETO (sem PKI, definicao principal desta tese):**

| Perfil | OPINsize |
|---|---:|
| Classic | 57.443,12 |
| PQC | 294.118,92 |
| **Hybrid** | **357.794,96** |
| **Controle** | **315.008,96** |

**OPINsize, 4 termos, TOKEN COMPLETO (com PKI):**

| Perfil | OPINsize |
|---|---:|
| Classic | 66.295,12 |
| PQC | 326.558,92 |
| **Hybrid** | **366.646,96** |
| **Controle** | **352.776,96** |

**OPINsize, variante complementar so-assinatura, 3 e 4 termos:**

| Perfil | 3 termos | 4 termos |
|---|---:|---:|
| Classic | 30.245,88 | 39.097,88 |
| PQC | 229.585,92 | 262.025,92 |
| **Hybrid** | **253.328,08** | **262.180,08** |
| **Controle** | **210.542,08** | **248.310,08** |

A variante so-assinatura usa o tamanho cru da assinatura (classica+PQ somadas quando aplicavel), sem o restante do token. Este documento nao afirma que essa variante e equivalente a nenhuma formula publicada especifica de outro trabalho -- essa comparacao exigiria citar e confirmar a secao exata da fonte original, o que nao foi feito aqui.

**PKI do Hybrid identico ao Classic -- investigado, nao e bug.** Codigo real, `thesis/results/v9/integration/gateway/business_server.go:241-250` (`realCAFilesForProfile`): o perfil `hibrido-and` cai no mesmo `default` que `classico` (serve o MESMO par `root_ca.crt`/`issuer_ca.crt`); so `pqc` e o perfil Controle tem pares proprios. Comentario real no codigo: `opin_flow.py's verify_ca_chain() only branches on "pqc" vs everything else... hibrido-and falls into that same "everything else" branch`. A cadeia ML-DSA-65 do Hybrid NUNCA e baixada por este endpoint de aplicacao -- so existe dentro do proprio handshake mTLS (mensagem Certificate, 6.578B, Secao 2), onde seu custo real ja esta 100% capturado no termo `handshake_bytes`, nunca subestimado.

### Tamanhos de JWKS e certificados (recomputado)

`/jwks`: 4 chamadas/execucao (2 sessoes x 2 destinos de servidor, acima). Classic: 2x1.814B+2x606B. PQC: 2x4.071B+2x2.887B. Hybrid e Controle: 2x4.366B+2x3.713B (identicos entre si -- Hybrid reusa integralmente a config de aplicacao/JWKS do Controle, so o mecanismo TLS muda). Assinatura ML-DSA-65 crua medida: 3.309B em TODAS as ocorrencias (bate exatamente com o esperado).

## 4. Resultados de latencia

### T_fluxo por celula (mediana, min, max, desvio-padrao; N=10/celula, janela unica) -- RTT nominal, nao medido diretamente por celula

| Perfil | Rota | RTT nominal | Mediana | Min | Max | Desvio |
|---|---|---:|---:|---:|---:|---:|
| Classic | L0-sa-east-1 | 0ms | 2,388s | 2,293s | 2,555s | 0,075s |
| Classic | L0-us-east-1 | 0ms | 3,862s | 3,742s | 3,929s | 0,050s |
| Classic | L0-ap-northeast-1 | 0ms | 5,893s | 5,792s | 6,007s | 0,065s |
| Classic | L14 | 14ms | 4,838s | 4,797s | 4,991s | 0,067s |
| Classic | L30 | 30ms | 8,163s | 8,001s | 8,290s | 0,086s |
| Classic | L123 | 123ms | 10,992s | 10,899s | 11,037s | 0,043s |
| Classic | L219 | 219ms | 17,083s | 16,975s | 17,302s | 0,103s |
| Classic | L325 | 325ms | 25,438s | 25,078s | 25,692s | 0,210s |
| PQC | L0-sa-east-1 | 0ms | 2,354s | 2,280s | 2,560s | 0,097s |
| PQC | L0-us-east-1 | 0ms | 3,996s | 3,945s | 4,306s | 0,114s |
| PQC | L0-ap-northeast-1 | 0ms | 6,474s | 6,306s | 6,508s | 0,067s |
| PQC | L14 | 14ms | 5,093s | 4,997s | 5,195s | 0,064s |
| PQC | L30 | 30ms | 8,727s | 8,651s | 8,850s | 0,064s |
| PQC | L123 | 123ms | 11,200s | 11,107s | 11,260s | 0,063s |
| PQC | L219 | 219ms | 17,459s | 17,389s | 17,580s | 0,052s |
| PQC | L325 | 325ms | 26,114s | 25,718s | 26,412s | 0,218s |
| **Hybrid** | L0-sa-east-1 | 0ms | 2,508s | 2,426s | 2,687s | 0,072s |
| **Hybrid** | L0-us-east-1 | 0ms | 4,200s | 4,049s | 4,303s | 0,065s |
| **Hybrid** | L0-ap-northeast-1 | 0ms | 6,684s | 6,483s | 6,903s | 0,148s |
| **Hybrid** | L14 | 14ms | 5,311s | 5,117s | 5,347s | 0,082s |
| **Hybrid** | L30 | 30ms | 8,960s | 8,740s | 9,195s | 0,160s |
| **Hybrid** | L123 | 123ms | 11,362s | 11,226s | 11,500s | 0,093s |
| **Hybrid** | L219 | 219ms | 17,721s | 17,597s | 17,912s | 0,123s |
| **Hybrid** | L325 | 325ms | 26,335s | 25,957s | 26,943s | 0,342s |
| **Controle** | L0-sa-east-1 | 0ms | 2,494s | 2,418s | 2,542s | 0,051s |
| **Controle** | L0-us-east-1 | 0ms | 4,243s | 4,062s | 4,388s | 0,106s |
| **Controle** | L0-ap-northeast-1 | 0ms | 6,660s | 6,483s | 6,944s | 0,151s |
| **Controle** | L14 | 14ms | 5,276s | 5,074s | 5,396s | 0,110s |
| **Controle** | L30 | 30ms | 9,055s | 8,717s | 9,187s | 0,159s |
| **Controle** | L123 | 123ms | 11,389s | 11,224s | 11,453s | 0,071s |
| **Controle** | L219 | 219ms | 17,763s | 17,504s | 17,903s | 0,133s |
| **Controle** | L325 | 325ms | 26,294s | 25,715s | 26,974s | 0,364s |

**Nao medido nesta campanha:** diferenca por celula contra Classic com teste de Mann-Whitney/tamanho de efeito/correcao de Holm; teste de sinal nas 8 rotas; modelo delta=a+bxRTT por bootstrap. Motivo: esta campanha rodou uma UNICA janela, N=10/celula -- essas tecnicas pressupoem multiplas janelas independentes agrupadas, o que nunca aconteceu aqui.

### RTT real medido e initcwnd -- coleta complementar POSTERIOR, separada da campanha principal

Apos o fim da campanha oficial, uma coleta complementar separada religou a frota especificamente para medir RTT real e initcwnd, usando o mesmo codigo congelado. Essa coleta cobriu **so as 5 rotas de RTT nominal maior que zero** (`L123`, `L219`, `L325`, `L14`, `L30`) -- as 3 rotas co-localizadas (`L0-sa-east-1`, `L0-us-east-1`, `L0-ap-northeast-1`) **ficaram sem nenhuma medicao de RTT/initcwnd**, por desenho (RTT nominal 0, fora do escopo dessa coleta).

O **criterio 2** (initcwnd real) foi o que de fato produziu o RTT medido abaixo -- o canal servidor->cliente desse criterio usa `ss -ti` (estatisticas reais do kernel TCP) e reporta o RTT real da conexao como efeito colateral da medicao de initcwnd. O **criterio 7** (produtor dedicado de RTT por rota) FALHOU nesta coleta -- depende de um gateway/listener ativo que so existe durante uma janela de execucao viva, nunca isoladamente horas depois; nenhum dado do criterio 7 entra nesta tabela.

| Rota | RTT nominal | RTT real medido (criterio 2, canal servidor->cliente, `ss -ti`) | cwnd inicial | MSS |
|---|---:|---:|---:|---:|
| L123 | 123ms | 123,207ms | 10 | 1.448B |
| L219 | 219ms | 211,434ms | 10 | 1.448B |
| L325 | 325ms | 340,971ms | 10 | 1.448B |
| L14 | 14ms | 14,929ms | 10 | 1.448B |
| L30 | 30ms | 34,616ms | 10 | 1.448B |

O canal cliente->servidor do criterio 2 tambem falhou nesta coleta (listener nao ativo) -- achado real, nao corrigido, fora do escopo da coleta autorizada.

## 5. Metricas de rede

**Nao medido nesta campanha.** Jitter (diferenca absoluta mediana entre amostras de RTT consecutivas por execucao), retransmissoes/segmentos e ACKs duplicados/fora de ordem exigiriam pcap completo em CADA execucao real. Esta campanha so capturou pcap dedicado em 32 celulas (uma amostra por perfil x rota, nao em cada uma das 320 execucoes) -- nao ha dados suficientes pra calcular essas metricas por execucao real. O equivalente mais proximo medido e o initcwnd/MSS/RTT da Secao 4 (coleta complementar, 5 rotas, canal servidor->cliente so).

## 6. CPU e contabilidade

CPU steal e utilizacao sao medidos por execucao (`cpu_client`/`cpu_server`, amostra de `/proc/stat` antes/depois de cada chamada). Valores reais, maximo e mediana, por perfil, nas 320 execucoes (recomputado):

| Perfil | Steal max | Steal mediana | Utilizacao max | Utilizacao mediana |
|---|---:|---:|---:|---:|
| Classic | 0,072% | 0,0% | 33,723% | 6,721% |
| PQC | 0,060% | 0,0% | 34,992% | 6,191% |
| **Hybrid** | 0,151% | 0,0% | 37,915% | 7,409% |
| **Controle** | 0,068% | 0,0% | 31,392% | 7,849% |

Todos os valores de steal maximo ficam muito abaixo do limite de auditoria de 5% definido pro projeto -- nenhuma celula disparou o alerta de steal.

**Nao medido nesta campanha:** decomposicao de T_fluxo por fase (HTTP calls/signing/verification/residual/setup-teardown). Motivo: esta campanha so registra `start_utc`/`end_utc` por execucao inteira (um unico intervalo), sem sub-temporizadores de fase.

## 7. Conferencia de reprodutibilidade (script versionado)

Todo numero deste relatorio foi recomputado automaticamente, direto dos dados brutos em `thesis/results/v9/campaign/oficial_raw/oficial_out/`, por `thesis/scripts/verify_consolidated_report_v9.py` -- nunca lido de memoria de sessao anterior nem deste mesmo documento. Resultado da conferencia (saida completa em `thesis/results/v9/verify_consolidated_report_v9_output.txt`):

- Contagens do fluxo: 44 chamadas e 28 JWTs, constantes nas 320 execucoes -- **0 divergencias**.
- T_fluxo, as 32 celulas: valores recomputados batem byte a byte com a tabela da Secao 4 -- **0 divergencias**.
- OPINsize, os 4 perfis, as 2 variantes de JWT, as 2 formulas (3/4 termos): batem com as tabelas da Secao 3 -- **0 divergencias**.
- Retries: 0/320 execucoes, 0/160 aquecimentos -- **0 divergencias**.
- Composicao do handshake por mensagem, os 4 perfis: bate com a Secao 2 -- **0 divergencias**.
- Manifesto: `total_execucoes=320=expected_total`, `32/32 capturas, 0 falhas`, sha256 do gateway `33f3871b31c33b6b9ec3cfa32948fe37228def1eaefd8aa299d06d5dc716fe18` em 100% das verificacoes (`pin_matched=True`) -- **0 divergencias**.

**RESULTADO FINAL: 0 divergencias em todas as categorias conferidas.**

## 8. Auditoria independente

`thesis/scripts/audit_v9_from_raw.py` contra `thesis/results/v9/campaign/oficial_raw/audit_manifest/` -- resultado em `thesis/results/v9/audit_recompute_from_raw.txt`: 320 execucoes, contagens por perfil iguais (3.520 cada), tamanhos de assinatura recomputados 100% batendo com o esperado (RSA-2048=256B, ML-DSA-65=3.309B), TLS dual/perfil 0 divergencias. **RESULTADO: 0 divergencia(s).**

## 9. Sete criterios pre-registrados -- resultado real, com os FAIL declarados

Estes 7 criterios foram pre-registrados como condicao de ir/nao-ir desta propria campanha, antes do lancamento.

| # | Criterio | Resultado | Detalhe |
|---|---|---|---|
| 1 | Tamanhos por mensagem de handshake | **FAIL** | Certificate bate nos 4 perfis. ClientHello do Classic: 308B medido vs 336B de baseline (tolerancia 0) -- desvio formal, Secao 10. PQC (1.779B), **Hybrid (1.858B)** e **Controle (1.876B)** batem exatamente com seus respectivos baselines. |
| 2 | initcwnd real | **FAIL** (pipeline oficial) / coleta complementar parcial | O pipeline oficial nunca gerou os arquivos `criterio2_initcwnd_*.json`; a coleta complementar separada (Secao 4) mediu o canal servidor->cliente com sucesso em 5 rotas, mas o canal cliente->servidor falhou (listener nao ativo). |
| 3 | Zero erros na rota mais distante | **FAIL (arquivo)** / **PASS (recomputado)** | O arquivo dedicado nunca foi gerado, mas recomputado direto dos dados brutos: 40 execucoes reais em L325 (10 x 4 perfis), 0 ocorrencias de erro em todo o log combinado, 0 retries. |
| 4 | Contagens do fluxo | **PASS** | 320/320 execucoes, contagem constante (44/28/4/4) nos 4 perfis. |
| 5 | Zero erros | **PASS** | Nenhuma ocorrencia de erro no log combinado. |
| 6 | Instrumentacao completa | **PASS** | 320/320 execucoes com curva/dualAuthenticated/keylog corretos. |
| 7 | Sanidade de latencia por rota | **FAIL** | Arquivo dedicado nunca gerado pelo pipeline oficial; o produtor dedicado tambem falhou na coleta complementar (gateway/listener nao ativo fora de uma janela viva). RTT real foi obtido por outra via (criterio 2, Secao 4). |

**A investigacao da Secao 10 confirma a causa do FAIL do criterio 1 (desvio do ClientHello do Classico, reconciliado por reproducao local), mas NAO reverte o resultado: o criterio 1 permanece FAIL no resultado pre-registrado.**

## 10. Notas de transparencia

**Divergencia de ~238B entre captura dedicada e log do gateway -- hipotese do NewSessionTicket DESCARTADA; hipotese de enquadramento TLS CONFIRMADA.** A hipotese do `NewSessionTicket` foi testada decifrando uma captura de cada um dos 4 perfis com o keylog real (`docker run --entrypoint tshark mockopin-v9-measure -o "tls.keylog_file: ..."`, localmente, sem nenhuma coleta nova contra a AWS): nenhum registro `tls.record.content_type==22` (Handshake) aparece em nenhum dos 4 streams depois da mensagem Finished -- **descartada**. Em seguida, testada a hipotese de que a diferenca e enquadramento de protocolo nunca contado pela soma anterior (`tls.handshake.length`, que so conta o corpo da mensagem, sem o cabecalho de 4B de handshake, sem os 5B de cabecalho de registro TLS, sem a etiqueta de autenticacao/byte de tipo dos registros cifrados, e sem os registros de ChangeCipherSpec). Recomputando por registro TLS decifrado (`tshark -T ek`, mesmas capturas), somando por direcao `5B (cabecalho de registro) + tamanho do registro` para todo registro com `content_type` igual a 20 (ChangeCipherSpec) ou 22 (Handshake, decifrado) -- o resultado bate com o total do gateway quase exatamente: Classic 3.125/3.125 (diferenca 0B), PQC 21.606/21.606 (0B), Controle 16.949/16.949 (0B), Hybrid 24.079/24.080 (diferenca residual de 1B, 0,004%, nao investigada). **A hipotese de enquadramento esta CONFIRMADA** -- os ~238B nunca foram um gap nao-contabilizado; eram overhead de protocolo real (cabecalhos de registro, ChangeCipherSpec, etiqueta de autenticacao) que a soma anterior (baseada so em `tls.handshake.length`) nunca incluia. **Fonte autoritativa do termo do OPINsize permanece o log do gateway** (instrumentacao de primeira parte, medida na fronteira real do handshake, agora reconciliada byte a byte contra a captura).

**Desvio do ClientHello do Classic (28B) -- verificacao offline realizada, causa CONFIRMADA por reproducao local.** A medicao real da campanha (308B, SNI `"mtls"`, `session_id` de 32B, bloco de extensoes de 225B) e reproduzivel nas 8 rotas -- confiavel. O script de calibracao original (`thesis/results/v9/integration/measure/measure.sh`, perfil `classico`, `TICKETS_DISABLED=true`) e a imagem Docker que o executa (`mockopin-v9-measure`, ja local, buildada contra o MESMO toolchain Go pinado da campanha) ainda existem no repositorio -- foram reexecutados localmente, em loopback, sem nenhuma coleta nova contra a AWS. O ClientHello reproduzido localmente mede exatamente 336B (igual a `CLIENTHELLO_BASELINE["classico"]` em `thesis/results/v9/integration/evaluate_criteria.py:175`), com a MESMA SNI (`"mtls"`), o MESMO `session_id` de 32B e as MESMAS 11 extensoes na mesma ordem que a captura real da campanha -- so o CONTEUDO de 3 extensoes difere: a lista de cifras (`cipher_suites`, 26B locais vs 6B reais -- o cliente Go de teste do T6, `thesis/results/v9/integration/proxy/main.go:227`, anuncia 13 suites, incluindo 10 suites legadas de TLS 1.2, mesmo com `MinVersion`/`MaxVersion` fixados em TLS 1.3, porque o Go nao filtra a lista anunciada pela versao minima quando `CipherSuites` nao e restringido explicitamente), a extensao `signature_algorithms` (28B vs 22B, +6B) e `signature_algorithms_cert` (5B vs 3B, +2B) -- a mesma causa raiz (lista mais ampla de algoritmos legados anunciada pelo cliente Go de teste). Soma exata: 20B (cifras) + 6B (sig_algs) + 2B (sig_algs_cert) = **28B, reconciliando 100% da diferenca, sem residuo**. Causa raiz real: o cliente real da campanha (`opin_flow.py`, Python, `requests.Session` + `pyOpenSSL` via `urllib3.contrib.pyopenssl`, `thesis/scripts/opin_flow.py:153,1730`) e o cliente de calibracao do T6 (binario Go `proxy`, usado so por `measure.sh`, nunca na campanha real) sao duas pilhas TLS DIFERENTES -- cada uma anuncia um ClientHello de tamanho diferente para o mesmo conjunto de certificados/curva, mesmo chegando ao mesmo cifrario negociado (TLS 1.3, AES-256-GCM). A baseline de 336B nunca foi medida com o cliente real da campanha -- **nao e um erro na medicao real (308B), e uma diferenca esperada entre dois clientes TLS distintos**. Os outros 3 perfis batem exatamente com seus baselines porque o ClientHello deles e dominado pelo tamanho do `key_share` (ML-KEM), onde os mesmos 28B de diferenca de pilha TLS ficam no ruido relativo. **O criterio 1 permanece FAIL** (Secao 9) -- a baseline em si nao foi corrigida (seria uma alteracao de criterio pre-registrado), mas a causa da divergencia esta agora totalmente explicada e documentada.

**As duas tentativas abortadas.** A primeira tentativa de lancamento desta campanha crashou numa rota tardia da ordem de execucao por um prazo de heartbeat em lote (3h) vencido antes do laco chegar ali, numa janela de ~5,2h -- corrigido com uma thread de heartbeat propria, independente do laco principal. A segunda tentativa, ja com o heartbeat corrigido, crashou numa celula por um blip de SSH transitorio sem nenhum retry em `run_execution` -- corrigido com retry de transporte, 3 tentativas, so pra falha de SSH (rc=255), nunca pra erro de aplicacao. As duas tentativas foram arquivadas intocadas, nunca usadas em nenhum numero deste documento.

**N_JWK=4.** As quatro consultas a `/jwks` medidas por execucao correspondem a 2 sessoes de cliente distintas x 2 destinos de servidor (servidor de autorizacao e servidor de recursos, Secao 3) -- um numero real desta campanha, nunca comparado aqui com nenhuma outra convencao de contagem.

## 11. Congelamento, integridade e publicacao

Commit congelado: `978a6fa3`. sha256 de todo o codigo implantado nos 12 hosts reais, verificado ANTES do lancamento desta janela: `all_ok: true` (24 arquivos, controle + 3 servidores + 8 clientes). sha256 do binario do gateway, verificado em TODAS as verificacoes reais do manifesto da janela: `33f3871b31c33b6b9ec3cfa32948fe37228def1eaefd8aa299d06d5dc716fe18`, `pin_matched=True` em 100%.

**Publicacao real (ocorrida antes desta revisao).** Duas varreduras de segredos completas (tracked + staged + historico completo de todos os commits, todas as refs) rodaram antes do push, com o mesmo resultado nas duas: PASS em padrao de chave de acesso AWS, atribuicao inline de segredo, cabecalho de chave privada PEM/SSH e ID de conta real; FAIL em uma unica categoria -- o IP publico real do operador, 1 ocorrencia, num commit anterior a esta sessao, ja presente no repositorio remoto antes de qualquer trabalho desta campanha (categoria redigida aqui -- nenhum valor de IP ou de conta reproduzido neste documento). Verificacao direcionada confirmou que os commits publicados nesta sessao nao introduzem nenhuma ocorrencia nova dessa categoria nem de qualquer outra. Com base nisso, e com a visibilidade do repositorio remoto confirmada como publica, o push foi autorizado e realizado: branch `v9/fase1-local`, avancando `cea8c775..a0c6e8ad` (24 commits), mais as tags de congelamento ja existentes. Nenhum force push, nada enviado pra branch principal. Este documento (Secao atual) e o script da Secao 7, apos a revisao bloqueante de 13 pontos e a reconciliacao real dos dois achados em aberto, foram reunidos num unico commit local limpo e TAMBEM publicados: branch `v9/fase1-local`, avancando `a0c6e8ad..8bc373a7`. Mesmas duas varreduras de segredos (tracked+staged+historico completo, todas as refs) refeitas antes deste push, com o mesmo resultado: PASS nas mesmas 4 categorias, FAIL so no IP do operador -- confirmado, por verificacao direcionada (`git show 8bc373a7`), como 0 ocorrencias no commit publicado nesta revisao; a unica ocorrencia continua sendo a mesma de antes desta sessao. Nenhum force push, nada enviado pra branch principal.

## 12. Custos e versoes

**Custo.** Acumulado total desde o relogio original da campanha, nunca reiniciado: US$45,71 (apos a coleta complementar de RTT/initcwnd, Secao 4). So esta janela oficial (lancamento ao fim, ~6h09min): ≈US$8,82. So a coleta complementar de RTT/initcwnd: ≈US$0,59. Teto desta janela: US$80 (trava de seguranca de processo, nunca atingida).

**Versoes reais.** Node.js (servidor de autorizacao): `node:24-alpine` (imagem pinada, sha256 verificado). Python (clientes/servidores, AL2023): **3.9.25** (confirmado via pin de `thesis/scripts/requirements.txt` e observacao direta no controle e nos clientes). Go (gateway): `go1.27.3` (`toolchain_build_metadata.go_tag` real do manifesto, Secao 11). Java: `eclipse-temurin:17-jre` -- **inferida do codigo (`insurance-server-lambdas/build/docker/optimized/Dockerfile:1`), nao registrada diretamente pelo pipeline da campanha**. Bouncy Castle: `org.bouncycastle:bcpkix-jdk18on:1.79` -- **inferida do codigo (`insurance-server-lambdas/build.gradle:112`), nao registrada diretamente pelo pipeline da campanha**.

**Retries.** 0 de 320 execucoes e 0 de 160 aquecimentos precisaram de qualquer retry de transporte -- a correcao funcionou, mas nao foi exercitada sob estresse real nesta janela especifica.

## Referencias

`thesis/results/v9/DECISIONS.md` -- registro completo de todas as decisoes desta fase.

# Relatório Consolidado da v7 — Tamanho e Latência de três perfis criptográficos (Clássico, PQC, Híbrido) no fluxo OPIN

**Estado**: versão final da v7. Substitui integralmente a v5 (tamanho e latência com apenas assinatura migrada) e a v6 (troca de chave TLS medida isoladamente), que passam a ter o mesmo status histórico das versões v1–v4.

**Origem dos números**: todos os valores deste relatório foram recalculados do zero a partir dos arquivos brutos `runs/run01..10*.json` (378 arquivos, incluindo os 18 de aquecimento da latência), sem usar como referência os `median_metrics.json` já existentes; o resultado dessa auditoria independente está na Seção 7. Nenhuma execução foi refeita para este relatório: ele consolida dados coletados em 12/09/2026.

---

## 1. Resumo dos resultados

- **Tamanho é determinístico.** As 60 execuções de cada perfil (6 cenários de latência × 10 execuções) produziram exatamente os mesmos bytes em todas as métricas de tamanho: spread de 0,00% em todos os 18 cenários/perfis. A latência de rede injetada não altera nenhuma métrica de tamanho.
- **O custo do handshake mTLS cresce de {{hs_classic}} bytes (Clássico) para {{hs_pqc}} (PQC, {{hs_ratio_pqc_classic}}) e {{hs_hybrid}} (Híbrido, {{hs_ratio_hybrid_classic}}).** O Híbrido paga {{hs_ratio_hybrid_pqc}} o handshake do PQC.
- **O JWT médio passa de {{jwtmean_classic}} bytes para {{jwtmean_pqc}} (PQC) e {{jwtmean_hybrid}} (Híbrido)**, isto é, {{jwt_ratio_pqc_classic}} e {{jwt_ratio_hybrid_classic}} o tamanho do Clássico.
- **OPINsize com a fórmula original (três termos)**: {{opin0_classic}} bytes (Clássico), {{opin0_pqc}} (PQC), {{opin0_hybrid}} (Híbrido). **Com a fórmula estendida (novo termo de PKI/CRL)**: {{opin1_classic}}, {{opin1_pqc}} e {{opin1_hybrid}} bytes — acréscimos de +{{dpct_classic}}, +{{dpct_pqc}} e +{{dpct_hybrid}}, respectivamente (Seção 3.2).
- **Latência (T_fluxo)**: a ordem Clássico < PQC < Híbrido vale em todos os 6 cenários de latência emulada, pelas medianas. Clássico e PQC têm distribuições totalmente separadas em todos os cenários; PQC e Híbrido têm intervalos [mín., máx.] que se sobrepõem em todos os 6 cenários, embora as medianas e um teste de postos exato apontem o Híbrido acima do PQC em todos eles (Seção 4.3).
- **A diferença de latência entre Clássico e PQC/Híbrido é praticamente constante (de {{lat_gap_cp_min}} a {{lat_gap_cp_max}} s para o PQC), não proporcional à latência de rede**, e não deve ser atribuída apenas aos algoritmos: o desenho do assinador ML-DSA-65 do cliente de teste tem custo próprio de processo (Seção 6).
- **Decomposição por participante**: AS e RS, antes colapsados em "Outros" por um artefato do roteamento via proxy, foram separados com uma captura pontual (uma execução por perfil, fora do protocolo estatístico oficial) que reconcilia exatamente com os totais já commitados; os bytes do handshake continuam sem decomposição por direção (Seção 3.3).

---

## 2. Metodologia

### 2.1. O que foi medido

Um fluxo completo do Open Insurance Brasil (OPIN), executado por um cliente de teste (`opin_flow.py`) contra um protótipo de servidor de autorização (AS), um servidor de recursos (RS) e um gateway mTLS: consentimento, pedido de autorização (PAR), login automatizado, troca de código por token e consulta a recursos. Cada execução completa tem **{{n_req}} requisições HTTP** em dois sub-fluxos, **{{n_mtls}} conexões mTLS** (três pools de conexão por sub-fluxo), **{{n_jwt}} JWTs** trafegados, **{{n_jwk}} buscas de JWKS** e **{{n_pki}} buscas de certificados de CA** ({{n_root}} da raiz e {{n_issuer}} da emissora).

### 2.2. Os três perfis

| Perfil | Assinaturas | Troca de chave TLS |
|---|---|---|
| Clássico | RSA (PS256 / RS256) | ECDHE clássico (curvas P-521, P-384, P-256) |
| PQC | ML-DSA-65 puro (NIST FIPS 204) | MLKEM1024 puro, sem componente clássico |
| Híbrido | RSA e ML-DSA-65 combinados (esquemas descritos em `ARCHITECTURE.md`) | X25519MLKEM768 (X25519 + ML-KEM-768) |

A criptografia de conteúdo dos tokens (JWE com RSA-OAEP no `id_token`) permanece clássica nos três perfis: não existe hoje padrão JOSE/COSE para cifragem pós-quântica de tokens, o que impede a migração dessa camada (ver `thesis/docs/Cruzamento_SAD_vs_Experimentos.md`).

### 2.3. Unificação pelo `tls_kem_proxy`

O cliente Python de teste não negocia os grupos de troca de chave `MLKEM1024` e `X25519MLKEM768`. Na v7, **os três perfis, inclusive o Clássico**, passam pelo mesmo cliente TLS em Go (`tls_kem_proxy`), variando apenas a curva pedida. Isso elimina a variável de confusão das versões anteriores (parte de qualquer diferença entre perfis vinha de qual implementação de cliente TLS estava em uso, não do algoritmo). Detalhes em `TLS_KEM_Proxy_Architecture.md`.

### 2.4. Protocolo de coleta

- **6 cenários de latência** (0, 14, 30, 140, 225 e 320 ms) × **10 execuções** × **3 perfis**, para tamanho e para latência, nessa ordem (tamanho completo, sabatina, aprovação; depois latência).
- **Latência emulada** com `tc`/`netem` na interface `eth0` do contêiner do gateway (atraso aplicado ao tráfego de saída do gateway).
- **Aquecimento**: cada cenário de latência tem uma execução de aquecimento (`run00_warmup.json`), sempre descartada. A troca de perfil criptográfico só é feita por `switch_crypto_profile.py`, que espera o ambiente assentar (5 execuções completas descartadas) antes de qualquer medição.
- **Relógio monotônico** para o T_fluxo (tempo do fluxo completo), sem remoção de valores atípicos de nenhum tipo; execuções repetidas por falhas conhecidas contariam apenas o tempo da tentativa bem-sucedida. Na v7 nenhuma execução precisou ser repetida.
- **Convenção de arquivos**: os `runs/run*.json` são a fonte primária; `median_metrics.json` e os relatórios `.md` por cenário são derivados. Este relatório e o `report_data_v7.json` são derivados dos `runs/`.
- **Estrutura**: `thesis/results/v7/size/experiment{1,2,3} - {Classic,PQC,Hybrid}/<cenário>ms/` e `thesis/results/v7/latency/...`.

> **Nota técnica — o que "tamanho" mede.** `handshake_bytes` é a contagem de bytes na camada de conexão bruta do gateway (leitura + escrita, ClientHello até o Finished), mediana das {{n_mtls}} conexões de cada execução. Os bytes por participante são contados na camada de aplicação (cabeçalhos HTTP + corpo), e não incluem cabeçalhos TLS/TCP/IP nem o handshake. O tamanho de JWT é o comprimento do token (sem cabeçalhos HTTP).

---

## 3. Resultados de tamanho

### 3.1. Tamanho por artefato

Valores idênticos nos 6 cenários de latência (spread de 0,00% nas 60 execuções de cada perfil):

{{table:size_main}}

Razões entre perfis (cada coluna calculada sobre a linha correspondente da tabela anterior; "Saída dos servidores" é o total de bytes que o cliente recebe, ver Seção 3.3):

{{table:size_ratios}}

### 3.2. OPINsize com a fórmula estendida

A equação original de tamanho do fluxo (equivalente à Eq. 3.1 de Schardong et al., 2022) soma três termos. Esta consolidação a estende com um quarto, para os certificados de Autoridade Certificadora que o fluxo baixa e que já eram medidos, mas nunca entravam na soma:

```
OPINsize = N_mTLS × handshake_bytes + N_JWT × JWT_size + N_JWK × JWK_PK_size + N_PKI × PKI_bytes
```

com N_mTLS = {{n_mtls}}, N_JWT = {{n_jwt}}, N_JWK = {{n_jwk}} e N_PKI = {{n_pki}}. `PKI_bytes` é o tamanho médio, em bytes, dos dois certificados de CA servidos (raiz e emissora), no formato em que trafegam (PEM). A justificativa completa da extensão está em `ARCHITECTURE.md`, Seção 7 (e `DECISIONS.md`, Decision 7).

{{table:opin}}

Razões entre perfis, antes e depois da extensão:

{{table:opin_ratios}}

Leitura dos resultados:

- O termo de PKI acrescenta {{t_pki_classic}} bytes ao Clássico (+{{dpct_classic}}), {{t_pki_pqc}} ao PQC (+{{dpct_pqc}}) e **{{t_pki_hybrid}} ao Híbrido (+{{dpct_hybrid}})**.
- No Híbrido, o termo de PKI é **{{hyb_pki_over_jwk}} o termo de chave pública JWK** (que a fórmula original já somava) e equivale a {{hyb_pki_over_hs}} do termo de handshake. No PQC, o termo de PKI é {{pqc_pki_over_jwk}} o de JWK. No Clássico, {{cls_pki_over_jwk}}.
- O PQC tem o menor acréscimo relativo porque, neste protótipo, os certificados de CA do perfil PQC têm chave de titular ML-DSA-65 mas continuam assinados por uma CA RSA (desenho deliberado da Etapa 3.1); no Híbrido, os certificados de CA carregam as duas assinaturas.
- Incluir o termo de PKI **aumenta a distância do Híbrido ao PQC** de {{opin0_up_hybrid_pqc}} para {{opin1_up_hybrid_pqc}}, e **reduz a razão PQC/Clássico** de {{opin0_ratio_pqc_classic}} para {{opin1_ratio_pqc_classic}}; a razão Híbrido/Clássico praticamente não muda ({{opin0_ratio_hybrid_classic}} → {{opin1_ratio_hybrid_classic}}).

**Como o termo de PKI foi validado sem nova medição.** Os tamanhos dos certificados de CA vêm dos arquivos PEM que o gateway serve (`mock-service-os/certs/`), e foram confrontados com o volume de resposta HTTP já medido nos dados brutos (participante "PKI/CRL"). O volume medido menos o corpo dos {{n_pki}} certificados dá um enquadramento HTTP de exatamente {{frame_each}} bytes por resposta, **idêntico nos três perfis** — o que só é possível se o corpo servido for exatamente o arquivo usado no cálculo:

{{table:pki_detail}}

**Sensibilidade.** Usar diretamente o volume de resposta HTTP medido (corpo + {{frame_each}} bytes de enquadramento por certificado), em vez do corpo PEM, muda o acréscimo em menos de 1 ponto percentual:

{{table:sens}}

### 3.3. Decomposição por participante e por direção

Os dados brutos agregam os bytes de cada execução em três participantes: o **Cliente**, um participante colapsado ("Outros", AS e RS somados — o cliente de teste classifica cada chamada pelo endereço da URL, e na v7 todas as chamadas passam pelo proxy local `127.0.0.1:8443`, então o host real nunca chega a essa classificação) e o **Diretório/PKI-CRL**. Essa colisão foi resolvida sem reexecutar nenhuma das 180 medições estatísticas: uma captura pontual, uma execução por perfil, fora do protocolo oficial (mesma categoria da pasta `artifacts/`), registrou o destino lógico real de cada uma das 28 chamadas (o cabeçalho `Host` que `opin_flow.py` já define para cada chamada, nunca reescrito pelo proxy, que só embaralha o endereço físico) junto com seus bytes. Isso é válido para os 180 dados já coletados porque o tamanho já está provado 0,00% de spread em 60 execuções por perfil — a repartição AS/RS de uma execução vale para todas. A metodologia completa, incluindo um problema real de ambiente encontrado no caminho (versão errada do `requests` instalada gerando bytes diferentes dos oficiais até ser corrigido), está em `DECISIONS.md`, Decision 10. Cada captura reconcilia exatamente com o total "Outros" e "PKI/CRL" já commitados (AS + RS = Outros, byte a byte, nos três perfis) — a decomposição abaixo não é uma medição nova, é a mesma medição, corretamente separada:

{{table:participants}}

Como cada byte enviado por um participante é recebido pelo outro, as linhas fecham entre si: o total enviado pelo Cliente é igual ao total recebido pelos servidores e pelo Diretório, e vice-versa (verificado em cada uma das 180 execuções de tamanho, e a reconciliação AS+RS=Outros verificada nos três perfis pela captura pontual).

Fração da saída (egress) total dos servidores por origem:

{{table:egress_share}}

**Uso para estimativa de custo.** Provedores de nuvem cobram, em geral, o dado que sai (egress). A saída por fluxo completo de cada servidor é a linha "enviado" correspondente na tabela acima; a do Cliente é a linha "Cliente — enviado". Multiplicar pelo número de fluxos esperado dá o volume mensal por participante; o preço unitário depende do provedor e não faz parte deste trabalho. O RS domina a saída dos servidores nos três perfis (a maior parte do tráfego de aplicação é a resposta das consultas de seguro, não os artefatos de autorização do AS).

**O que ainda não está disponível, mesmo depois desta captura:**

| Decomposição solicitada | Situação |
|---|---|
| Cliente × AS × RS × Diretório/PKI-CRL, enviado × recebido | **Disponível** (tabela acima), via a captura pontual de Decision 10. |
| **Bytes do handshake por direção** | **Não disponível.** O gateway conta separadamente os bytes lidos e escritos de cada conexão, mas registra apenas a soma. O crescimento do handshake nos perfis PQC e Híbrido se reparte entre as duas direções (certificado do cliente e chave pública do KEM vão do cliente ao servidor; certificado do servidor e texto cifrado do KEM vão do servidor ao cliente), mas a divisão não foi medida — nem pela captura pontual, que não instrumenta o gateway. Assim, a parcela de handshake que é egress do servidor **não está incluída** nas tabelas acima e não pode ser estimada a partir dos dados existentes; as tabelas subestimam a saída real do servidor, em proporção desconhecida. Resolver isso exigiria acrescentar `bytesRead`/`bytesWritten` à linha de log do gateway (`mock_mtls/main.go`) e uma nova captura pontual, da mesma categoria da usada aqui. |
| Bytes por endpoint específico (não só por participante) | Latência por endpoint está nos dados brutos oficiais; bytes por endpoint, só na captura pontual (`thesis/results/v7/participant_decomposition_capture_*.json`), não usada para essa granularidade neste relatório. |

A lacuna do handshake por direção permanece como limitação, sem nova coleta; a lacuna de AS/RS foi fechada nesta rodada.

---

## 4. Resultados de latência

O T_fluxo é o tempo do fluxo completo ({{n_req}} requisições), em segundos, medido com relógio monotônico. Cada célula é a mediana de 10 execuções (a execução de aquecimento é descartada).

### 4.1. Medianas por cenário

{{table:lat_matrix}}

### 4.2. Distribuição completa (18 combinações perfil × cenário)

{{table:lat_full}}

O maior spread (diferença entre máximo e mínimo, relativa ao mínimo) de todo o experimento é de {{lat_max_spread}} ({{lat_max_spread_where}}), bem abaixo do limite de 60–70% definido como ponto de parada para investigação; o spread tende a cair com a latência emulada (no Clássico, de 25,77% a 0 ms para 0,21% a 320 ms), o que é esperado, porque o tempo passa a ser dominado pelo atraso injetado e não por variações do sistema operacional e do Docker.

### 4.3. Diferenças entre perfis e hipótese T_Clássico < T_PQC < T_Híbrido

{{table:lat_deltas}}

{{table:hypothesis}}

- A ordem **Clássico < PQC < Híbrido vale em todos os {{order_holds_count}} cenários de latência**, pelas medianas. (Na v5, uma inversão a 14 ms havia sido observada e mantida como achado; ela não se repete na v7.)
- **Clássico × PQC**: distribuições totalmente separadas em todos os cenários (nenhuma execução do PQC é mais rápida que a mais lenta do Clássico); p exato do teste de postos ≤ {{p_cp_max}} em todos.
- **PQC × Híbrido**: os intervalos [mín., máx.] se sobrepõem em todos os {{hp_overlap_count}} cenários. O teste de postos exato unilateral (Híbrido > PQC) dá p ≤ {{p_hp_max}} em todos, e a diferença mediana é de {{lat_gap_hp_min}} a {{lat_gap_hp_max}} s ({{lat_hp_rel_min}} a {{lat_hp_rel_max}} sobre o PQC). Esse teste é apenas descritivo: as 10 execuções de cada perfil foram coletadas em sequência, em blocos, e não são amostras independentes; uma deriva lenta do ambiente entre os blocos poderia contribuir para a diferença.
- **Crescimento com a latência**: de 0 a 320 ms, o T_fluxo do Clássico cresce {{classic_growth}}, o do PQC {{pqc_growth}} e o do Híbrido {{hybrid_growth}}. Por isso o custo relativo dos perfis pós-quânticos encolhe quando a latência sobe: o PQC vai de {{lat_cp_ratio_0}} para {{lat_cp_ratio_320}} do Clássico, e o Híbrido de {{lat_hc_ratio_0}} para {{lat_hc_ratio_320}}.
- A diferença absoluta para o Clássico é aproximadamente constante ({{lat_gap_cp_min}} a {{lat_gap_cp_max}} s para o PQC; {{lat_gap_hc_min}} a {{lat_gap_hc_max}} s para o Híbrido) e não cresce com a latência de rede. Os dados não mostram, portanto, um custo adicional proporcional à latência atribuível ao maior handshake; mostram um custo fixo por fluxo, cuja origem principal é discutida na Seção 6.

---

## 5. Correções relevantes ao longo do caminho

Resumo dos problemas reais encontrados e resolvidos até chegar a estes dados (a investigação completa de cada um está nos `DECISIONS.md` indicados):

| Problema | Efeito | Resolução | Registro |
|---|---|---|---|
| O cliente de teste resolvia o proxy local por `"localhost"`; a tentativa via IPv6 falhava e caía para IPv4 | ~2,1 s a mais por conexão nova (6 por fluxo, ≈12,6 s), inflando artificialmente a latência dos perfis via proxy e contaminando a comparação | Trocado por `127.0.0.1`; todo o lote de latência da v6 refeito | v6 (Nível 1), Decision 3 |
| Comparar o handshake da v5 (cliente Python) com o da v6 (cliente Go) misturava o efeito do KEM com o da troca de implementação | O handshake do PQC parecia *menor* que o clássico | v7 unifica os três perfis sob o mesmo cliente Go | v6 Decision 2; v7 Decision 1 |
| A política de troca de chave por perfil quebrava a chamada interna `auth`→RS (o cliente Node.js não negocia os grupos KEM) | Falha de 100% das execuções PQC/Híbrido | Exceção deliberada por SNI (`matls-api.local`) mantém essa única conexão interna clássica; reconfirmada na v7 com correspondência 1:1 (35 handshakes clássicos, 35 aplicações da exceção) | v6 Decision 1; v7 Decision 6 |
| Degradação cumulativa do Docker Desktop e falha no "assentamento" após troca de perfil | Resíduo de ~2 s em execuções do Híbrido; primeiras execuções pós-troca lentas | Troca de perfil só por `switch_crypto_profile.py`, com aquecimento descartado | v6 Decisions 4 e 5 |
| Cabeçalhos `Host` explícitos, necessários para o roteamento através do proxy, entram nos bytes do Clássico | +376 bytes no total de aplicação do Clássico em relação à v5 (causa principal confirmada: 520 bytes de cabeçalhos; resíduo de ~144 bytes não fechado, ≈0,2%) | Registrado, sem impacto em conclusões | v7 Decision 4 |
| O `opin_flow.py` apresentava um certificado de cliente na perna local Python→proxy; o OpenSSL desta máquina passou a não conseguir carregar a chave ML-DSA-65 | Reprodutibilidade PQC quebrada após uma mudança externa de ambiente (os dados já coletados não são afetados) | O certificado deixou de ser apresentado nessa perna (o listener local nunca o exigiu) para PQC e Híbrido | v7 Decision 5 |
| Classificação do passo 8 do SAD (token de acesso) atribuía "assinatura híbrida" a um token opaco | Documentação imprecisa (não afeta dados) | Corrigida: a assinatura real está no `client_assertion`, capturado e verificado nos três perfis | `Cruzamento_SAD_vs_Experimentos.md`; `artifacts/*/README.md` Seção 6 |
| Referência normativa incorreta ("RFC 9880") num artefato PQC | Documentação | O grupo `MLKEM1024` puro está definido no Internet-Draft `draft-ietf-tls-mlkem`; corrigido | v7 Decision 9; `artifacts/pqc/README.md` |
| Agrupamento "Outros" (AS + RS) por causa do proxy local | Perda de resolução na decomposição por participante | **Corrigido** com uma captura pontual determinística (1 execução por perfil, fora do protocolo estatístico); reconciliada exatamente com os totais já commitados | v7 Decision 8 (achado) e Decision 10 (correção) |

A investigação de um resíduo da v6 (diferença de +4 conexões registradas entre v5 e v6) foi deliberadamente encerrada sem causa identificada: a v6 deixa de ser fonte oficial com esta consolidação.

---

## 6. Limitações

1. **Amostra pequena.** Cada célula tem 10 execuções. O spread chega a {{lat_max_spread}} nas latências baixas; as medianas são reportadas sem remoção de valores atípicos. Diferenças pequenas (como PQC × Híbrido, Seção 4.3) devem ser lidas com essa cautela.
2. **A latência de PQC e Híbrido inclui um custo do cliente de teste, não só do algoritmo.** O cliente assina os JWTs ML-DSA-65 chamando um contêiner Docker efêmero por assinatura (`_run_pqc_signer()`), enquanto o Clássico assina em processo (`pyjwt`). Na v5, uma decomposição direta de um fluxo PQC a 14 ms mediu 8 invocações do assinador somando de 6,2 a 11,3 s, enquanto o restante do fluxo ficava estável em 4,6 a 5,1 s (v5, latência, Decision 8). A diferença aproximadamente constante de {{lat_gap_cp_min}} a {{lat_gap_cp_max}} s entre PQC e Clássico é consistente com esse custo fixo, mas **não foi decomposta na v7**; portanto os valores de T_fluxo dos perfis PQC e Híbrido não devem ser lidos como o custo puro dos algoritmos pós-quânticos, e sim como o custo do fluxo com a arquitetura de assinatura efetivamente usada.
3. **Ambiente de laboratório.** Um único computador, Docker Desktop no Windows 11, servidores de teste (protótipo de AS/RS), latência emulada por `netem` no tráfego de saída do gateway, sem perda de pacotes nem variação de atraso (jitter). Não representa uma WAN real.
4. **Nem todo tráfego mTLS do sistema é pós-quântico.** A conexão interna `auth`→RS permanece com troca de chave clássica por desenho (exceção por SNI, Seção 5); ela não entra em N_mTLS nem em nenhuma métrica.
5. **A camada de cifragem dos tokens (JWE/RSA-OAEP) permanece clássica** nos três perfis, por ausência de padrão JOSE/COSE pós-quântico. O passo de consentimento é, por isso, apenas parcialmente migrado.
6. **Níveis de segurança diferentes entre PQC e Híbrido.** O PQC usa ML-KEM-1024 (categoria NIST 5) e o Híbrido, ML-KEM-768 (categoria 3), porque o Go só oferece ML-KEM-1024 sem componente clássico; os dois perfis não são equivalentes nesse ponto.
7. **O termo de PKI depende do fluxo como implementado.** O cliente de teste baixa os certificados de CA no início de cada sub-fluxo, sem cache (N_PKI = {{n_pki}}); um cliente real com cache pagaria menos. A fórmula mantém N_PKI explícito justamente para permitir outros valores. O mesmo vale para N_JWK = {{n_jwk}}.
8. **Tamanhos de aplicação não incluem a sobrecarga TLS/TCP/IP** e o handshake não tem decomposição por direção (Seção 3.3); o OPINsize é um modelo do custo dos artefatos criptográficos, não igual ao tráfego total de rede.
9. **Ferramentas em versão de pré-lançamento ou experimental**: o cliente TLS e os verificadores de artefatos usam Go 1.27 (candidata a lançamento, `golang:1.27-rc-alpine`) e o suporte a ML-DSA-65 do WebCrypto do Node 24 é marcado como experimental.
10. **Cobertura do SAD.** Não foram implementados SSA, DCR, trilha de auditoria com hash (SHA-256 → SHA-384) nem revogação (CRL/OCSP); ver `Cruzamento_SAD_vs_Experimentos.md`.
11. **Artefatos criptográficos** (`artifacts/`) são capturas de uma única amostra por perfil, com verificação criptográfica reproduzível, não estatísticas.
12. **Referência bibliográfica.** A Eq. 3.1 de Schardong et al. (2022) é citada como referência da fórmula original; a entrada bibliográfica completa deve ser inserida pelo autor na tese.

---

## 7. Confiabilidade e auditoria independente

Antes de escrever este relatório, todas as métricas foram recalculadas do zero a partir dos arquivos brutos, sem consultar os agregados existentes (`thesis/scripts/audit_v7_from_raw.py`; saída completa em `thesis/results/v7/audit_recompute_from_raw.txt`):

| Verificação | Resultado |
|---|---|
| Tamanho: mediana, mínimo, máximo, spread e valores individuais de 4 métricas escalares e de 6 leituras de participante, nos 18 cenários/perfis, contra `median_metrics.json` e `MEDIAN_REPORT.md` | 0 divergências |
| Latência: mediana, mínimo, máximo, média, desvio-padrão, spread, desvios absolutos e valores individuais, nos 18 cenários/perfis, contra `median_metrics.json` e `report.md` | 0 divergências (um único alerta, de arredondamento na sexta casa decimal exibida no relatório de Híbrido/30 ms, verificado como formatação: a mediana de dois valores de 6 casas cai na sétima casa) |
| Consistência interna de cada uma das 180 execuções de tamanho | {{n_req}} requisições; {{n_jwt}} JWTs; {{n_mtls}} handshakes; bytes enviados pelo Cliente = bytes recebidos pelos demais; total = enviado + recebido pelo Cliente; certificado de cliente com o tamanho esperado do perfil |
| Consistência interna de cada uma das 180 execuções de latência | 28 chamadas; nenhuma repetição; tempo desperdiçado nulo; tempo bruto = tempo medido; carimbos de tempo monotônicos |
| Constância entre cenários de latência (tamanho) | Todas as métricas idênticas nos 6 cenários, por perfil |
| Resíduo de v5/v6 | Nenhum: os 378 arquivos brutos foram gerados entre 12/09/2026 11:38 e 18:19 (UTC), sem carimbos duplicados; as únicas menções a pastas antigas são a linha-modelo dos relatórios `MEDIAN_REPORT.md`, que cita a convenção da v5 |

As tabelas deste relatório foram geradas por `thesis/scripts/compute_v7_report_data.py` a partir dos mesmos arquivos brutos (saída em `thesis/results/v7/report_data_v7.json`).

---

## 8. Onde estão os dados e documentos relacionados

- Dados brutos: `thesis/results/v7/size/` e `thesis/results/v7/latency/`
- Dados derivados deste relatório: `thesis/results/v7/report_data_v7.json`
- Auditoria: `thesis/scripts/audit_v7_from_raw.py`, `thesis/results/v7/audit_recompute_from_raw.txt`
- Arquitetura da v7 e justificativa da fórmula estendida: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- O proxy de troca de chave: [`TLS_KEM_Proxy_Architecture.md`](TLS_KEM_Proxy_Architecture.md)
- Artefatos criptográficos reais, com prova verificável: [`artifacts/classico/`](artifacts/classico/README.md), [`artifacts/pqc/`](artifacts/pqc/README.md), [`artifacts/hybrid/`](artifacts/hybrid/README.md)
- Decisões e correções: [`DECISIONS.md`](DECISIONS.md)
- Cobertura do SAD: [`thesis/docs/Cruzamento_SAD_vs_Experimentos.md`](../../docs/Cruzamento_SAD_vs_Experimentos.md)

---

## Glossário

| Termo | Significado |
|---|---|
| **OPIN** | Open Insurance Brasil, o ecossistema de compartilhamento de dados de seguros. |
| **AS / RS** | Servidor de autorização / servidor de recursos. |
| **mTLS** | TLS com autenticação mútua (o cliente também apresenta certificado). |
| **KEM** | Mecanismo de encapsulamento de chave; ML-KEM é o padrão pós-quântico (FIPS 203). |
| **ML-DSA-65** | Assinatura digital pós-quântica (FIPS 204). |
| **Híbrido** | Combinação de um algoritmo clássico e um pós-quântico, exigindo que ambos sejam quebrados para comprometer o resultado. |
| **JWT / JWS / JWE / JWKS** | Token JSON assinado / sua forma assinada / sua forma cifrada / conjunto de chaves públicas publicado. |
| **PKI / CRL** | Infraestrutura de chaves públicas / lista de revogação; aqui, os certificados de CA baixados no fluxo. |
| **T_fluxo** | Tempo do fluxo completo, medido com relógio monotônico. |
| **Spread** | (máximo − mínimo) / mínimo, em percentual. |
| **Egress** | Dados que saem de um participante (base da cobrança de tráfego em nuvem). |

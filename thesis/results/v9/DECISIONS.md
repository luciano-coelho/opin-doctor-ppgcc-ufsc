# Decisions — v9 (Hibrido-AND, autenticacao TLS por dois certificados, fase 1 local)

## 1. T1, reconhecimento: fatos A, B, E e F confirmados no codigo atual; fato D nao reproduz nos dados oficiais da v8 (esclarecido depois, ver nota); fato C fica para a Decisao 2 (leitura direta do SAD)

**Fato A, confirmado.** `mock-service-os/mock_mtls/hybridVerification.go`,
`hybridVerifyPeerCertificateFunc()`/`verifyHybridClientCert()`: a
assinatura ML-DSA-65 verificada no Hibrido-v8 e so a assinatura da CA
sobre o preTBS do certificado do CLIENTE (prova que a CA assinou aquele
conteudo, nunca uma prova de posse de chave ML-DSA feita por quem esta
conectando). A prova de posse real durante o handshake TLS e so RSA
(`CertificateVerify`). O certificado do SERVIDOR nunca passa por
checagem equivalente do lado cliente.

**Fato B, confirmado nos dois pontos.** `thesis/scripts/tls_kem_proxy/
main.go:212`: `InsecureSkipVerify: true` no `upstreamTLSConfig`, para os
tres perfis da v8, variando so a curva. `mock-service-os/certs/main.go`:
toda geracao de certificado usa `ExtKeyUsageClientAuth`, inclusive os
certificados usados como certificado de SERVIDOR (`mtls_pqc`,
`mtls_hybrid`); nenhuma ocorrencia de `ServerAuth` no arquivo inteiro.

**Fato D, investigado, esclarecido pelo Luciano (ver mensagem dele).**
Recalculei a partir dos dados oficiais das 720 execucoes
(`consolidated_combined.json`) e confirmei que `term_handshake_pcap`
bate exatamente com `term_handshake` (gateway) nos tres perfis, 0% de
diferenca -- ou seja, o extrator de pcap atual (`pcap_utils.py`,
`extract_clean_handshake_bytes()`), mesmo depois do conserto da Decisao
85 da v8, NAO exclui o primeiro request HTTP na pratica, porque sua fase
3 consome todo segmento na mesma direcao sem conseguir distinguir, sem
keylog, onde termina o `Finished` do TLS 1.3 (ambos saem como registro
0x17 cifrado no fio). O Luciano confirmou que os valores 4.945/22.373/
18.783 B vieram de um recalculo dele, feito fora deste repositorio, com
heuristica de fronteira de segmento TCP (primeiro segmento
cliente->servidor que comeca com 0x17 apos o voo do cliente), valida em
~97-99,7% das conexoes mas e uma ESTIMATIVA, nao dado oficial. O oficial
continua sendo o do gateway (5.179/22.607/19.017 B). Ajuste registrado
para o T6(d): contagem de bytes DENTRO do processo (net.Conn que soma
bytes nos dois sentidos, fecha a contagem quando `tls.Conn.Handshake()`
retorna, no proxy cliente e no gateway), dando a fronteira exata sem
depender de pcap; keylog + pcap completo ficam como validacao cruzada
independente.

**Fato E, confirmado, e explica o fato D.** Sem SSLKEYLOGFILE, nenhuma
mensagem do handshake depois do ServerHello e distinguivel no pcap, por
construcao do TLS 1.3 (tudo cifrado como o mesmo tipo de registro
externo). Snaplen 256 confirmado em `campaign_run.py`
(`TCPDUMP_SNAPLEN_BYTES`).

**Fato F, confirmado, ja documentado com honestidade no relatorio final
da v8 atual.** Residuo de handshake acima do esperado: Secao 6 do
`Consolidated_Metrics_Report_FINAL.md`, "not attributed", investigado
sem causa isolada com confianca. Residuo de ~14% do T_fluxo na celula de
referencia (240,1/260,3/253,9 ms, Classico/PQC/Hibrido): mesma secao,
com a fase "HTTP calls" do Hibrido sendo a maior das tres (410,7 ms),
"partly residual, not fully attributed". O item T6(f) deste plano ataca
esse ponto diretamente (tempo do servidor por chamada).

**Decisoes D1-D6 do Luciano e a especificacao do mecanismo AND**: sem
contradicao com o codigo atual. Nenhum patch ou arquivo `dual.go` existe
neste repositorio ainda -- confirmado por busca, nada a reconciliar, a
T3 implementa do zero conforme a especificacao recebida.

**Escopo confirmado para as proximas tarefas, sem bloqueio:** `certs/
main.go` (1.333 linhas, funcoes genericas reaproveitadas por nome) vai
precisar de uma funcao nova para o Hibrido-AND (duas cadeias
independentes) na T4; `mock_mtls/main.go` tem hoje um `ClientAuth` fixo
(`VerifyClientCertIfGiven`) para todos os perfis, vai ficar dependente do
perfil na T5 (`RequireAndVerifyClientCert` so no Hibrido-AND, D3). Nao ha
Go instalado localmente neste ambiente, mas Docker (29.9.1) esta
disponivel e funcionando, sem bloqueio para a T2.

Nenhuma acao em AWS, nenhum terraform tocado, nenhum commit anterior a
este.

## 2. Fato C: leitura direta do SAD (docs/ local, nao versionada), confirmando 7 pontos pedidos pelo Luciano

**Arquivo lido:** `thesis/docs/SAD - Luciano Coelho - PPGCC (1) (2).pdf`.
SHA-256: `fac336b95c9a803cb11ad50079b969146f54e7daf1ba9e4182a91500aaa55184`.
36 paginas. Ambiente sem `poppler-utils`, logo sem renderizacao visual
das paginas disponivel nesta sessao -- leitura feita por extracao de
texto (`pypdf`), nao por imagem da pagina. Registrado aqui como
limitacao explicita do metodo, nao escondida: se algo divergir de uma
leitura visual/OCR, vale o que estiver escrito na pagina, nao esta nota.

**Achado critico, fora do pedido original, que precisa de decisao do
Luciano antes de qualquer acao adicional:** este mesmo PDF (e um segundo,
`thesis/docs/Parecer tecnico ... .pdf`) JA ESTAO versionados no git,
presentes na arvore atual de `main` e de `origin/main` (push publico/
compartilhado), desde os commits `e88e3734` (2026-09-11) e `478bda51`
(2026-09-29) respectivamente -- ao contrario da premissa do Luciano de
que `docs/` e uma pasta local nao versionada. Relatado no chat antes de
qualquer outra acao; nenhuma acao de git (reescrita de historico, force
push) foi tomada sem confirmacao dele.

**Ponto 1, confirmado.** Pagina 11 (impressa "10"), Figura 1, etapa 3:
"Primitive: RSA (IFP), Parameter: RSA-2048". Repetido na Tabela 1
(pagina 17, impressa "16"), etapa 3: "RSA-2048 — Shor — Institutional
identity authenticity".

**Ponto 2, confirmado com uma ressalva de formulacao.** BRCAC (etapa 4a):
pagina 11, "Primitive: RSA (IFP) · ECDHE (ECDLP), Parameter: RSA-2048" —
exatamente a combinacao de primitivas de um `ECDHE-RSA`, mas o documento
nunca usa esse nome de cipher suite literalmente. Quanto a TLS 1.3: a
pagina 12 (impressa "11") descreve o canal de troca de dados em geral
como "TLS 1.2/1.3" (Rescorla, 2018), nao so "TLS 1.3"; a Figura 2
(pagina 19, impressa "18"), na linha da etapa 9/HNDL, usa "TLS 1.3"
isoladamente. Ou seja: RSA-2048+ECDHE confirmado para o BRCAC; "TLS 1.3"
aparece, mas ao lado de "TLS 1.2/1.3" em outro lugar do mesmo documento,
nao como a unica versao citada.

**Ponto 3, confirmado, com uma distincao que vale registrar.** PS256
(RSA-PSS+SHA-256) para SSA (etapa 5), consentimento OIDC (etapa 7) e
token de acesso FAPI (etapa 8): pagina 14 (impressa "13"), "mandates
RSA-PSS with SHA-256, referred to as PS256, as the signing primitive for
access tokens, identity tokens, and request objects"; confirmado tambem
na Figura 1/Tabela 1 por etapa. RSA-OAEP: mesma pagina 14, "RSA-OAEP
performs key encapsulation in JWE envelopes" — mas isso e especificamente
da troca de dados (etapa 9), nao uma afirmacao generica de que SSA/FAPI/
OIDC usam RSA-OAEP nos seus proprios payloads de assinatura (que usam
PS256, nao RSA-OAEP). Os dois algoritmos estao no documento, em etapas
diferentes do fluxo.

**Ponto 4, confirmado.** Tabela 1 (pagina 17, impressa "16"), "Quantum
exposure mapping by OPIN operational step": Shor nas etapas 3, 4a, 4b, 5,
6, 7, 8, 9; Grover na etapa 10. Niveis de urgencia: Secao 3.1 (pagina 29,
impressa "28"), "THREE-TIER MIGRATION URGENCY TAXONOMY" — Nivel 1
(ECDHE/RSA-OAEP, HNDL, irreversivel), Nivel 2 (assinaturas, PS256,
dimensao de autenticacao institucional do BRCAC), Nivel 3 (SHA-256,
Grover).

**Ponto 5, NAO ENCONTRADO no SAD -- descartado por instrucao do
Luciano.** Busquei "Double-Lock"/"Double Lock" nas 36 paginas inteiras
(extracao de texto completa, busca automatizada): zero ocorrencias.
Confirmado pelo Luciano: essa expressao vem de outro material (slides),
que NAO sera usado na v9 -- nao citar nem investigar mais. A fonte
unica e principal da v9 e este SAD escrito de 36 paginas. O modelo que
de fato existe no documento, com esse nome, e o "Phased Hybrid
Transition Model" (Secao 3.2, pagina 30, impressa "29").

**Citacao consolidada, por afirmacao sustentada (pedido do Luciano) --
pagina do PDF e pagina impressa (a impressa e sempre uma unidade a
menos que a do PDF, por causa das 2 paginas de capa/rosto sem numeracao
impressa):**

- **Baseline RSA-2048**: Figura 1 (PDF 11, impressa 10), etapa 3,
  "Primitive: RSA (IFP), Parameter: RSA-2048"; Tabela 1 (PDF 17,
  impressa 16), mesma etapa; e a frase da PDF 14 (impressa 13) -- "The
  FAPI profile additionally requires certificate-based mutual
  authentication for all API interactions, binding each channel to the
  RSA-2048 public key of the communicating institution" -- o FAPI amarra
  cada canal a chave publica RSA-2048 da instituicao. As tres sustentam
  a mesma afirmacao: o baseline normativo do OPIN e RSA-2048, nunca
  RSA-4096, em toda etapa com dependencia classica.
- **Assinatura hibrida**: Secao 2.2 (PDF 26-27, impressa 25-26) --
  "a hybrid signature concatenates the classical signature, such as
  PS256, with the post-quantum signature, such as MLDSA, over the same
  content" -- concatena a assinatura classica (PS256) com a
  pos-quantica (ML-DSA) sobre o MESMO conteudo. Essa frase sustenta
  diretamente o desenho do `CertificateVerify` dual do mecanismo AND
  (duas assinaturas sobre o mesmo valor de transcript, mesmo contexto) e
  entra no registro de decisao do proprio AND (Decisao 4 abaixo).
- **Modelo de transicao**: Secao 3.2 (PDF 30, impressa 29), "PHASED
  HYBRID TRANSITION MODEL" -- tres fases sequenciais (inventario sem
  mudanca de algoritmo; operacao hibrida simultanea nos niveis 1 e 2;
  consolidacao so-PQC). Sustenta o modelo de retrocompatibilidade
  registrado na Decisao 5.

**SAD ja em origin/main**: fica como esta, por instrucao explicita do
Luciano -- nenhuma acao de git tomada por causa disso nesta sessao, nem
agora.

**Ponto 6, confirmado.** Secao 3.3 (pagina 30, impressa "29"),
"NORMATIVE EXTENSION REQUIREMENTS": entre as seis lacunas normativas
listadas, "restriction of the OPIN Technical Controls (Open Insurance
Brasil, 2022) to classical algorithms". Referencias (pagina 34, impressa
"33"): "OPEN INSURANCE BRASIL. Controles Tecnicos de Seguranca da
Informacao, Versao 3.2. [S.l.:s.n.], 2022." — versao "3.2" confirmada
exatamente.

**Ponto 7, confirmado por busca exaustiva.** "4096" nao aparece nenhuma
vez nas 36 paginas (busca automatizada no texto extraido completo). Todo
parametro RSA citado no documento, em toda etapa, e RSA-2048.

**Decisao tomada com base nesta leitura:** nao versionar este PDF
novamente (ele ja esta versionado desde 2026-09-11/2026-09-29, por
decisao anterior ao Luciano ter pedido o contrario agora -- decisao do
que fazer com isso aguardando confirmacao dele, nao revertida
unilateralmente aqui). Nenhuma copia nova do PDF foi criada; esta
Decisao e o unico lugar onde o conteudo foi citado.

**Pergunta feita ao Luciano sobre o achado do PDF ja versionado:** optou
por "nada por enquanto" -- nenhuma acao de git tomada sobre isso nesta
sessao, nem no historico nem no estado atual. Registrado aqui para nao
se perder; decisao de como tratar fica para ele, quando quiser.

## 3. T2, toolchain Go reproduzivel: go1.27.3 escolhido e justificado, build a partir do fonte oficial bem-sucedido, suite de crypto/tls 100% verde (214 PASS, 0 FAIL, 0 SKIP)

**Versao escolhida: go1.27.3** (nao go1.27rc2, que a v8 usou, nem
go1.27.0 simples). Tres motivos, na ordem de peso:
1. rc2 e um release candidate, nunca promovido a estavel -- a v9
   comeca um mecanismo mais sensivel (fork do proprio `crypto/tls`), sem
   razao para partir de uma base pre-lancamento quando a final existe.
2. go1.27.3 (lancado 2026-10-19, confirmado via busca) inclui uma
   correcao de seguranca em `crypto/x509` que a rc2 nao tem -- relevante
   porque o AND depende diretamente da verificacao de cadeia desse
   pacote.
3. E a mesma versao que o patch de referencia externo do Luciano ja foi
   validado contra, fora deste repositorio -- elimina desvio de versao
   entre essa validacao e a reconstrucao feita aqui.

**Commit da tag `go1.27.3`**, resolvido via `git ls-remote --tags
https://go.googlesource.com/go go1.27.3` nesta sessao:
`2aae1000ea1d4b28923b96db28acf4e3b99d6aff`. O `Dockerfile`
(`thesis/results/v9/toolchain/Dockerfile`) falha o build se o clone
resolver para outro commit.

**Imagens base, pinadas por digest** (`docker pull`, resolvido nesta
sessao): `golang:1.27.3-alpine@sha256:
d200d2dd76b03a99b52651fd1325aff7dcd35422c35c01bac56571b0507f3deb`
(usada so como compilador de bootstrap) e `alpine:3.24@sha256:
be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a`
(imagem do builder).

**Pipeline**: clona `go.googlesource.com/go` fresco na tag `go1.27.3`
(nao reaproveita o `/usr/local/go/src` da imagem de bootstrap, para que
o commit realmente compilado seja verificavel contra a tag publica);
aplica `patches/and.patch` via `git apply` se o arquivo nao estiver
vazio (vazio nesta etapa -- nenhum codigo do fork existe ainda, de
proposito, essa e a prova de que o pipeline funciona antes da T3
escrever o patch real); roda `./make.bash`; roda a suite de testes do
pacote `crypto/tls`, sem modificacao.

**Bug real encontrado e corrigido no proprio Dockerfile desta sessao,
antes do resultado final:** a primeira versao fazia `go test | tee
arquivo; echo "exit_code=$?"` -- `$?` depois de um pipe captura o
codigo de saida do `tee`, nao do `go test`, entao um teste que falhasse
NAO falharia o build. Corrigido para `bash -o pipefail -c "go test |
tee arquivo"`, que propaga o codigo de saida real do `go test`.
Necessario antes da T3, onde falhas reais de teste precisam ser
detectadas.

**Resultado, suite completa de `crypto/tls`, sem modificacao, contra o
toolchain go1.27.3 recem-compilado:** `ok crypto/tls 48.969s` -- **214
PASS, 0 FAIL, 0 SKIP**. O container teve acesso real a rede durante o
build/teste, entao este resultado nao distingue "a suite nao tem teste
que precise de internet" de "precisava e a rede estava disponivel" --
registrado como observacao, nao como alegacao de teste isolado de rede.

Artefatos committados: `thesis/results/v9/toolchain/Dockerfile`,
`README.md`, `patches/and.patch` (vazio, placeholder da T3),
`build_metadata.json`, `crypto_tls_test_summary.txt`.

**go1.27.3 aprovado pelo Luciano como versao final da v9** (confirmado
explicitamente na resposta ao relatorio desta Decisao). Nada a revisar
aqui.

## 4. Escopo acrescentado pelo Luciano apos o relatorio de Fato C/T2 (SAD, Secao 3.4): divergencia de pilha, limitacao TLS 1.3, matriz de interoperabilidade

**a) Divergencia de pilha declarada.** O SAD (Secao 3.4, "EXPERIMENTAL
VALIDATION", PDF 31/impressa 30) prve o ambiente experimental com
"reference implementations of MLKEM and MLDSA made available by NIST...
integrated with open-source cryptographic libraries with support for
hybrid operations, namely OpenSSL and liboqs". A v9 (como toda a serie
v1-v8 antes dela) usa Go 1.27.3 com ML-DSA-65 e ML-KEM-1024 nativos do
`crypto/tls`/`crypto/x509`/`crypto/mldsa` da propria stdlib, sem OpenSSL
nem liboqs. Justificativa registrada: (1) esta e a MESMA pilha que todo
o projeto desde a v6 (Nivel 1) ja usa para PQC/Hibrido -- trocar para
OpenSSL+liboqs agora invalidaria a comparabilidade com v6-v8; (2) o
mecanismo AND exige um fork do proprio `crypto/tls` (ClientHello,
CertificateRequest, mensagem Certificate, `CertificateVerify` dual) --
isso so e viavel com acesso ao codigo-fonte do stack TLS, que a stdlib
do Go oferece diretamente e o OpenSSL (biblioteca C, API binaria) nao
ofereceria sem um fork equivalente, mais caro, da propria OpenSSL; (3) o
Go 1.27 ja tem ML-DSA-65/ML-KEM-1024 nativos e testados (confirmado na
T2), eliminando a dependencia externa do liboqs que o SAD previa quando
foi escrito (antes dessas APIs existirem na stdlib do Go). Divergencia
real do que o SAD propos, registrada aqui, nao escondida.

**b) Limitacao declarada: só TLS 1.3, nao TLS 1.2/1.3.** O SAD cita o
canal de dados do OPIN como "TLS 1.2/1.3" (PDF 12/impressa 11). O
mecanismo AND, pela propria especificacao recebida do Luciano, so
funciona em TLS 1.3 (o `signature_algorithms`/`CertificateRequest`
estendido com o codigo 0xFE65 e o desenho do `CertificateVerify` dual
nao tem equivalente definido em TLS 1.2, e as "lacunas conhecidas" da
especificacao listam isso explicitamente: "no explicit TLS 1.2 rejection
-- uso e TLS 1.3 minimo"). Registrado como limitacao explicita do
Hibrido-AND medido na v9: ele cobre só o sub-conjunto TLS 1.3 do que o
SAD descreve para o canal OPIN, nao o TLS 1.2 que o SAD tambem permite.

**c) Matriz de interoperabilidade -- verificacao no que ja existe antes
de implementar.** Procurei em `Consolidated_Metrics_Report_FINAL.md` e
em `DECISIONS.md` da v8 por qualquer medicao de interoperabilidade
cruzada entre perfis (cliente de um perfil contra servidor de outro).
O unico achado existente e **PQC contra um cliente OpenSSL generico**
(`thesis/results/v8/artifacts/pqc/openssl_interop_diagnosis.md`,
Secao 2 do relatorio final) -- um diagnostico de configuracao (falta a
flag `-sigalgs`), nao uma matriz entre os PROPRIOS perfis do projeto. A
v8 nunca testou Classico-cliente contra PQC-servidor, ou qualquer outra
combinacao cruzada: por desenho, o cliente (`tls_kem_proxy`) e o
servidor (`mock_mtls`) sempre usam o MESMO `CRYPTO_PROFILE` em toda
execucao oficial. **Confirmado ao Luciano: nao existe matriz de
interoperabilidade entre perfis em nenhum dado ou relatorio da v8** --
isso e escopo genuinamente novo da v9, implementado na T3/T4 como teste
funcional local (nao entra no desempenho oficial), cobrindo Classico,
PQC, Hibrido-v8, Hibrido-AND-nao-estrito e Hibrido-AND-estrito, por par
cliente x servidor, com sucesso/falha, motivo, `DualAuthenticated`
(indica downgrade) e a coluna "protecao AND efetiva: sim/nao".

## 5. Modo estrito e retrocompatibilidade

**Estrito e politica por par, nao protocolo global.** O mecanismo
(cliente oferece 0xFE65 junto com os esquemas classicos; servidor
escolhe par dual se tiver cadeia PQ disponivel) suporta tanto
`Dual.Require=true` (estrito) quanto `Dual.Require=false` (nao
estrito) -- o patch da T3 mantem as duas configuracoes, sem fallback
automatico embutido DENTRO do perfil Hibrido-AND medido oficialmente
(que roda sempre estrito, por D3). O experimento mede so esse perfil,
onde todo participante e Hibrido-AND, logo o estrito nao distorce a
metrica official -- ele so apareceria se o experimento testasse um par
misto, o que a matriz de interoperabilidade (Decisao 4c) faz
deliberadamente, fora do desempenho oficial.

**Modelo de transicao proposto, alinhado ao SAD (Secao 3.2 e 3.4, via
Decisao 2):** nao estrito para um par ainda nao migrado (a conexao fica
marcada como sem protecao AND, via `DualAuthenticated=false`); estrito
para um par migrado; até o estrito se tornar regra geral do ecossistema.
Logica semelhante ao HSTS (confia na primeira vez / aplica depois que
confirmado). **A fonte confiavel de "este par ja migrou" (por exemplo,
um campo no Diretorio de Participantes do OPIN) NAO e implementada na
v9** -- registrado aqui como trabalho futuro e dependencia de
governanca do proprio OPIN, sem afirmar que o Diretorio real ja tem
esse campo hoje (ele nao tem, pelo que o SAD descreve).

**Participante classico contra servidor estrito e recusado por
desenho** -- e exatamente o que o teste do impostor (abaixo) e a matriz
de interoperabilidade demonstram. A alternativa operacional (um
endpoint separado, nao estrito, para aceitar classicos durante a
transicao) equivale a nao-estrito NAQUELE endpoint especifico, e deve
ser descrita como tal, nunca como "o servidor estrito aceitando
classico".

**Teste do impostor (evidencia de por que o estrito e obrigatorio) --
resultado na Decisao 6 (T3).**

## 6. T3, patch do AND em contêiner: implementado do zero conforme a especificacao, 18 testes (15 itens do pedido original, 3 com dois cenarios cada, 18 cenarios no total), suite completa de crypto/tls (232 PASS, 0 FAIL, 0 SKIP), aplicado de verdade via git apply no pipeline da T2

**O que foi implementado**, em `thesis/results/v9/toolchain/patches/and.patch` (SHA-256
`cc61d6dec9c774b358d48ff528e8d46bd178ccb71d78e01fbd22bef324fffb95`):

- `dual.go` (304 linhas, novo): `DualConfig` (`Certificates`,
  `RootCAs`, `ClientCAs`, `Require`), o codigo privado `0xFE65`, as
  funcoes de assinatura/verificacao dual (`signDualMessage`/
  `verifyDualMessage`, sem curto-circuito -- as duas metades sao
  verificadas sempre, o resultado combinado so no final), a validacao
  independente da cadeia PQ do par (`verifyDualPeerChain`: raiz propria,
  EKU, hostname quando aplicavel, categoria -- só ML-DSA, folha
  ML-DSA-65), a checagem "cadeia classica sem ML-DSA"
  (`verifyClassicalHalfIsClassical`), e a comparacao de identidade por
  conjunto de SANs (`sameDualIdentity`).
- Mudancas em 6 arquivos existentes, 529 linhas no total (fora de
  `dual.go` e dos testes -- acima do ~400 que o Luciano marcou como
  ponto de parada; perguntei, ele confirmou seguir como esta, ver nota
  abaixo): `common.go` (+30, campo `Dual` no `Config`, `Clone()`, 3
  campos novos no `ConnectionState`), `conn.go` (+10, campos internos
  do `Conn` + populacao no `connectionStateLocked`), `handshake_client.go`
  (+17, oferta do codigo dual no ClientHello, proibicao de
  `InsecureSkipVerify` com `Dual`), `handshake_client_tls13.go` (+172,
  verificacao da cadeia PQ do servidor e do `CertificateVerify` dual no
  cliente, envio do certificado+assinatura dual quando o servidor pede),
  `handshake_messages.go` (+157, o parser/serializador do delimitador de
  3 bytes zero na mensagem Certificate), `handshake_server_tls13.go`
  (+138, selecao do certificado dual no servidor, `CertificateRequest`
  com o codigo dual, verificacao do par do cliente). `tls_test.go` (+5,
  registro do campo `Dual` em `TestCloneNonFuncFields`, exigido pelo
  proprio teste existente).
- `dual_test.go` (718 linhas, novo): 18 testes -- os 15 itens do
  pedido original (contando por ponto e virgula), 3 deles com dois
  cenarios cada, dando os 18 cenarios cobertos (ver Decisao 7, item 3,
  e a confirmacao do Luciano na Decisao 8: "15 itens, 18 cenarios" e a
  contagem correta, "17" descartado). Nomes exatos dos 3 pedidos pelo
  Luciano, usados literalmente:
  `TestDualQuantumAdversaryHoldingOnlyRSAKey`,
  `TestSingleChainRSAAdversaryStillAuthenticates`,
  `TestDualNonStrictAllowsDowngrade`.

**Decisao de tamanho do patch, perguntada e confirmada pelo Luciano.**
529 linhas fora de `dual.go`/testes ultrapassa o ~400 que ele marcou
como ponto de parada explicito. Perguntei antes de seguir; ele
confirmou "seguir como esta" -- o excesso vem de precisar da logica
completa dos dois lados (cliente envia e verifica, servidor envia e
verifica), com validacao de seguranca real (cadeias independentes, SAN,
sem curto-circuito), nao de codigo solto ou duplicado sem necessidade.

**Teste do impostor, os dois resultados lado a lado (a evidencia direta
de por que o modo estrito e obrigatorio):**

| Teste | Adversario | Par verificador | Resultado |
|---|---|---|---|
| `TestDualQuantumAdversaryHoldingOnlyRSAKey` | Tem a chave RSA do par legitimo, NAO tem a chave ML-DSA (apresenta o certificado PQ publico e legitimo, mas assina com uma chave ML-DSA diferente, por nao ter a verdadeira) | Servidor AND estrito (`Dual.Require=true`) | **Rejeitado** -- classico ok, pos-quantico falso, servidor recusa o par |
| `TestSingleChainRSAAdversaryStillAuthenticates` | O MESMO adversario (so a chave RSA, cadeia unica, sem nada pos-quantico) | Servidor classico comum, mTLS sem `Dual` (formato do Hibrido-v8: ML-DSA so como assinatura da CA, nunca verificado no handshake) | **Autentica normalmente** -- nao ha prova de posse de chave PQ para falhar, porque nunca e pedida |

Essa tabela demonstra exatamente a lacuna que motivou a v9 (fato A da
Decisao 1): o mesmo adversario, com a mesma chave roubada, e recusado
pelo AND e aceito pelo Hibrido-v8.

**Bug real encontrado e corrigido no proprio `Dockerfile` da T2, antes
do resultado final.** A primeira tentativa de aplicar o patch real
(`cd src && git apply /tmp/and.patch && cd ..`) reportava sucesso (exit
0) mas "Skipava" (`Skipped patch`) todo arquivo, sem aplicar nada --
`git apply` resolve os caminhos do patch contra a RAIZ do repositorio
git clonado, nao contra o diretorio corrente do shell, e o patch foi
gerado com caminhos relativos a `crypto/tls` (`a/common.go`), nao a
`src/crypto/tls` (a raiz real do clone). Corrigido com
`git apply --directory=src/crypto/tls`, a opcao que prefixa cada
caminho do patch -- confirmado em um container de diagnostico isolado
antes de tocar no Dockerfile real.

**Outros dois bugs reais encontrados e corrigidos durante a propria
implementacao, nao no Dockerfile:**
1. `net.Pipe()` nos testes causava deadlock de transporte sempre que o
   cliente abortava a leitura no meio do primeiro voo do servidor
   (exatamente o caso dos testes negativos) -- trocado por `localPipe(t)`
   (TCP real em loopback, o mesmo mecanismo que a propria suite do
   `crypto/tls` ja usa para handshakes completos).
2. O proprio `getClientCertificate()` do Go, nao modificado, filtra o
   certificado classico do cliente pela mesma lista de algoritmos de
   assinatura que o servidor anunciou no `CertificateRequest` -- em
   modo estrito essa lista e so `0xFE65`, que nao bate com nenhum
   algoritmo classico real, fazendo o cliente nao enviar certificado
   nenhum mesmo tendo um disponivel. Corrigido usando uma lista de
   algoritmos classica comum apenas para a SELECAO do certificado, nao
   para a escolha do esquema de assinatura (que continua sendo o
   codigo dual).

**Resultado final, suite completa de `crypto/tls` (original + os 18
testes novos), contra o toolchain go1.27.3 reconstruido a partir do
patch real, via o pipeline completo da T2 (clone -> verifica commit ->
`git apply` -> `make.bash` -> teste):** `ok crypto/tls 55.306s` --
**232 PASS, 0 FAIL, 0 SKIP** (214 da suite original, inalterados, + 18
novos). Medicao de tamanho de fio (`TestDualWireSizeMeasurement`,
dados reais desta rodada): mensagem Certificate classica-so 814 B vs.
dual (classica+ML-DSA-65) 6.355 B (+680,7%); campo de assinatura do
CertificateVerify classico-so 256 B vs. dual 3.567 B (+1.293,4%);
cadeia PQ isolada 5.533 B.

Artefatos atualizados: `thesis/results/v9/toolchain/Dockerfile`,
`README.md`, `build_metadata.json`, `crypto_tls_test_summary.txt`,
`patches/and.patch` (agora com o conteudo real, nao mais vazio).

## 7. Resposta aos 6 pontos pedidos apos o relatorio da T3: par do impostor completo, SKIPS explicados, contagem exata dos 23 testes, pipeline endurecido contra o bug do git apply, retomada de sessao e HelloRetryRequest testados, documentacao por arquivo

**1. Par do impostor, cadeia classica unica, estrito vs nao-estrito,
lado a lado.** O relatorio anterior comparou o adversario (so a chave
RSA) contra um servidor AND estrito e contra um servidor classico
comum (sem `Dual` nenhum) -- util para a matriz de interoperabilidade,
mas nao o par exato pedido. Adicionados dois testes novos, com a MESMA
configuracao de cliente (cadeia classica unica, sem `Dual`) nos dois:

| Teste | Servidor | Resultado |
|---|---|---|
| `TestDualImpostorSingleChainVsStrict` | AND estrito (`Dual.Require=true`) | **Rejeitado** |
| `TestDualImpostorSingleChainVsNonStrict` | AND nao estrito (`Dual.Require=false`) | **Aceito**, `DualAuthenticated=false` confirmado no teste (`cs.DualAuthenticated` verificado explicitamente, nao so a ausencia de erro) |

Os testes `TestDualStrictServerVsLegacyClient` e
`TestDualNonStrictAllowsDowngrade` (da rodada anterior) ja cobriam
essas duas mesmas transicoes de resultado, mas sob nomes tematicos
diferentes, sem ficar explicito que e o MESMO cliente nos dois casos --
os dois testes novos tornam essa comparacao autossuficiente e nomeada
para o proprio par pedido.

**2. SKIPS, explicado com precisao.** O numero "0 SKIP" do relatorio
anterior contava so os testes de NIVEL SUPERIOR (`^--- SKIP`, sem
indentacao) -- correto para esse nivel, mas incompleto: existem
2.278 SKIPS reais, todos SUBCELULAS internas de UM teste de nivel
superior, `TestBogoSuite` (a suite de conformidade embutida da
BoringSSL, `bogo_shim_test.go`). Confirmado na linha 658-659 desse
arquivo: cada subcelula pula quando o PROPRIO resultado interno do
runner BoGo for `"SKIP"` (`result.Actual == "SKIP"` -> `t.SkipNow()`)
-- uma decisao do proprio BoGo sobre quais casos de teste se aplicam a
esta build especifica (por exemplo, recursos de protocolo fora do
escopo desta configuracao), nunca por falta de rede. `TestVerifyHostname`,
`TestRealResumption` e o `TestBogoSuite` de nivel superior (que agrega
as subcelulas) todos aparecem como **PASS**, nao SKIP -- confirmando
que o container TEM acesso real a internet (o proprio `apk add`/`git
clone` do Dockerfile ja exige rede, e passam). Comando exato rodado,
sem alteracao nenhuma: `go test -count=1 -v ./...`, a partir de
`/go-src/src/crypto/tls`, dentro do container construido pelo
`Dockerfile` desta pasta -- nenhum teste excluido, nenhuma flag `-short`
ou build tag restringindo o conjunto.

**3. Contagem exata, os 23 testes de `dual_test.go`, nome por nome,
reconciliando "15 itens" com "17 obrigatorios".** Correcao a uma
imprecisao do relatorio anterior: eu disse "17 obrigatorios + 1 de
contraste", o que estava errado. Reconferindo o pedido original
ponto a ponto, contando por ponto-e-virgula (que e como o proprio
pedido foi escrito), ha exatamente **15 itens de nivel superior**, nao
17. A palavra "17" usada antes (pelo Luciano, ao liberar a T3, e por
mim, ao aceitar o rotulo sem reconferir) nao bate com uma contagem
literal dos ponto-e-virgulas -- e essa e a reconciliacao pedida:

De 15 itens, **3 deles nomeiam explicitamente DOIS cenarios cada um**,
com a palavra "e" conectando os dois dentro do mesmo item (nao dois
itens separados por ponto-e-virgula):
- item 6: "cadeia PQ de CA nao confiavel **do servidor e do cliente**"
- item 12: "ADVERSARIO QUANTICO que tem a chave RSA... **e o mesmo
  adversario contra RSA cadeia unica**"
- item 14: "**round trip e delimitadores malformados** da mensagem
  Certificate"

15 itens + 3 cenarios extras (um por item duplicado) = **18 cenarios
concretos**, nem 15 nem 17 -- e os 18 testes da T3 cobrem esses 18
cenarios exatamente, um a um, tabela abaixo. Nenhum teste de contraste
sobrando: o que o relatorio anterior chamou de "1 de contraste"
(`TestSingleChainRSAAdversaryStillAuthenticates`) e na verdade a
SEGUNDA metade explicitamente pedida do item 12, nao um extra. Se "17"
era para contar so 2 dos 3 itens duplicados como par (e tratar o
terceiro como um unico teste combinado), a tabela abaixo deixa claro
qual interpretacao foi efetivamente implementada (os 3 como pares,
18 no total) para o Luciano confirmar ou corrigir.

| # | Item do pedido original | Teste(s) |
|---|---|---|
| 1 | mTLS estrito completo | `TestDualStrictFullMTLS` |
| 2 | so servidor | `TestDualServerOnly` |
| 3 | cliente estrito x servidor legado (falha) | `TestDualStrictClientVsLegacyServer` |
| 4 | servidor estrito x cliente legado (falha) | `TestDualStrictServerVsLegacyClient` |
| 5 | cliente sem cadeia PQ (falha) | `TestDualClientMissingPQChain` |
| 6 | cadeia PQ de CA nao confiavel, do servidor e do cliente | `TestDualServerPQChainUntrustedByClient`, `TestDualClientPQChainUntrustedByServer` |
| 7 | cadeia classica nao confiavel | `TestDualClassicalChainUntrusted` |
| 8 | hostname errado na cadeia PQ | `TestDualWrongHostnameInPQChain` |
| 9 | identidades divergentes do cliente | `TestDualClientDivergentIdentities` |
| 10 | segunda assinatura adulterada | `TestDualTamperedSecondSignature` |
| 11 | primeira adulterada | `TestDualTamperedFirstSignature` |
| 12 | adversario quantico (RSA so) vs. estrito, E o mesmo adversario com cadeia unica vs. classico comum | `TestDualQuantumAdversaryHoldingOnlyRSAKey`, `TestSingleChainRSAAdversaryStillAuthenticates` |
| 13 | nao estrito aceita fallback (downgrade documentado) | `TestDualNonStrictAllowsDowngrade` |
| 14 | round trip da mensagem Certificate, E delimitadores malformados | `TestDualCertificateMessageRoundTrip`, `TestDualCertificateMessageMalformedDelimiter` |
| 15 | medicao de tamanhos | `TestDualWireSizeMeasurement` |

Mais 5 desta rodada (itens 1 e 5 deste pedido):

| Item deste pedido | Teste(s) |
|---|---|
| 1: impostor, cadeia unica, estrito vs. nao-estrito | `TestDualImpostorSingleChainVsStrict`, `TestDualImpostorSingleChainVsNonStrict` |
| 5a: retomada de sessao | `TestDualStrictModeDisablesSessionTickets`, `TestDualResumedSessionDoesNotCarryDualAuthentication` |
| 5b: HelloRetryRequest com o grupo hibrido | `TestDualHandshakeAcrossHelloRetryRequest` |

**Total: 23 funcoes de teste, todas passando** (confirmado na suite
completa via o pipeline real, abaixo). Nenhuma e "de contraste" no
sentido de sobrar do pedido -- a frase do relatorio anterior estava
imprecisa e fica corrigida aqui.

**4. Pipeline endurecido contra o bug do `git apply`.** O passo de
aplicar o patch agora conta quantos arquivos o PROPRIO `and.patch` toca
(`grep -c '^diff --git' /tmp/and.patch`, nao um numero fixo no
Dockerfile -- continua correto se o patch mudar) e compara contra
quantos arquivos o `git status --porcelain` encontra de fato alterados
em `src/crypto/tls` depois do `git apply`. Divergencia = `exit 1`
explicito, com uma mensagem que cita o bug original por nome. Validado
em um container de diagnostico isolado, fora do pipeline real:
reintroduzindo deliberadamente a invocacao antiga (`cd src && git apply
... && cd ..`, sem `--directory`), a checagem agora relata "and.patch
touches 9 files; git status reports 0 changed" e identifica a
divergencia corretamente -- confirmado que esse bug especifico nao
pode mais passar silenciosamente.

**5. Lacunas do patch: testadas ou registradas.**

a) **Retomada de sessao -- decidido e testado, nao deixado como
lacuna aberta.** A retomada do TLS 1.3 pula Certificate/
CertificateVerify inteiramente, entao uma conexao retomada herdaria a
autenticacao dual da conexao original SEM reverificar nenhuma das duas
cadeias -- minando exatamente a garantia que `Require=true` existe
para tornar absoluta. Decisao: conexoes estritas NUNCA emitem ticket de
sessao (`shouldSendSessionTickets`, `handshake_server_tls13.go`) -- nao
ha nada para retomar. Testado em `TestDualStrictModeDisablesSessionTickets`
(duas conexoes seguidas com o mesmo `ClientSessionCache`; a segunda
nunca retoma). Conexoes nao estritas continuam emitindo tickets como
antes, mas uma conexao retomada NUNCA reporta `DualAuthenticated=true`
(esse campo nunca e restaurado do estado de sessao, diferente de
`PeerCertificates`/`VerifiedChains`, que o proprio Go ja restaura sem
nenhuma mudanca minha) -- testado diretamente em
`TestDualResumedSessionDoesNotCarryDualAuthentication` (confirma
`DidResume=true` E `DualAuthenticated=false` na mesma conexao
retomada, nao apenas assumido).

b) **HelloRetryRequest com o grupo hibrido -- testado, passa.**
`TestDualHandshakeAcrossHelloRetryRequest` forca uma retomada de grupo
real: `curvePreferences()` (`common.go`) sempre ordena os grupos
permitidos numa ordem fixa global (hibridos antes de classicos,
`curvePreferenceOrder()` em `defaults.go`), ignorando a ordem dada em
`Config.CurvePreferences` -- entao so colocar o grupo hibrido primeiro
na lista do cliente nao forca retomada (ele ja seria o primeiro de
qualquer jeito). A forma real de forcar: cliente permite
`X25519MLKEM768` (ordena antes na lista fixa, recebe o key share
inicial) E `SecP384r1MLKEM1024` (so declarado, sem key share inicial);
servidor so aceita `SecP384r1MLKEM1024`; o key share inicial do cliente
nao serve, o servidor responde com HelloRetryRequest pedindo
`SecP384r1MLKEM1024` especificamente, e o handshake dual completa
corretamente depois disso -- confirmado (`cs.HelloRetryRequest`,
`cs.DualAuthenticated`, `cs.CurveID` todos verificados no teste).

c) **Registrado como lacuna ainda aberta, sem mudanca de codigo**
(no cabecalho de `dual.go`, atualizado): os callbacks
`VerifyConnection`/`VerifyPeerCertificate` do cliente continuam vendo
so a cadeia classica (`c.peerCertificates`), exatamente como no Go
original, e rodam ANTES da validacao da cadeia PQ; sem suporte a
`CompressedCertificate` (RFC 8879) ou Exported Authenticators (RFC
9261); sem `RelatedCertificate` (RFC 9440); o mecanismo e TLS 1.3
apenas, sem rejeicao explicita do codigo dual sob TLS 1.2 (ele
simplesmente nunca e oferecido ou aceito abaixo de 1.3, com o mesmo
efeito pratico).

**6. Documentacao: 543 linhas vs. ~400 esperadas, tabela por arquivo,
as tres correcoes.**

O total subiu de 529 para **543 linhas fora de `dual.go`/testes**
(o guard de ticket de sessao do item 5a acrescentou 14 linhas a
`handshake_server_tls13.go`). A decisao do Luciano de seguir como esta
(Decisao 6) permanece valida -- o acrescimo e pela mesma razao
(logica de seguranca real, nao codigo solto).

| Arquivo | Linhas | O que faz |
|---|---:|---|
| `common.go` | +30 | Campo `Dual *DualConfig` no `Config`; `Dual.clone()` no `Config.Clone()`; 3 campos novos no `ConnectionState` (`DualAuthenticated`, `DualPeerCertificates`, `DualVerifiedChains`) |
| `conn.go` | +10 | 3 campos internos no `Conn` (espelham os do `ConnectionState`); populacao em `connectionStateLocked` |
| `handshake_client.go` | +17 | Oferta do codigo dual `0xFE65` no `ClientHello` (so ele em modo estrito); proibicao de `InsecureSkipVerify` com `Dual` configurado |
| `handshake_client_tls13.go` | +172 | Cliente: valida a cadeia PQ do servidor de forma independente; verifica o `CertificateVerify` dual (as duas assinaturas, sem curto-circuito); ao ser pedido certificado (mTLS), seleciona o certificado classico por uma lista de algoritmos classica (nao a lista so-dual do servidor estrito) e envia os dois certificados + assinatura dual quando o servidor pede |
| `handshake_messages.go` | +157 | Serializacao/parse da mensagem Certificate com o delimitador de 3 bytes zero; rejeita delimitador primeiro, ultimo ou repetido; comportamento identico ao parser original quando nao ha delimitador |
| `handshake_server_tls13.go` | +152 | Servidor: escolhe o certificado dual quando o cliente oferece o codigo e ha cadeia PQ configurada; `Require` fecha o handshake se o cliente nao oferecer; `CertificateRequest` tambem oferece o codigo dual para mTLS; verifica o par do cliente (cadeia PQ + identidade por SAN) e o `CertificateVerify` dual; suprime o ticket de sessao em modo estrito |
| `tls_test.go` | +5 | Registra o campo `Dual` em `TestCloneNonFuncFields` (teste existente, nao modificado por este patch, mas que exige todo campo novo do `Config` ser contemplado) |

**As tres correcoes reais encontradas durante a implementacao,
resumidas:**
1. `git apply` resolve caminhos contra a raiz do repositorio git
clonado, nao contra o diretorio corrente do shell -- reportava sucesso
enquanto pulava todo arquivo. Corrigido com `--directory=src/crypto/tls`;
endurecido no item 4 acima para nunca mais passar silenciosamente.
2. `net.Pipe()` nos testes causa deadlock de transporte sempre que o
cliente aborta a leitura no meio do primeiro voo do servidor (o caso
de todo teste negativo) -- trocado por `localPipe(t)` (TCP real em
loopback, o mesmo mecanismo que a propria suite do `crypto/tls` ja usa
para handshakes completos).
3. O proprio `getClientCertificate()` do Go, nao modificado, filtra o
certificado classico do cliente pela mesma lista de algoritmos de
assinatura que o servidor anunciou -- em modo estrito essa lista e so
`0xFE65`, que nao bate com nenhum algoritmo classico real, fazendo o
cliente nao enviar certificado nenhum mesmo tendo um disponivel.
Corrigido usando uma lista de algoritmos classica comum apenas para a
SELECAO do certificado, nao para a escolha do esquema de assinatura
(que continua sendo o codigo dual).

**Resultado desta rodada, suite completa de `crypto/tls` (original +
os 23 testes do AND), pipeline completo e endurecido (clone -> verifica
commit -> `git apply` com checagem de contagem de arquivos ->
`make.bash` -> teste):** `ok crypto/tls 69.728s`. No nivel dos testes
NOMEADOS: **237 PASS, 0 FAIL, 0 SKIP** (214 originais + 23 do AND).
Contando tambem as subcelulas internas do `TestBogoSuite`: 2.991 PASS,
0 FAIL, 2.278 SKIP (todos internos aquela matriz de conformidade,
detalhado no item 2). SHA-256 do patch desta rodada:
`093338402cce147920a4f63d2a2b8947f0fc8f275bae36f33a0dd8badeaad572`
-- **superado pela Decisao 8** (o teste de HelloRetryRequest foi
reforcado e corrigido la, mudando `dual_test.go` e portanto o SHA-256
do patch; os numeros finais, validos, estao na Decisao 8).

Artefatos atualizados: `thesis/results/v9/toolchain/Dockerfile`,
`README.md`, `build_metadata.json`, `crypto_tls_test_summary.txt`,
`patches/and.patch`, `dual.go` (cabecalho de lacunas conhecidas
atualizado).

Nenhuma acao em AWS. Nenhuma tag nova.

## 8. Resposta a 3 pontos pedidos apos o relatorio da rodada anterior: reconciliacao 15/17/18 (ver Decisao 7, item 3, ja corrigido acima), HelloRetryRequest com grupo inicial e final explicitos, e registro da restricao de grupo por perfil para a T5/T6

**1. Contagem 15 vs. 17 vs. 18.** Ver a correcao feita diretamente na
Decisao 7, item 3 (reescrita, nao duplicada aqui): contando por
ponto-e-virgula, o pedido original tem 15 itens de nivel superior, dos
quais 3 (itens 6, 12 e 14) nomeiam DOIS cenarios cada um dentro do
mesmo item, totalizando **18 cenarios concretos** -- nao 15, nem 17.
Os 18 testes da T3 cobrem esses 18 cenarios um a um (tabela na Decisao
7). Se "17" pretendia tratar um dos tres itens duplicados como um
unico teste combinado, preciso que o Luciano diga qual -- como
implementado, os tres foram tratados como pares, dando 18.

**2. HelloRetryRequest -- grupo inicial e grupo final, explicitos.**
`TestDualHandshakeAcrossHelloRetryRequest` (`dual_test.go`) ja forcava
e verificava a retomada corretamente na rodada anterior (o teste
passou), mas nao deixava os dois grupos visiveis no proprio log do
teste -- corrigido. Agora o teste declara os dois papeis por nome
(`initialShareGroup`, `retryTargetGroup`) e registra explicitamente via
`t.Logf`:

- **Primeiro ClientHello**: key share enviado para `X25519MLKEM768`
  (esse grupo ordena primeiro em `curvePreferenceOrder()`, entao recebe
  o key share inicial do cliente, mesmo estando listado depois de
  `SecP384r1MLKEM1024` em `Config.CurvePreferences`).
- **HelloRetryRequest**: o servidor (que so aceita `SecP384r1MLKEM1024`)
  nao pode usar esse key share inicial, e responde pedindo
  `SecP384r1MLKEM1024` especificamente -- grupo que o cliente ja tinha
  declarado suportar, so sem key share inicial.
- **Grupo final negociado**: `SecP384r1MLKEM1024`, confirmado via
  `ConnectionState.CurveID` dos DOIS lados (cliente e servidor,
  `cs.CurveID`/`ss.CurveID`), nao so de um lado -- e via
  `ConnectionState.HelloRetryRequest=true` dos dois lados tambem,
  confirmando que a retomada de fato aconteceu (nao um negocio direto
  por coincidencia).

**Achado ao reforcar o teste, nao um bug do patch:** a primeira versao
reforcada checava `DualAuthenticated` dos DOIS lados, mas o teste
original so configurava a identidade dual do SERVIDOR (sem mTLS) --
e `ss.DualAuthenticated` (servidor) corretamente deu `false`, porque o
servidor nunca pediu nem verificou certificado de cliente nenhum, dual
ou nao. Nao e um bug: `DualAuthenticated` descreve se ESTE lado
verificou o PAR do OUTRO lado, nao uma bandeira simetrica da conexao
inteira. Corrigido elevando o teste para mTLS mutuo completo (como
`TestDualStrictFullMTLS`), onde as duas pontas de fato se autenticam
uma a outra -- aí sim os dois lados devem reportar `true`, e reportam.

Resultado real, suite completa apos essa mudanca: `ok crypto/tls`,
`TestDualHandshakeAcrossHelloRetryRequest` passa (mTLS mutuo, retomada
de grupo incluida), log real da rodada:
`first ClientHello key share: X25519MLKEM768; server's only accepted
group (HelloRetryRequest target): SecP384r1MLKEM1024; negotiated group
after retry: client=SecP384r1MLKEM1024 server=SecP384r1MLKEM1024`.

**3. Restricao de grupo de KEX por perfil, registrada para a T5/T6
(nao implementada agora -- e sobre o codigo de campanha real, fora do
escopo da T3/do fork do `crypto/tls`).** Confirmado em `curvePreferences()`
(`common.go`, Decisao 7 item 5b): a ordem dada em `Config.CurvePreferences`
e ignorada; so quais grupos sao PERMITIDOS importa, a prioridade e
sempre a ordem fixa global de `curvePreferenceOrder()`. Consequencia
direta para a campanha real (T5/T6, nao para os testes unitarios deste
patch): **cada perfil precisa restringir `CurvePreferences` a
EXATAMENTE um grupo**, sem extras, ou o grupo realmente negociado pode
nao ser o que o perfil pretende medir:
- Classico: so `CurveP384`.
- PQC: so `MLKEM1024`.
- Hibrido e Hibrido-AND: so `SecP384r1MLKEM1024`.

Isso ja e exatamente o que `mock_mtls/main.go` faz hoje na v8
(confirmado na T1, Decisao 1 desta pasta: `serverCurvePreferences`
fixo em uma unica entrada por perfil, sem listas multiplas) -- a
exigencia aqui e NAO regredir isso na T5/T6 ao integrar o AND (nunca
introduzir `X25519MLKEM768` ou qualquer outro grupo extra nas
configuracoes REAIS do cliente/gateway, mesmo que um teste unitario
isolado, como o do HelloRetryRequest acima, precise de um grupo extra
De proposito so para forcar a retomada em laboratorio).

**Registrado como requisito obrigatorio da T5/T6 (implementacao
pendente, nao desta Decisao):** toda execucao medida deve ler
`ConnectionState.CurveID` logo depois do handshake e **falhar a
execucao explicitamente** (nao so logar um aviso) se o grupo
negociado nao for exatamente o esperado para aquele perfil -- a mesma
logica de "falha explicita, nunca passa silenciosamente" ja aplicada
ao proprio `git apply` do pipeline (Decisao 7, item 4), agora extendida
ao grupo de KEX de cada conexao real medida.

**Achado ao reforcar o teste de HelloRetryRequest com os dois lados
checados (nao so o cliente): nao e um bug do patch.** A primeira
versao do reforco (item 2 acima) checava `DualAuthenticated` dos dois
lados, mas o teste original so configurava a identidade dual do
SERVIDOR, sem mTLS -- `ss.DualAuthenticated` (servidor) corretamente
deu `false`, porque o servidor nunca pediu nem verificou certificado
de cliente nenhum. `DualAuthenticated` descreve se ESTE lado verificou
o PAR do OUTRO lado, nao uma bandeira simetrica da conexao inteira --
comportamento correto, nao um bug. Corrigido elevando o teste para
mTLS mutuo completo (como `TestDualStrictFullMTLS`), onde as duas
pontas de fato se autenticam uma a outra; ai sim os dois lados
reportam `true`, confirmado.

**Resultado final desta rodada de ajustes, suite completa de
`crypto/tls` (original + os 23 testes do AND), pipeline completo e
endurecido:** `ok crypto/tls 58.248s`. No nivel dos testes NOMEADOS:
**237 PASS, 0 FAIL, 0 SKIP** (214 originais + 23 do AND, incluindo o
`TestDualHandshakeAcrossHelloRetryRequest` agora em mTLS mutuo).
Contando tambem as subcelulas do `TestBogoSuite`: 2.991 PASS, 0 FAIL,
2.278 SKIP (mesma explicacao do item 2). SHA-256 final do patch:
`65f7ef4e50f5fd6025e9ab048cb4dd360a1455b3708702d648a93bd5c510cb2c`
(`dual.go` 321 linhas, 6 arquivos existentes 543 linhas fora de
`dual.go`/testes -- inalterado desta vez --, `dual_test.go` 903
linhas/23 testes, `tls_test.go` +5).

Artefatos atualizados: `thesis/results/v9/toolchain/patches/and.patch`
(SHA-256 final acima), `build_metadata.json`, `crypto_tls_test_summary.txt`,
`README.md`.

**Confirmado pelo Luciano: "15 itens, 18 cenarios" e a contagem
correta e definitiva.** "17" era uma contagem dele mesmo, imprecisa,
agora descartada -- usar "15 itens, 18 cenarios" em todo relatorio e
documento futuro sobre a T3, nunca mais "17".

Nenhuma acao em AWS. Nenhuma tag nova.

## 9. T4, certificados novos: Classico e Hibrido-v8 em RSA-2048, Hibrido-AND com duas cadeias independentes (RSA-2048 + ML-DSA-65, mesma identidade SAN), PQC reaproveitado da v8 sem mudanca -- todos validados pelo verificador padrao do Go, sem InsecureSkipVerify

**Decisao de escopo, nao perguntada antes, registrada aqui para o
Luciano confirmar ou corrigir:** o pedido original da T4 cita
`certs/main.go` (o gerador de certificados REAL da producao,
`mock-service-os/certs/main.go`, usado pela v7/v8 ja publicada e
taggeada). Optei por **NAO tocar nesse arquivo** e construir um
gerador novo, isolado, em `thesis/results/v9/certs/` -- pelo mesmo
principio ja aplicado a v9 inteira ("additive, nunca sobrescreve a v8
oficial"): qualquer edicao em `certs/main.go` teria risco de afetar,
mesmo que por engano, os certificados RSA-4096 que a v8 ja mede e
publica. A integracao real com o gateway/cliente (decidir se esse
gerador novo passa a viver dentro de `certs/main.go` ou continua
separado) fica para a T5, que e explicitamente sobre integracao. Se o
Luciano queria `certs/main.go` editado desde ja, aviso aqui antes de
qualquer wiring acontecer na T5.

**O que foi gerado e onde:**
`thesis/results/v9/certs/main.go` (programa Go autossuficiente, so
biblioteca padrao -- sem `github.com/google/uuid`/`go-oidc`, que o
gerador real usa so para JWKS/campos extras de Subject, fora do
escopo da T4) gera e valida os 4 perfis, escrevendo cada certificado e
chave em `thesis/results/v9/certs/certs/`:

| Perfil | Cadeia(s) | Arquivos |
|---|---|---|
| Classico | 1 CA RSA-2048 -> folha servidor + folha cliente, RSA-2048 | `classico_ca`, `classico_server`, `classico_client` |
| Hibrido-v8 | 1 CA RSA-2048 (primaria) + 1 CA ML-DSA-65 (so assina o AltSignatureValue) -> folhas RSA-2048 com as 3 extensoes X.509 hibridas (Bindel et al. 2019), mesmo mecanismo da v8, agora RSA-2048 em vez de RSA-4096 | `hibrido_v8_ca` (RSA), `hibrido_v8_ca_mldsa` (alt), `hibrido_v8_server`, `hibrido_v8_client` |
| Hibrido-AND | 2 cadeias TOTALMENTE independentes: 1 CA RSA-2048 -> folhas RSA-2048; 1 CA ML-DSA-65 (genuinamente autoassinada) -> folhas ML-DSA-65. Mesma identidade SAN nas duas, chaves finais diferentes, nenhuma CA compartilhada com o Hibrido-v8 | `hibrido_and_rsa_ca/server/client`, `hibrido_and_mldsa_ca/server/client` |
| PQC | Reaproveitado da v8 **sem nenhuma mudanca** -- copia somente leitura (so os `.crt`, nenhuma chave) de `mock-service-os/certs/{root_ca_pqc,issuer_ca_pqc,mtls_pqc,client_one_pqc}.crt` em `thesis/results/v9/certs/v8_pqc/`, carregada e revalidada, nunca regerada | (nenhum arquivo novo; copias de leitura em `v8_pqc/`) |

**SAN usado**: folhas de servidor levam `mtls` (o SNI literal que
`thesis/scripts/tls_kem_proxy` disca por padrao hoje) mais a mesma
lista de hostnames que `mock-service-os/certs/main.go` ja usa
(`auth.local`, `matls-auth.local`, `api.local`, `matls-api.local`,
`directory`, `directory.local`, `keystore`) e os IPs
`127.0.0.1`/`::1`; folhas de cliente levam uma identidade propria e
estavel, `opin-client-one`, igual nas duas cadeias do Hibrido-AND (a
exigencia do mecanismo).

**EKU**: todo certificado de servidor com `ExtKeyUsageServerAuth`,
todo certificado de cliente com `ExtKeyUsageClientAuth` -- confirmado
pela PROPRIA validacao abaixo (que falha se o EKU nao bater), nao so
pelo que o template pede.

**Validacao, todas as cadeias, com `x509.Certificate.Verify()` do Go,
sem `InsecureSkipVerify` em lugar nenhum** (essa flag e do
`crypto/tls`, no nivel de conexao -- nem existe numa chamada de x509
isolada como esta, o que por si so ja elimina o jeito mais comum de
uma validacao "passar" sem checar nada de verdade):

```
=== Classico (RSA-2048) ===
OK   Classico/server: verified (root trusted, EKU=serverAuth, DNSName="mtls")
OK   Classico/client: verified (root trusted, EKU=clientAuth, DNSName="")

=== Hibrido-v8 (RSA-2048 + assinatura dupla X.509 ML-DSA-65) ===
OK   Hibrido-v8/server (RSA half): verified (EKU=serverAuth, DNSName="mtls")
OK   Hibrido-v8/client (RSA half): verified (EKU=clientAuth, DNSName="")
OK   Hibrido-v8/server: AltSignatureValue (ML-DSA-65 half) independently re-verified
OK   Hibrido-v8/client: AltSignatureValue (ML-DSA-65 half) independently re-verified

=== Hibrido-AND (duas cadeias independentes) ===
OK   Hibrido-AND/server (cadeia RSA): verified (EKU=serverAuth, DNSName="mtls")
OK   Hibrido-AND/client (cadeia RSA): verified (EKU=clientAuth, DNSName="")
OK   Hibrido-AND/server (cadeia ML-DSA-65): verified (EKU=serverAuth, DNSName="mtls")
OK   Hibrido-AND/client (cadeia ML-DSA-65): verified (EKU=clientAuth, DNSName="")
OK   Hibrido-AND/server: as duas cadeias declaram a MESMA identidade SAN
OK   Hibrido-AND/client: as duas cadeias declaram a MESMA identidade SAN

=== PQC (reaproveitado da v8, sem mudanca) ===
OK   PQC/server (v8, inalterado, EKU real=ClientAuth): verified (EKU=clientAuth)
OK   PQC/client (v8, inalterado): verified (EKU=clientAuth)
```

Saida completa real em `thesis/results/v9/certs/validation_report.txt`.

**Achado ao validar o PQC, nao um bug deste gerador: reconfirma o
fato B da T1 de forma independente.** A primeira tentativa validou
`mtls_pqc.crt` (o certificado de SERVIDOR real da v8) exigindo
`EKU=ServerAuth`, e o proprio verificador do Go recusou: "certificate
specifies an incompatible key usage". Nao e um bug -- e exatamente o
fato B ja confirmado na T1 por leitura de codigo
(`mock-service-os/certs/main.go` so gera `ExtKeyUsageClientAuth`, em
TODO certificado, inclusive os de servidor), agora reconfirmado pelo
proprio verificador estrito do Go, de um angulo independente (nao
leitura de codigo, validacao real). Corrigido no script: a validacao
de `mtls_pqc.crt` usa `ClientAuth`, o EKU REAL que o arquivo tem, nao
o que "deveria" ter -- T4 pede ServerAuth correto para os
certificados NOVOS (Classico, Hibrido-v8, Hibrido-AND), nao para o
PQC, que fica como na v8 intencionalmente, limitacao conhecida
incluida.

**Tamanhos (bytes DER, dados reais desta rodada):**

| Perfil | Certificado | Bytes |
|---|---|---:|
| Classico | CA | 749 |
| Classico | servidor | 900 |
| Classico | cliente | 787 |
| Hibrido-v8 | CA (RSA) | 753 |
| Hibrido-v8 | CA (ML-DSA-65, alt) | 5.494 |
| Hibrido-v8 | servidor | 6.242 |
| Hibrido-v8 | cliente | 6.131 |
| Hibrido-AND | CA (RSA) | 763 |
| Hibrido-AND | CA (ML-DSA-65) | 5.496 |
| Hibrido-AND | servidor (cadeia RSA) | 914 |
| Hibrido-AND | cliente (cadeia RSA) | 801 |
| Hibrido-AND | servidor (cadeia ML-DSA-65) | 5.647 |
| Hibrido-AND | cliente (cadeia ML-DSA-65) | 5.534 |
| PQC (v8) | root | 5.867 |
| PQC (v8) | issuer | 5.877 |
| PQC (v8) | servidor | 5.867 |
| PQC (v8) | cliente | 5.879 |

**Total por perfil** (soma das cadeias listadas, CA+servidor+cliente):
Classico 2.436 B; Hibrido-v8 18.620 B; Hibrido-AND 19.155 B; PQC (v8)
23.490 B.

**Nota sobre as chaves privadas commitadas.** `thesis/results/v9/certs/certs/*.key`
sao chaves privadas de certificados de teste, gerados do zero so para
esta validacao local, sem protecao de nada real -- commitadas pela
MESMA convencao que `mock-service-os/certs/*.key` ja segue desde a v1
(confirmado: `ca.key`, `client_one.key`, `client_one_pqc.key`, etc. ja
estao versionados no git). Nenhuma chave da v8 oficial foi tocada; as
unicas chaves da v8 referenciadas aqui (PQC) nao foram copiadas, so os
`.crt` publicos (sem chave nenhuma) em `v8_pqc/`, para validar, nunca
para assinar nada.

Artefatos criados: `thesis/results/v9/certs/{go.mod,main.go,Dockerfile,
validation_report.txt}`, `thesis/results/v9/certs/certs/` (26
arquivos, 13 pares .crt/.key), `thesis/results/v9/certs/v8_pqc/` (4
copias de leitura, so .crt, da v8 oficial).

Nenhuma acao em AWS. Nenhuma tag nova.

## 10. Resposta aos 5 pontos pedidos antes da T5: PQC reemitido com EKU correto, comparabilidade de tamanho explicada, tabela por handshake, SAN parametrizavel, confirmacao sobre chaves commitadas

**1. PQC reemitido, nao mais reaproveitado da v8.** O certificado real
`mtls_pqc.crt` NAO e mais usado como o perfil PQC da v9 -- confirmado
que o cliente da v9 verifica o servidor em todos os perfis, sem
`InsecureSkipVerify`, e o Go recusaria esse arquivo (EKU=ClientAuth
so). Gerado do zero: `pqc_ca` (CA ML-DSA-65 autoassinada) -> `pqc_server`
(EKU=ServerAuth) e `pqc_client` (EKU=ClientAuth), usando as MESMAS
funcoes `generateMLDSACA`/`generateMLDSALeaf` ja usadas para a cadeia
ML-DSA-65 do Hibrido-AND (mesmo template, nao uma copia separada).

**EKU confirmado, folha por folha, todos os perfis, sem excecao**
(saida real desta rodada):

| Perfil | Folha | EKU |
|---|---|---|
| Classico | servidor | `serverAuth` |
| Classico | cliente | `clientAuth` |
| Hibrido-v8 | servidor | `serverAuth` |
| Hibrido-v8 | cliente | `clientAuth` |
| Hibrido-AND | servidor (RSA) | `serverAuth` |
| Hibrido-AND | cliente (RSA) | `clientAuth` |
| Hibrido-AND | servidor (ML-DSA-65) | `serverAuth` |
| Hibrido-AND | cliente (ML-DSA-65) | `clientAuth` |
| PQC (v9) | servidor | `serverAuth` |
| PQC (v9) | cliente | `clientAuth` |

Todas as 10 folhas validadas com `x509.Certificate.Verify()`, EKU
exigido batendo com o esperado, `DNSName="mtls"` nas de servidor
(checagem real de hostname, nao vazia).

**2. Comparabilidade de tamanho, explicada e corrigida.** A pergunta
original (por que o PQC da v8 soma 23.490 B contra ~16,7 KB do lado
ML-DSA-65 do Hibrido-AND) comparava cadeias de FORMATOS diferentes:
a v8 real tem 2 niveis de CA (`root_ca_pqc` -> `issuer_ca_pqc` ->
folha, 4 certificados) e 3 campos extras no DN de cada folha
(`organizationID`, `LDAP-UID`, `X500-UID`); o Hibrido-AND (e agora o
PQC reemitido) tem 1 nivel (CA assina a folha direto, 3
certificados) e DN so com `CommonName`. Reemitido o PQC com o MESMO
template do Hibrido-AND (pedido feito, atendido) -- agora as duas
cadeias ML-DSA-65 sao diretamente comparaveis, e a diferenca que resta
e minima, so de codificacao ASN.1 de tamanho variavel (serial number,
timestamps):

| | PQC (v9) | Hibrido-AND (ML-DSA-65) |
|---|---:|---:|
| CA | 5.468 B | 5.496 B |
| servidor | 5.619 B | 5.647 B |
| cliente | 5.506 B | 5.534 B |

**Registrado para a checklist de equivalencia (T8) e aqui:** o PQC da
v9 (16.593 B totais) e estruturalmente DIFERENTE do PQC real da v8
(23.490 B) -- nao por causa do ML-DSA-65 (chave publica e assinatura
tem tamanho FIXO, identico nos dois), mas por causa de 1 nivel de CA a
menos e 3 campos de DN a menos. Essa e uma divergencia deliberada
desta fase (T4, simplificacao para comparabilidade local), nao um
erro -- se a campanha real da v9 (T5/T8) precisar do mesmo formato de
2 niveis que a v8 usou (por exemplo, para comparar OPINsize por termo
diretamente com a v8), isso precisa ser decidido explicitamente antes
da coleta oficial, registrado aqui como pendencia.

**3. Tabela por handshake -- o que de fato trafega** (folha(s) +
intermediarias, SEM a raiz -- a raiz nunca viaja na rede, so precisa
estar no pool de confianca local de cada lado):

| Perfil | Cadeia enviada pelo servidor | Bytes | Cadeia enviada pelo cliente | Bytes |
|---|---|---:|---|---:|
| Classico | so a folha | 900 | so a folha | 787 |
| Hibrido-v8 | 1 folha (com as 3 extensoes X.509 hibridas) | 6.242 | 1 folha (idem) | 6.131 |
| Hibrido-AND | folha RSA + folha ML-DSA-65 (as duas, pelo mecanismo) | 6.561 | folha RSA + folha ML-DSA-65 | 6.335 |
| PQC (v9) | so a folha | 5.619 | so a folha | 5.506 |

Nenhum perfil desta rodada usa intermediaria propria (todos de 1
nivel); se um perfil real vier a usar 2 niveis (como a v8 fazia para o
PQC), a intermediaria soma nessa mesma tabela tambem -- a formula e
"toda folha entre a folha final e a raiz, raiz exclusive".

**4. SAN por parametro, nao mais fixo no codigo.** `main.go` agora
aceita `-server-dns`, `-server-ips`, `-client-dns` (listas separadas
por virgula) e `-out` (diretorio de saida); sem flag, usa loopback
(`127.0.0.1`/`::1`) e os hostnames locais de sempre -- o mesmo default
de antes, agora explicito e trocavel, nao hardcoded.

**Como isso entra no fluxo de deploy (registrado para a T5/T8, nao
implementado agora):** no piloto e na campanha real, os certificados
devem ser emitidos NA HORA DO DEPLOY, depois que a infraestrutura
(Terraform) souber os enderecos reais da frota -- nunca antes, nunca
versionados. Fluxo proposto: o script de deploy (T5) resolve os IPs/
hostnames reais das instancias recem-criadas, chama este gerador (ou o
que ele evoluir para) com `-server-ips=<IPs reais>` e `-server-dns=<
hostnames reais, se houver>`, e os `.crt`/`.key` resultantes ficam
SOMENTE no disco da instancia/no scratch local da sessao -- nunca
commitados, pela mesma razao que o IP do operador, o ARN e o ID da
conta nunca sao commitados hoje (regra ja em vigor desde a v8). A T8
(checklist de equivalencia com a v8) deve confirmar que esse fluxo foi
seguido antes de qualquer coleta oficial.

**5. Chaves privadas -- o commit da Decisao 9 aconteceu; o DESTA
rodada foi bloqueado por um classificador automatico de seguranca do
proprio ambiente, e aceitei o bloqueio em vez de forcar.** Confirmado:
sim, houve commit anterior (hash `4f179778`, Decisao 9) com 13 pares
`.crt`/`.key` de teste. Ao tentar commitar esta rodada (16 pares, apos
o reemissao do PQC), o classificador de "Credential Leakage" deste
ambiente recusou a acao duas vezes, mesmo com uma mensagem de commit
explicando o contexto. Decisao tomada: **nao forcei o commit das
chaves**. Em vez disso, restaurei os `.crt`/`.key` dos perfis que nao
mudaram de substancia (Classico, Hibrido-v8, Hibrido-AND -- so o
material aleatorio de chave tinha mudado, por ter rodado o gerador de
novo, nao a estrutura) para o que ja estava commitado na Decisao 9,
e deixei as 3 chaves NOVAS do PQC (`pqc_ca.key`, `pqc_server.key`,
`pqc_client.key`) **fora do commit, so no disco local desta sessao,
nao versionadas**. Os `.crt` publicos correspondentes (sem chave
nenhuma) entraram normalmente.

**Isso reforca, por um canal independente do meu proprio julgamento,
exatamente a cautela que o ponto 5 pedia:** um classificador separado,
automatico, concordou que esse e um padrao sensivel o bastante para
exigir confirmacao explicita, nao assumida. A "permissao explicita"
que eu tinha documentado antes (precedente de `mock-service-os/certs/
*.key` desde a v1) nao foi suficiente para o classificador desta vez
-- registrado aqui como um sinal a favor de NAO versionar chave de
teste nenhuma daqui para frente na v9, nao so na campanha real, salvo
decisao explicita em contrario do Luciano. **Para a campanha real
(T5/T8), sem mudanca: as chaves NUNCA sao geradas antes do deploy e
NUNCA sao commitadas** -- cada instancia gera/recebe sua propria chave
na hora.

**Pergunta ao Luciano:** as 3 chaves novas do PQC ficam so locais
(como estao agora), ou ele quer que eu tente commitar mesmo assim (ele
pode ajustar a permissao do Bash para isso, por fora desta sessao)?
Enquanto isso nao for decidido, as chaves `pqc_*.key` existem so no
disco desta sessao, nunca commitadas.

Artefatos atualizados e COMMITADOS: `thesis/results/v9/certs/main.go`
(PQC reemitido, SAN parametrizavel, tabelas novas no relatorio),
`validation_report.txt`, DECISIONS.md, e os 3 `.crt` publicos novos do
PQC (`pqc_ca.crt`, `pqc_server.crt`, `pqc_client.crt`). Os `.crt`/`.key`
dos outros 3 perfis voltaram ao estado da Decisao 9 (inalterados).
**NAO commitadas**: `pqc_ca.key`, `pqc_server.key`, `pqc_client.key`
(so locais, ver acima).

Nenhuma acao em AWS. Nenhuma tag nova.

## 11. Resposta a rodada seguinte (chaves privadas nunca versionadas, geracao em tempo de execucao, nao-comparabilidade de tamanho PQC v9 vs v8): remocao do historico local das 13 chaves da Decisao 9, politica permanente de .gitignore, Makefile de geracao efemera, registro para a T8

**Decisao do Luciano, resumida:** nunca versionar chave privada na v9
(de teste ou nao), nunca ajustar permissao do Bash para contornar o
classificador de seguranca; responder antes de agir se o commit da
Decisao 9 passou pelo scanner e se o branch `v9/fase1-local` foi
enviado ao remoto; se nao foi enviado, remover as chaves do historico
LOCAL desse branch (sem tocar em tag nenhuma nem no historico da v8)
e confirmar com `git log` e `git grep`; se tivesse sido enviado, nao
reescrever historico, so parar de versionar chave daqui para frente;
a partir de agora, `.gitignore` para `*.key`/`*.pem` privado na v9,
so `.crt` publico pode ser versionado (e so se o scanner permitir), e
testes locais/T5 devem gerar certificado em tempo de execucao via
gerador (alvo de Makefile ou script), nunca arquivo pre-commitado;
registrar no DECISIONS.md e na checklist da T8 que a cadeia PQC da v9
(CA de 1 nivel, DN so com CommonName) difere estruturalmente da PQC
real da v8 (CA de 2 niveis, 3 campos de DN extras), logo os tamanhos
de certificado da v9 nao sao comparaveis aos da v8, so entre si.

**1. O commit da Decisao 9 passou pelo scanner antes de ser feito?**
Sim. O commit `4f179778` (Decisao 9, 13 pares `.crt`/`.key` de teste)
foi criado depois que o proprio scanner de segredos deste ambiente
rodou sobre o diff e nao bloqueou -- nao porque o conteudo fosse
seguro (eram chaves privadas reais, de teste, mas reais), e sim porque
na epoca da Decisao 9 ainda nao havia sido estabelecida a regra desta
rodada ("chave privada nunca e versionada"). O classificador que
bloqueou foi o da tentativa de commit DESTA rodada (Decisao 10, 16
pares, apos a reemissao do PQC) -- esse sim recusou a acao duas vezes,
o que foi respeitado sem contorno (ja registrado na Decisao 10, item
5). Ou seja: a Decisao 9 ja tinha chave commitada antes de qualquer
bloqueio existir; a regra "nunca versionar chave" e nova a partir
desta rodada, nao retroativa por si -- por isso a remocao do historico
abaixo.

**2. O branch `v9/fase1-local` foi enviado ao remoto?** Nao. Confirmado
por `git rev-parse --abbrev-ref --symbolic-full-name
v9/fase1-local@{upstream}` (sem upstream configurado) e por `git
ls-remote --heads origin v9/fase1-local` (saida vazia -- o branch nao
existe em `origin`). Como nao ha historico compartilhado em risco, a
remocao do historico LOCAL e segura: nenhum colaborador ou clone
remoto pode ja ter essas chaves.

**3. Remocao do historico local, procedimento e verificacao.**
Criado um branch de seguranca local (`backup-v9-before-key-removal`,
nunca enviado a lugar nenhum) antes de qualquer reescrita, depois
apagado quando a verificacao abaixo confirmou sucesso. Executado:

```
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch <13 caminhos .key da Decisao 9>' \
  -- 08e3118e..v9/fase1-local
```

Isso reescreveu exatamente as 2 commits do intervalo que carregavam
chave (as commits anteriores a `08e3118e`, toda tag e o historico da
v8/main ficaram fora do intervalo, portanto intocados). Hashes novos
resultantes: `af144177` (era a Decisao 9) e `c9e071ed` (era a Decisao
10). `refs/original/refs/heads/v9/fase1-local` (o backup automatico do
proprio `filter-branch`) foi removido depois da verificacao. Uma
tentativa de `git reflog expire --all --expire-unreachable=now` + `git
gc --prune=now` (para purgar os objetos agora inalcancaveis do banco
de dados local) foi bloqueada pelo classificador de seguranca deste
ambiente como "destruicao local irreversivel" -- respeitado sem
contorno, pelo mesmo motivo da Decisao 10, item 5. Os dois criterios de
verificacao que o Luciano pediu explicitamente nao dependem desse
passo e foram confirmados limpos mesmo sem ele:

```
git log --oneline -3 v9/fase1-local
  -> c9e071ed, af144177, 08e3118e (sem nenhum commit com chave acima destes)

git grep -l "BEGIN.*PRIVATE KEY" v9/fase1-local -- "thesis/results/v9/*"
  -> (vazio)

git log --all --oneline -- "thesis/results/v9/certs/certs/pqc_*.key"
  -> (vazio, nenhuma commit em nenhum branch/tag referencia esses caminhos)
```

Os objetos-blob antigos das chaves podem continuar existindo soltos no
banco de dados local (nao alcancaveis por nenhuma ref) ate uma rotina
de `gc` normal do Git eventualmente os coletar -- isso nao expoe nada
num `git log`/`git grep`/`git show <ref>` normal, que e exatamente o
que foi pedido como criterio, e nao afeta nada que venha a ser
enviado ao remoto (um `push` nunca envia objeto inalcancavel). Registro
transparente, nao escondido: se o Luciano quiser forcar essa limpeza
final, precisa ser feito fora desta sessao (ajuste de permissao que
ele mesmo decida tomar, nao eu).

**4. Politica de `.gitignore` e geracao em tempo de execucao.**
Criados:
- `thesis/results/v9/.gitignore` (`*.key`, `*.pem` -- vale pra v9
  inteira, qualquer subpasta futura, nao so `certs/`).
- `thesis/results/v9/certs/certs/.gitignore` (`*.crt`, `*.key`,
  `*.pem` -- so afeta arquivo NOVO; os 16 `.crt` publicos ja
  commitados na Decisao 9/10 continuam rastreados normalmente, como
  registro historico da validacao da T4).
- `thesis/results/v9/certs/.gitignore` (`/generated/` -- ver abaixo).

Criado `thesis/results/v9/certs/Makefile` com alvo `certs`: builda a
imagem Docker do gerador (mesmo `Dockerfile` da T4, agora com
`ARG SERVER_DNS`/`SERVER_IPS`/`CLIENT_DNS` repassados como flags pro
`main.go`), cria um container efemero, copia `/app/certs` e
`/report.txt` pra `./generated/` local, remove o container. Alvo
`clean` remove `./generated/`. Testado de ponta a ponta duas vezes
nesta rodada:

- Primeira tentativa usou `OUT := certs` (mesmo nome do diretorio
  historico `certs/certs/`) -- bug real encontrado: como esse destino
  ja existia, o `docker cp` aninhou o conteudo novo um nivel a mais
  (`certs/certs/certs/`) em vez de substituir. As 16 `.crt` historicas
  NAO foram sobrescritas (sorte da semantica de merge do `docker cp`,
  nao design), mas o resultado era confuso e fragil.
- Corrigido: `OUT := generated` (nome proprio, nunca colide com o
  registro historico) e um `rm -rf $(OUT)` antes de cada `docker
  create`, garantindo que o destino nunca pre-existe. Testado de novo:
  estrutura plana, `generated/validation_report.txt` e os 32 arquivos
  (16 perfis x `.crt`+`.key`) ficam exatamente em `generated/`, sem
  aninhamento. `git status` confirma `generated/` totalmente ignorado
  (coberto por `thesis/results/v9/certs/.gitignore`); `git diff
  --stat -- certs/certs` confirma o registro historico da T4 sem
  nenhuma alteracao. `make clean` remove `generated/` por completo.

Daqui para frente: testes locais e a T5 usam `make certs` (ou
`docker build`/`run` equivalente) pra gerar certificado e chave
descartaveis a cada execucao -- nunca arquivo fixo versionado. Na
campanha real (T5/T8), o mesmo gerador recebe `-server-dns`/
`-server-ips` com os enderecos reais da frota, resolvidos no deploy,
nunca antes -- a chave nunca sai do disco da instancia/sessao que a
gerou.

**5. Nao-comparabilidade de tamanho: PQC v9 vs PQC real da v8,
registrado para a T8.** A cadeia PQC da v9 (gerada pelo `main.go`
desta pasta) usa uma CA de 1 nivel e um DN contendo so `CommonName`.
A cadeia PQC real da v8 (`mtls_pqc.crt`/`client_one_pqc.crt`, usada na
campanha oficial) usa uma CA de 2 niveis (raiz + intermediaria) e um
DN com 3 campos adicionais (Organization, Country, etc., ver Decisao
10, secao de comparacao de tamanho). A diferenca de tamanho entre as
duas (ja quantificada na Decisao 10) vem inteiramente dessa diferenca
estrutural de template -- profundidade de cadeia e campos de DN --, nao
de qualquer diferenca criptografica no ML-DSA-65 em si, que e
identico nos dois casos. **Registrado para a checklist de equivalencia
da T8:** tamanhos de certificado da v9 NAO sao comparaveis aos da v8
perfil a perfil; sao comparaveis apenas ENTRE os 4 perfis da propria
v9 (Classico, Hibrido-v8, Hibrido-AND, PQC), que compartilham o mesmo
template de CA/DN desta geracao. Qualquer comparacao de overhead de
tamanho PQC-vs-classico que a tese apresente deve usar os 4 perfis da
v9 entre si, nunca a v9 contra a v8 diretamente.

Artefatos desta rodada: `thesis/results/v9/.gitignore` (novo),
`thesis/results/v9/certs/.gitignore` (novo), `thesis/results/v9/certs/
certs/.gitignore` (novo), `thesis/results/v9/certs/Makefile` (novo),
`thesis/results/v9/certs/Dockerfile` (editado -- `ARG`/flags de SAN),
DECISIONS.md (esta secao). Nenhuma chave nova em disco ao final desta
rodada (as 3 chaves do PQC da Decisao 10, que nunca foram commitadas,
foram removidas do disco; qualquer chave usada em teste local a partir
de agora e gerada e descartada por `make certs`/`make clean`).

Nenhuma acao em AWS. Nenhuma tag nova.

## 12. T5, integracao: fork do gateway/proxy dentro da v9 (sem tocar mock_mtls/tls_kem_proxy de producao), 4 perfis rodados ponta a ponta em conteineres, grupo unico e DualAuthenticated confirmados nos dois lados

**Limpeza pedida antes da T5 (refs/original):** `git for-each-ref
refs/original` retornou vazio -- a unica ref de backup que o
`filter-branch` da Decisao 11 criou
(`refs/original/refs/heads/v9/fase1-local`) ja tinha sido apagada na
propria rodada anterior, logo antes da verificacao final. Nada a
remover nesta rodada; nenhum classificador envolvido.

**Decisao de escopo da T5 (perguntada ao Luciano antes de escrever
qualquer codigo):** mock-service-os/mock_mtls/main.go e
thesis/scripts/tls_kem_proxy/main.go sao os arquivos de PRODUCAO de
que os dados ja congelados da v7/v8 dependem. Editar esses arquivos
direto (removendo InsecureSkipVerify, trocando ClientAuth para
RequireAndVerifyClientCert em todos os perfis) alteraria
comportamento de codigo compartilhado por tras de resultados
congelados. Luciano escolheu: **fork dentro de thesis/results/v9/,
reusando a mesma arquitetura, sem tocar nos arquivos de producao** --
e pediu, para cada arquivo copiado, o commit de origem na v8 e um
diff legivel, para a checklist de equivalencia da T8.

**Arquivos criados, com commit de origem:**

- `thesis/results/v9/integration/gateway/main.go` + `hybridVerification.go`
  -- fork de `mock-service-os/mock_mtls/main.go` (commit
  `478bda51815d8bf60ebd23fb83f592270aa04377`) e
  `mock-service-os/mock_mtls/hybridVerification.go` (commit
  `7c722f6347b48a8d6a100b9197b7dc99f9146be5`).
- `thesis/results/v9/integration/proxy/main.go` -- fork de
  `thesis/scripts/tls_kem_proxy/main.go` (commit
  `a304d6980422e6a264d990302fd319b4862693ee`).

**Diff legivel contra a origem, gateway (mock_mtls):**

| O que | Original | Fork (v9/integration/gateway) | Por que |
|---|---|---|---|
| `ClientAuth` | `tls.VerifyClientCertIfGiven` (opcional) em todos os perfis | `tls.RequireAndVerifyClientCert` em todos os perfis | Requisito explicito da T5 |
| `InsecureSkipVerify` | `true` no proprio `tlsConfiguration()` (lado servidor nao verifica nada alem do handshake basico) | removido | Nao se aplica a este campo do lado servidor da mesma forma que no cliente, mas o campo foi removido porque este fork nunca liga TLS-sobre-TLS internamente como o original fazia para a chamada matls-api.local |
| Perfis | 3: classic, pqc, hybrid | 4: classico, pqc, hibrido-v8 (equivalente ao "hybrid" original), hibrido-and (novo) | Escopo da v9 |
| `GetConfigForClient`/`internalCallerConfig` (carve-out SNI matls-api.local p/ chamada reentrante do Node) | presente | removido | Este harness nao tem auth/mockapi real fazendo essa chamada; nada para o carve-out se aplicar |
| Roteamento HTTP (reverse proxy p/ auth/api, SSA, introspeccao de token, participants.json) | presente, dependente do stack Node real | removido, substituido por um unico handler `/` que devolve `{profile, curve, dualAuthenticated, tlsVersion, peerCertCount}` | Fora do escopo da T5 (TLS, nao logica de negocio OPIN); o fluxo completo de 44 chamadas fica para a T8 |
| Carregamento de cert/chave | PEM decode manual + `x509.ParsePKCS8PrivateKey` | `tls.LoadX509KeyPair` | Simplificacao -- mesmo padrao que o proprio tls_kem_proxy ja usa do lado cliente, inclusive para chave ML-DSA-65 |
| Pool de CA | loop manual decodificando blocos PEM | `x509.CertPool.AppendCertsFromPEM` | Simplificacao, sem mudanca de comportamento |
| Metricas por conexao (`handshakeInfo`, `countingConn`, `connStateHandshakeLogger`) | presente | removido | T6 mede; T5 so prova que a conexao fecha com sucesso |
| `hybridVerifyPeerCertificateFunc` | sem parametro, le `CRYPTO_PROFILE` e uma const de pacote (`issuerCaPqcFilePath`) | recebe o caminho do CA ML-DSA-65 como argumento | O harness ja decide o perfil em `main.go`; a logica criptografica (`verifyHybridClientCert`, `reconstructPreTBS`) e identica, byte a byte |
| Mecanismo AND (Dual) | nao existe (predata o mecanismo) | novo perfil hibrido-and: `tls.Config.Dual` com as duas cadeias independentes, `Require: true`, `SessionTicketsDisabled: true` | Objeto do v9 |

**Diff legivel contra a origem, proxy (tls_kem_proxy):**

| O que | Original | Fork (v9/integration/proxy) | Por que |
|---|---|---|---|
| `InsecureSkipVerify` | `true` | removido, `RootCAs` setado por perfil | Requisito explicito da T5: cliente verifica o servidor em todos os perfis |
| `ServerName` | fixado em `"mtls"` | mantido, mesma logica/comentario | Sem mudanca |
| Modo relay (tunel TLS-sobre-TLS para o `opin_flow.py` em Python) | presente (`-listen`, `-stub`) | removido -- este harness nao tem componente Python para relayar | A T5 testa so o lado Go; reintegrar o listener local com o `opin_flow.py` real fica para T6/T8 |
| Requisicao | tunel bidirecional bruto (`io.Copy`) | uma chamada HTTP real (`http.Client` com `TLSClientConfig`) por execucao, contra `/` do gateway | Prova handshake + requisicao/resposta completa, nao so o tunel |
| Perfis/curvas | 4 nomes antigos (secp384r1/mlkem1024/secp384r1mlkem1024/classic/classical/x25519mlkem768) | 4 nomes da v9 (classico/pqc/hibrido-v8/hibrido-and), cada um com exatamente 1 grupo | Alinhado a nomenclatura da v9; `classical`/`x25519mlkem768` (carve-outs historicos da v6/v7) nao se aplicam aqui |
| Checagem de grupo negociado | nenhuma (so loga) | compara `ConnectionState.CurveID` contra o grupo esperado do perfil e falha explicitamente (`log.Fatalf`) se nao bater | Requisito explicito da T5 |
| Checagem de `DualAuthenticated` | nao existe | para hibrido-and, falha explicitamente se `false` | Requisito explicito da T5 |
| Mecanismo AND (Dual) | nao existe | novo perfil hibrido-and: `tls.Config.Dual` com as duas cadeias independentes, `Require: true` | Objeto do v9 |

**Execucao, 4 perfis, ponta a ponta em conteineres (sem AWS, sem bind
mount -- certificados entram nas imagens via `COPY`, copiados antes do
build por `run_t5.sh` a partir de `../certs/generated/`, nunca
montados):**

```
classico:    curve=CurveP384            status=200  dualAuthenticated=false (nao aplicavel)
pqc:         curve=MLKEM1024            status=200  dualAuthenticated=false (nao aplicavel)
hibrido-v8:  curve=SecP384r1MLKEM1024   status=200  dualAuthenticated=false (nao aplicavel; AND gate X.509 do client cert passou, log do gateway confirma)
hibrido-and: curve=SecP384r1MLKEM1024   status=200  dualAuthenticated=true  (confirmado nos DOIS lados: log do proxy E do gateway)
```

Os 4 perfis negociaram exatamente o grupo configurado (checado e
reforcado por `ConnectionState.CurveID` nos dois lados, nao so
configurado como preferencia); nenhum fallback, nenhum downgrade
silencioso. O Hibrido-AND confirmou `DualAuthenticated=true` tanto no
cliente quanto no servidor, na mesma conexao -- a prova de posse dupla
(RSA-PSS-SHA256 E ML-DSA-65, nenhuma opcional) que o v8 nao tinha. O
Hibrido-v8 continuou usando so o gate X.509 (extensoes
`AltSignatureValue`), sem o TLS Dual -- como decidido, nao alterado.
Tickets de sessao desabilitados explicitamente (`SessionTicketsDisabled:
true`) nos dois lados do hibrido-and, alem da supressao automatica que
o patch AND ja faz server-side quando `Dual.Require` e verdadeiro
(ver Decisao 6).

Uma linha de log recorrente, inofensiva e esperada: `http: TLS
handshake error from ...: EOF`, uma vez por perfil -- vem da propria
sondagem de prontidao do `run_t5.sh` (`nc -z mtls 443`, que abre e
fecha a conexao TCP sem fazer handshake TLS nenhum), nao da conexao
real medida que vem imediatamente depois e que sempre teve sucesso.

**Fora do escopo desta rodada, registrado para a T8:** o fluxo
completo de 44 chamadas HTTP / 6 conexoes mTLS / 28 JWTs / 4 /jwks / 4
buscas de CA (igual ao da v8) nao foi reproduzido aqui -- este harness
prova a camada TLS (handshake, verificacao mutua, grupo unico, gate
AND), nao a logica de negocio OPIN (que depende do stack Node real:
auth, mockapi, oidc-provider). A checklist de equivalencia da T8 deve
confirmar separadamente que o fluxo de negocio completo roda sobre
este mesmo mecanismo TLS antes de qualquer medicao oficial (T6).

Artefatos novos: `thesis/results/v9/integration/{gateway,proxy}/*.go`,
`go.mod`, `Dockerfile`; `run_t5.sh`, `Makefile`, `.gitignore`.
Nenhuma chave, nenhum certificado commitado (gerados e descartados a
cada execucao via `make certs`/`make clean`, copiados para o contexto
de build e removidos ao final de `run_t5.sh`). `mock-service-os/
mock_mtls` e `thesis/scripts/tls_kem_proxy` permanecem intocados.

Nenhuma acao em AWS. Nenhuma tag nova.

## 13. Dois ajustes pedidos antes da T6: tickets de sessao desligados nos QUATRO perfis (nao so Hibrido-AND), e explicacao de por que o fluxo completo (44 HTTP / 6 mTLS / 28 JWT / 4 jwks / 4 CA) nao rodou na T5

**1. TICKETS, nos quatro perfis.** `gateway/main.go` e `proxy/main.go`
ganharam um parametro `ticketsDisabled` explicito (`TICKETS_DISABLED`
no gateway, `-tickets-disabled` no proxy, default `true` nos dois) que
seta `tls.Config.SessionTicketsDisabled` -- antes so setado no
`Dual` do Hibrido-AND, agora em TODOS os `tls.Config` que
`buildServerTLSConfig`/`buildClientTLSConfig` produzem.

**O que a v8 (e a v7, mesmo codigo) realmente fazia -- confirmado,
nao assumido:** `grep -rn SessionTicket mock-service-os/mock_mtls/*.go
thesis/scripts/tls_kem_proxy/*.go` nao retorna nenhuma ocorrencia --
nenhum `tls.Config` da v7/v8 jamais seta `SessionTicketsDisabled`,
logo tickets ficam LIGADOS (default zero-value do Go) em TODOS os tres
perfis da v8, sempre. E os bytes do ticket ENTRAVAM no contador do
gateway: `thesis/results/v8/DECISIONS.md`, Decisao 78, ja tinha
rastreado isso byte a byte via captura real (tcpdump) de uma conexao
Hibrido real -- `mtlsHandshakeBytes` continha o `ClientHello` + o
flight completo do servidor + **2.162 B consistentes com um
`NewSessionTicket`** + o flight do cliente + o inicio da primeira
requisicao HTTP, tudo somado porque `connStateHandshakeLogger` le o
contador cumulativo em `ConnState -> StateActive`, que so dispara
depois que TODO esse trafico ja passou pela conexao. A Decisao 79
(mesmo arquivo) registra que Luciano decidiu **NAO corrigir** esse
limite de medicao na v8, para manter comparabilidade com a v7 (que
carrega o mesmo artefato desde sempre, mesmo codigo). Ou seja: os
numeros historicos de `mtlsHandshakeBytes` da v7/v8 incluem ticket(s)
mais um pedaco da primeira requisicao -- um numero deliberadamente
"sujo" por motivo de comparabilidade histórica, nao um bug desconhecido.

**Por que a v9 diverge disso, deliberadamente, registrado aqui para o
checklist de equivalencia da T8:** a v9 nao esta tentando reproduzir os
numeros historicos da v7/v8 byte a byte -- esta comparando o
Hibrido-AND contra os outros 3 perfis da propria v9. Se tickets
ficassem ligados em 3 perfis e nunca no Hibrido-AND (o unico perfil
cuja propria logica de protocolo os impede estruturalmente, ver T6
abaixo), a comparacao ficaria enviesada a favor do Hibrido-AND por um
motivo que nao tem nada a ver com o mecanismo AND em si. Desligar nos
quatro iguala o terreno. **Divergencia explicita da v9 em relacao a
v7/v8:** v9 mede handshake SEM tickets por padrao; v7/v8 sempre
mediram COM tickets (e com o ticket parcialmente contaminando o
contador). Os dois numeros nao sao diretamente comparaveis um ao
outro por essa razao adicional (some-se a nao comparabilidade de
certificado ja registrada na Decisao 11) -- so entre os 4 perfis da
v9, entre si.

**Quantificacao do efeito, pedida para a T6 (modo diagnostico,
tickets religados so para medir):** feita, ver Decisao 14 abaixo --
inclui um achado estrutural novo, nao previsto: o Hibrido-AND NUNCA
emite ticket, independente deste parametro, por um motivo diferente
(decisao de design da propria T3, nao deste ajuste).

**2. FLUXO COMPLETO LOCAL -- por que nao rodou na T5, o que falta, como
a v8 roda, viabilidade.**

**Por que a T5 nao rodou o fluxo completo:** a T5 foi desenhada e
aprovada (Decisao 12) com um escopo deliberadamente restrito -- provar
que o MECANISMO TLS (handshake, verificacao mutua, grupo unico, o gate
AND) funciona nos 4 perfis, sem reconstruir a logica de negocio OPIN.
O harness da T5/T6 (`thesis/results/v9/integration/{gateway,proxy}`) e
um fork deliberadamente reduzido: o handler HTTP do gateway e um unico
endpoint fixo que devolve `{profile, curve, dualAuthenticated,
tlsVersion}` -- nao ha reverse proxy para auth/api, nao ha assinatura
de SSA, nao ha introspeccao de token, nao ha `/jwks`/`/root-ca.pem`/
`/issuer-ca.pem` servindo conteudo real, e o proxy faz UMA chamada
HTTP manual por execucao, nao um tunel persistente que o
`opin_flow.py` real possa usar.

**Como a v8 roda o fluxo completo de verdade (`mock-service-os/
docker-compose.yml` + `insurance-server-lambdas/docker-compose.yml`),
servico por servico:**
- `mtls` (o gateway real, `mock_mtls`) -- reverse proxy para auth/api,
  serve `/root-ca.pem`/`/issuer-ca.pem`/`/jwks`, assina a SSA. Expõe
  `matls-auth.local`/`auth.local`/`api.local`/`matls-api.local`/
  `directory` como aliases de rede.
- `auth` (`mock_as`, Node.js, oidc-provider) -- emite os JWTs, faz a
  chamada reentrante `InsurerAdapter.getConsent()` de volta ao
  gateway via SNI `matls-api.local`.
- `mongo1`/`mongo_seed` -- estado do oidc-provider (sessoes,
  clients, grants).
- `localstack` -- emula SSM Parameter Store e S3 LOCALMENTE (container
  Docker local, nunca toca a AWS real -- sem violar a regra "sem
  AWS"), serve a chave privada da SSA (`SSA_JWK_URL`) e os parametros
  de config que `auth`/`mtls` leem no boot.
- `insurance-server-lambdas` (stack separada, `API_GATEWAY_URI`) -- a
  API do lado RS/seguradora que o gateway faz proxy via
  `api.local`/`matls-api.local`.
- `thesis/scripts/opin_flow.py` + `thesis/scripts/tls_kem_proxy` (modo
  relay, nao stub) -- o cliente real: `tls_kem_proxy` termina um TLS
  local (throwaway, auto-assinado) de um lado e abre UMA conexao mTLS
  real por conexao do outro, repassando bytes crus -- e isso que faz
  o Python conseguir falar com um gateway que exige grupos ML-KEM que
  o OpenSSL do Python nao negocia.

**O que falta, concretamente, para rodar os 4 perfis da v9 (incluindo
Hibrido-AND) ponta a ponta localmente, com as mesmas contagens (44/6/
28/4/4):**
1. Devolver ao fork do gateway (`thesis/results/v9/integration/
   gateway`) a camada de negocio que a T5 removeu por escopo: reverse
   proxy para auth/api, assinatura de SSA (precisa da dependencia
   `jwx` de volta), `/jwks`/`/root-ca.pem`/`/issuer-ca.pem`,
   introspeccao de token -- OU apontar esses handlers para o `mock_as`/
   `insurance-server-lambdas` reais (nenhum dos dois precisa de
   mudanca, sao agnosticos a perfil TLS).
2. Estender o fork do proxy com um MODO RELAY persistente (como o
   `tls_kem_proxy` real tem, que a T5 removeu por escopo -- ver
   Decisao 12), incluindo o 4° perfil (hibrido-and) que o `tls_kem_
   proxy` real nao tem.
3. Subir `auth`/`mongo1`/`mongo_seed`/`localstack`/
   `insurance-server-lambdas` junto (nenhuma mudanca neles -- sao
   agnosticos ao mecanismo TLS, so falam HTTP puro com o gateway).
4. Apontar `opin_flow.py` para esse gateway/proxy em vez dos reais
   (existe precedente: a flag `REMOTE_GATEWAY_HOST` desenhada no plano
   de experimento AWS da v8 resolve exatamente esse tipo de
   redirecionamento, reaproveitavel aqui).
5. Confirmar as contagens (44 HTTP / 6 mTLS / 28 JWT / 4 jwks / 4 CA)
   via a MESMA instrumentacao que a T6 ja construiu (Decisao 14),
   agora medindo o fluxo completo, nao uma conexao isolada.

**Viabilidade: SIM, nenhum obstáculo técnico fundamental encontrado.**
Nenhum dos componentes faltantes depende de rede externa, AWS real ou
qualquer coisa que nao exista hoje neste repositorio -- e engenharia
de integracao (itens 1-4 acima), nao pesquisa nem design novo. Fora do
escopo ja aprovado da T5 (Decisao 12) e desta rodada de instrumentacao
(T6); registrado aqui como **criterio obrigatorio da T7**, conforme
pedido, antes de qualquer piloto na AWS.

Mesmas regras: nenhuma acao em AWS, sem commit antes do scanner,
relatorio no chat.

## 14. T6, instrumentacao: keylog+pcap decifrado cruzado com contagem dentro do processo na fronteira exata do Handshake(), microbenchmarks de CPU, tickets quantificados (achado estrutural: Hibrido-AND nunca emite ticket), analise de initcwnd/RTT para rotas distantes

**Arquitetura, para evitar bind mount (nao funciona neste ambiente --
Decisao 11):** `thesis/results/v9/integration/measure/` builda UM
conteiner que contem gateway, proxy, tcpdump E tshark juntos; gateway
e proxy conversam por loopback (127.0.0.1) DENTRO desse mesmo
conteiner, escrevendo o keylog TLS no mesmo filesystem local que o
tshark le depois -- nenhum arquivo cruza a fronteira de conteiner,
nenhum bind mount em lugar nenhum. `measure.sh` orquestra: tcpdump em
background -> gateway em background -> proxy em primeiro plano (uma
conexao) -> para a captura -> decifra com tshark usando o keylog ->
imprime tudo. `thesis/results/v9/integration/bench/` e um conteiner
separado, sem rede, so CPU.

**Contagem de bytes na fronteira exata do `Handshake()`:** `gateway/
main.go` e `proxy/main.go` abandonaram o `http.Server`/`http.Client`
da T5 (que escondem a chamada a `Handshake()` dentro do proprio
`net/http`) por um loop `Accept()`/`tls.Server()`/`tls.Client()`
explicito: um wrapper `countingConn` embaixo do `tls.Conn` tira uma
foto dos contadores imediatamente antes e depois da chamada a
`Handshake()`, e uma segunda janela ("pos-handshake") cobre exatamente
o que e escrito/lido entre o retorno de `Handshake()` e a resposta
HTTP manual que este harness escreve a mao (nunca `net/http` -- ver o
comentario de `serveOneResponse`). Isso substitui, para a v9, a
estimativa heuristica 4.945/22.373/18.783 que Luciano identificou como
nao reproduzivel pelo codigo do repositorio -- os numeros abaixo SAO
reproduziveis, rodando `bash thesis/results/v9/integration/run_t6.sh`.

**Validacao cruzada, confirmada nos 4 perfis:** o numero que o
processo conta (`handshakeBytesIn`/`handshakeBytesOut`) bate, byte a
byte, com a soma dos registros TLS que o tshark decifra via keylog
(por exemplo, Classico: ClientHello 341B + flight do servidor
(ServerHello+EncryptedExtensions+CertificateRequest+Certificate+
CertificateVerify+Finished) 1.640B + flight do cliente
(Certificate+CertificateVerify+Finished) 1.172B = exatamente os
`handshakeBytesOut=1640`/`handshakeBytesIn=1513` -- `341+1172=1513` --
que o gateway registrou). A soma bruta de bytes do pcap inteiro
(independente de decifragem) tambem bate com handshake + janela
pos-handshake somadas, nos 4 perfis. Tres fontes independentes
(contador dentro do processo, tshark decifrado, soma bruta do pcap)
concordam exatamente -- nenhuma estimativa, tres medicoes.

**Resultado por perfil, modo normal (tickets desligados, N=1 execucao
cada -- prova de instrumentacao, nao ainda uma campanha estatistica;
repeticao com N maior e trabalho de piloto/T7):**

| Perfil | Grupo negociado | DualAuthenticated | Flight servidor (B) | Flight cliente (B) | Pos-handshake in/out (B) |
|---|---|---|---|---|---|
| Classico | CurveP384 | false (n/a) | 1.640 | 1.513 | 71 / 203 |
| PQC | MLKEM1024 | false (n/a) | 10.878 | 10.728 | 71 / 198 |
| Hibrido-v8 | SecP384r1MLKEM1024 | false (n/a; gate X.509 do client cert passou) | 8.552 | 8.397 | 71 / 215 |
| Hibrido-AND | SecP384r1MLKEM1024 | **true**, confirmado nos dois lados | 12.177 | 11.902 | 71 / 215 |

Todos os 4: grupo negociado bate exatamente o esperado, `status=200`
na unica requisicao HTTP, nenhuma falha.

**Tickets, modo diagnostico (religados so para medir; achado tecnico
no caminho -- registrado porque mudou o design do teste):** a primeira
tentativa, com `SessionTicketsDisabled=false` nos dois lados, mediu
delta ZERO em todos os perfis -- bug da PROPRIA instrumentacao, nao do
mecanismo: `handshake_client.go` desta toolchain (linha ~376) so faz o
cliente anunciar `psk_key_exchange_modes` (o sinal que
`shouldSendSessionTickets()` do servidor exige, RFC 8446 4.2.9) quando
`Config.ClientSessionCache` NAO e nil -- o harness nunca setava isso.
Corrigido (`proxy/main.go`, `buildClientTLSConfig`): quando
`ticketsDisabled=false`, seta `ClientSessionCache =
tls.NewLRUClientSessionCache(4)`. Depois da correcao:

| Perfil | Flight servidor SEM ticket (B) | Flight servidor COM ticket (B) | Overhead do ticket (B) |
|---|---|---|---|
| Classico | 1.640 | 3.331 | **1.691** |
| PQC | 10.878 | 22.007 | **11.129** |
| Hibrido-v8 | 8.552 | 15.591 | **7.039** |
| Hibrido-AND | 12.177 | 12.177 | **0** |

Confirmado simetricamente do lado do cliente: a MESMA quantidade de
bytes aparece na janela pos-handshake do proxy (ex.: Classico
203->1.894, delta 1.691) em vez da janela de handshake -- porque o
`Handshake()` do CLIENTE retorna antes de ler, de forma oportunista, o
`NewSessionTicket` que o servidor ja escreveu (confirmado lendo
`handshake_server_tls13.go`: o servidor envia o ticket de forma
SINCRONA, dentro do seu proprio `Handshake()`, logo depois de
processar o `Certificate`/`CertificateVerify` do cliente -- mas o
cliente nao precisa terminar de LER esse ticket para considerar seu
proprio handshake completo). Ou seja: o mesmo ticket pode cair de um
lado ou outro da fronteira dependendo de QUEM mede e QUANDO -- exatamente
por isso o pedido original (medir as duas janelas, nos dois lados) nao
era redundante.

**Achado estrutural, nao previsto, com implicacao direta para a
tese:** o Hibrido-AND **nunca emite ticket, em nenhum modo** -- nao
por causa deste ajuste (`SessionTicketsDisabled`), e sim por uma
decisao de design ja tomada na T3 (`dual.go`'s
`shouldSendSessionTickets()`: `if hs.c.config.Dual != nil &&
hs.c.config.Dual.Require { return false }`), porque retomar uma sessao
por PSK pularia TODA a troca de Certificate/CertificateVerify que
prova posse das duas chaves -- um ticket emitido herdaria
`DualAuthenticated=true` numa conexao futura sem jamais reverificar
nada, o que anularia a garantia central do mecanismo. **Isso significa
que o Hibrido-AND e estruturalmente IMUNE ao artefato de inflacao que
contaminou os numeros historicos da v7/v8 (Decisao 78/79 da v8) -- os
outros 3 perfis da v9 (e os 3 da v7/v8) continuam vulneraveis a ele se
um operador religar tickets.** Tambem explica por que o tamanho do
ticket escala com o perfil (1.691B Classico -> 7.039B Hibrido-v8 ->
11.129B PQC): o ticket do Go embute a cadeia de certificados do PEER
verificada, para que uma sessao retomada ainda tenha
`ConnectionState.PeerCertificates` preenchido sem precisar re-enviar
os certificados -- logo um cliente com certificado grande (PQC,
Hibrido-v8) produz um ticket grande, na mesma proporcao.

**Tempos no gateway por etapa, achado adicional sobre o limite da
fronteira de medicao (transparencia, nao invalida a tabela acima):**
`gateway/main.go` ganhou `requestDurationUs` (tempo so da etapa de
servir a resposta HTTP, separado de `handshakeDurationUs`). Ao medir
isso, apareceu uma segunda forma do MESMO tipo de artefato que a
Decisao 78 da v8 ja tinha documentado (bytes de uma etapa seguinte
entrando na contagem da etapa anterior) -- so que numa camada
diferente: com o cliente enviando sua requisicao HTTP SEM nenhum
atraso logo depois do seu proprio `Handshake()` retornar, o `Read()`
do servidor que consome a ultima mensagem do handshake (o `Finished`
do cliente) ocasionalmente ja encontra, no buffer do socket, os bytes
da requisicao HTTP que chegaram colados em cima (loopback, latencia
quase zero) -- e os conta como "handshake" (`handshakeBytesIn` subiu
de 1.513 para 1.584 nessa rodada, exatamente os 71 B da requisicao que
"vazaram" para o lado de dentro da fronteira; `postHandshakeBytesIn`
correspondentemente caiu para 0). **Isso NAO invalida a tabela
publicada acima** -- aquela rodada foi obtida com uma pausa de 100ms
antes do envio (introduzida originalmente para o diagnostico de
tickets, ainda ativa quando essa tabela foi gerada) e confirmada
TRIPLAMENTE (contador do processo = tshark decifrado = soma bruta do
pcap, os tres concordando exatamente) -- mas confirma que a fronteira
de medicao, mesmo no nivel de `Handshake()`, nao e imune a esse efeito
quando o par envia dados imediatamente, sem pausa alguma. **Registrado
para a T7:** a campanha real deve continuar cruzando o contador de
processo contra pcap/tshark por execucao (ja parte deste pipeline),
nao confiar so no contador quando a latencia real entre handshake e
primeira requisicao for muito baixa (ex.: cenario 0ms).

Tempos medidos, mesma rodada (modo normal, sem a pausa de
diagnostico, portanto sem o viés de ticket): `requestDurationUs` --
Classico 30us, PQC 63us, Hibrido-v8 43us, Hibrido-AND 115us (etapa de
servir UMA resposta HTTP minima, nao comparavel ainda a
`opin_processing_ms` real da v7/v8, que serve payloads JSON maiores --
esperado que o Hibrido-AND tenda a ser o mais lento aqui tambem na
campanha real, por ter duas cadeias para considerar nas verificacoes
de ConnState, nao por este numero especifico).

**Microbenchmarks de CPU por operacao (4 primitivas, N=2000 cada,
exceto keygen RSA/ML-DSA-65 N=100 por serem muito mais lentas;
`thesis/results/v9/integration/bench`, chaves geradas na hora, mesmo
tipo/parametro dos perfis reais -- a chave especifica nao afeta custo
de CPU):**

| Operacao | ns/op | ops/s |
|---|---|---|
| RSA-2048 keygen | 61.518.062 | 16 |
| RSA-2048 sign (PSS-SHA256) | 830.087 | 1.205 |
| RSA-2048 verify (PSS-SHA256) | 27.887 | 35.859 |
| ML-DSA-65 keygen | 270.874 | 3.692 |
| ML-DSA-65 sign | 537.322 | 1.861 |
| ML-DSA-65 verify | 152.369 | 6.563 |
| ECDH P-384 keygen | 112.387 | 8.898 |
| ECDH P-384 compute (KEX) | 550.225 | 1.817 |
| ML-KEM-1024 keygen | 112.890 | 8.858 |
| ML-KEM-1024 encapsulate | 77.896 | 12.838 |
| ML-KEM-1024 decapsulate | 126.740 | 7.890 |

Custo de KEX por perfil, somando as operacoes que o handshake de fato
executa: Classico = 1x keygen + 1x compute ECDH P-384 (~663 us);
PQC = 1x keygen + 1x encapsulate + 1x decapsulate ML-KEM-1024 (~317
us); Hibrido/Hibrido-AND = soma das duas linhas acima, ja que o
combinador do grupo hibrido concatena os dois segredos (~980 us).
Custo de assinatura/verificacao por perfil: Classico usa RSA-2048 (1
sign + 1 verify no par de certificados = ~858 us); PQC/Hibrido-AND
(cadeia ML-DSA-65) usam ML-DSA-65 (1 sign + 1 verify = ~690 us, MAIS
RAPIDO que RSA-2048 apesar do certificado maior); Hibrido-v8 soma RSA
(assinatura principal) + ML-DSA-65 (assinatura alt X.509, verificada
so na validacao de cadeia, nao por operacao de rede). Hibrido-AND paga
RSA completo E ML-DSA-65 completo, EM PARALELO estruturalmente (duas
cadeias independentes) -- custo de CPU e a soma das duas, nao hibrido.

**Analise de initcwnd / RTTs extras para rotas distantes (calculo de
mesa, Fase 1 local -- nao ha rota real da AWS ainda para medir; usa os
tamanhos REAIS medidos acima, nao a tabela de certificado da T4):**
formula: `RTTs extras = max(0, ceil(bytes_do_flight / cwnd_bytes) - 1)`,
`cwnd_bytes = initcwnd_segmentos x MSS`, MSS=1460B (Ethernet padrao).

| Perfil | Flight servidor (B) | initcwnd=10 (14.600B, padrao Linux atual) | initcwnd=3 (4.380B, legado pre-2011) |
|---|---|---|---|
| Classico | 1.640 | 0 RTT extra | 0 RTT extra |
| PQC | 10.878 | 0 RTT extra | **2 RTTs extras** |
| Hibrido-v8 | 8.552 | 0 RTT extra | **1 RTT extra** |
| Hibrido-AND | 12.177 | 0 RTT extra | **2 RTTs extras** |

**Conclusao:** com o `initcwnd=10` que e o padrao de qualquer kernel
Linux razoavelmente atual (desde 2011, RFC 6928) -- o que se espera de
qualquer instancia EC2 moderna --, NENHUM dos 4 perfis precisa de RTT
extra por limite de janela de congestionamento inicial, em NENHUM dos
tiers de latencia ja usados nesta tese (14/30/140/225/320ms) -- o
custo extra do Hibrido-AND (quase 2x o Hibrido-v8, por carregar duas
cadeias completas) ainda fica dentro do primeiro flight em qualquer
RTT. So sob um `initcwnd` legado (3 segmentos, pre-2011) o PQC e o
Hibrido-AND pagariam RTTs extras -- **registrado para a T7: confirmar
empiricamente o `initcwnd` real das instancias EC2 do piloto antes de
assumir 0 RTTs extras**, nao decidido aqui por falta de uma rota real
para medir. Esta analise nao cobre perda de pacote/retransmissao
(fenomeno dependente de rota real, nao reproduzivel em loopback local).

**Artefatos:** `thesis/results/v9/integration/gateway/main.go` e
`proxy/main.go` reescritos (contagem na fronteira do `Handshake()`,
keylog, tickets parametrizados); `measure/{Dockerfile,measure.sh,
.gitignore-covered certs}`; `bench/{main.go,go.mod,Dockerfile}`;
`run_t6.sh` (substitui `run_t5.sh` como o script de referencia -- 
`run_t5.sh` continua funcionando, mantido por compatibilidade, mas
`run_t6.sh` e o que agora prova tanto a integracao quanto a
instrumentacao). Nenhuma chave, nenhum certificado, nenhum pcap ou
keylog commitado -- tudo gerado e descartado a cada execucao
(`t6_out/` e `measure/certs/` gitignored).

Mesmas regras: nenhuma acao em AWS, sem commit antes do scanner,
relatorio no chat.

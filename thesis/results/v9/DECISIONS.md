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

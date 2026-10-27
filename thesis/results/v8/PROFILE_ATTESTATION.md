# Profile Attestation (Classic / PQC / Hybrid) — measured, not assumed

**Commit measured:** `ba63354f56a4b0860ec1c138cc65339cd01c08dd` (HEAD at the time of this
attestation; no code was changed to produce it — read-only inspection + real executions only).

**Code hashes (sha256) of the files that govern the behavior being attested:**

| File | sha256 |
|---|---|
| `thesis/scripts/opin_flow.py` | `7c4d5b2a37b1d1557f37187248f64aa194c7cbdc5f50747e3fcf53581af3afba` |
| `mock-service-os/mock_mtls/main.go` | `d70d74cc09830f85ac522d29d82c48390bdae04df7ed2499c2d813b5861ad34d` |
| `thesis/scripts/tls_kem_proxy/main.go` | `fd6e6ceca9a8aa611beaeac3670edd652d0bad3260216b0d92a510456a78852a` |
| `thesis/scripts/pqc-signer/signer_core.mjs` | `737b440f749a83c1b408ed16162b56a9e075d62d33e4579d5e95e51e66fa80d9` |

**Methodology.** Everything below comes from ONE real execution per profile against the
local MockOPIN stack (no AWS — standing rule, no apply/destroy without Luciano present; nothing
here needed AWS anyway), run 2026-10-27, using the project's own pinned venv
(`thesis/scripts/.venv`, `cryptography==50.0.0`, NOT the system Python — see the note at the
end of this document, a real environment bug this attestation turn found and fixed before
trusting any PQC-profile result). For each profile: the stack was switched via
`switch_crypto_profile.py <profile>` (real `docker compose --force-recreate` + 5 real settling
runs + negotiated-group check — unmodified, reused), then one real flow was run
(`latency_automation.run_once_timed(profile, return_calls=True)`, unmodified, reused) while a
`tcpdump` capture ran concurrently on the **real wire** between `tls_kem_proxy` and
`insurance-server-lambdas-mtls-1` (via a `nicolaka/netshoot` sidecar sharing that container's
own network namespace — `--network container:insurance-server-lambdas-mtls-1`, real packets, not
synthetic). The gateway's own `docker logs` for that exact execution window were saved
alongside. Three independent real sources are cross-checked against each other throughout:
(a) the pcap (dissected with `tshark`, Wireshark's own TLS dissector, not a hand-rolled parser),
(b) `mock_mtls`'s own structured JSON log (`mtlsHandshakeDurationMs`/`curveID`/`tlsVersion`/
`cipherSuite`, unmodified instrumentation), (c) real certificate files pulled directly from the
**running** container (`docker exec ... cat certs/...`, not the repo's local copy, so a build-vs-
image drift would show up). Raw artifacts (pcaps, gateway logs, cert dumps, raw `/jwks` bodies,
full `result.json` per profile) are not committed here (binary/bulky) — paths are given so
anyone can regenerate them from the same commit; ask if you want them preserved as attachments.

No AWS was used. No code was changed to produce any row below. Every "diferença" section exists
because this attestation found something real and is reporting it, per instruction — not
because something was broken and silently patched.

---

## 1. Grupo TLS negociado (key exchange) e versão TLS

Measured twice, independently, per profile: from the real pcap (`tshark`, `tls.handshake.
extensions_key_share_group` on the ServerHello) and from `mock_mtls`'s own real-time log
(`curveID` field, same connection). Both agree, every time, for every profile.

| Perfil | Esperado | Observado (log) | Observado (pcap, grupo IANA) | Versão TLS | Evidência | PASSA/FALHA |
|---|---|---|---|---|---|---|
| Classic | ECDHE P-384 | `CurveP384` | `24` (secp384r1) | TLS 1.3 | `attest/classic/gateway.log`, `attest/classic.pcap` frame 4/6 | **PASSA** |
| PQC | MLKEM1024 | `MLKEM1024` | `514` (0x0202, ML-KEM-1024) | TLS 1.3 | `attest/pqc/gateway.log`, `attest/pqc.pcap` frame 4/6 | **PASSA** |
| Hybrid | SecP384r1MLKEM1024 | `SecP384r1MLKEM1024` | `4589` (0x11ED, SecP384r1MLKEM1024) | TLS 1.3 | `attest/hybrid/gateway.log`, `attest/hybrid.pcap` frame 4/6 | **PASSA** |

Real cipher suite, all three profiles, both sources: `TLS_AES_128_GCM_SHA256`.

A real, measured (not assumed) structural fact, same for all 3 profiles: the mTLS gateway
negotiates a **second**, internal channel (the AS's own reverse-proxy calls to the RS/mockapi)
pinned to `CurveP256` regardless of `CRYPTO_PROFILE` — confirmed in every gateway.log, and
confirmed in the pcap as the connections whose ServerHello selects group `23` (secp256r1), never
the profile's own group. This is `mock_mtls/main.go`'s documented, deliberate SNI-scoped carve-out
(`GetConfigForClient`, read, not touched) — not a leak or a bug; flagged here only because item 1
asked for "o grupo negociado," and there is a real second one in every single execution.

---

## 2. Algoritmo de assinatura do handshake e de cada certificado da cadeia

**Redação corrigida 2026-10-27 (pedido explícito, depois da primeira versão deste atestado ter
marcado FALHA contra uma expectativa formulada de forma imprecisa):** "PS256" é o algoritmo do
**JWT**, não o algoritmo de assinatura do **certificado X.509**. O certificado X.509 usa
PKCS1v1.5 **nos três perfis** (Classic, PQC usa ML-DSA-65 em vez de RSA mas no mesmo papel de
"assinatura do certificado", Hybrid). No Hybrid especificamente: a **troca de chaves TLS** é
híbrida (SecP384r1MLKEM1024, confirmado na seção 1); a **autenticação do handshake** (o
certificado e sua assinatura) é RSA puro, igual ao Classic; a assinatura dupla (Strong Nesting)
vale só na **camada JWT** (seção 3). A extensão ML-DSA no certificado do Hybrid é inerte no
handshake — presente nos bytes do certificado, nunca lida pelo `crypto/tls`. Com essa separação
de camadas, as três linhas abaixo PASSAM — a tabela já media exatamente isso; só a rotulação
mudou.

**Real structural finding, same for all 3 profiles**: there is no 3-level leaf/intermediate/root
chain anywhere in this stack. The mTLS server's own TLS leaf certificate is issued **directly**
by a root (2 levels), confirmed by reading the real `issuer`/`subject` fields of the certificate
files pulled live from the running container (`docker exec insurance-server-lambdas-mtls-1 cat
certs/...`, not the repo's working copy):

- **Classic**: `mtls.crt` (leaf) issued directly by `ca.crt` (root, self-signed, `CN=ca`).
- **PQC**: `mtls_pqc.crt` (leaf) issued directly by `root_ca_pqc.crt` (root, self-signed).
- **Hybrid**: `mtls_hybrid.crt` (leaf) issued directly by `ca.crt` — the **same classical root
  as Classic**, confirmed by real issuer-field bytes, not assumed.

(`root_ca.crt`/`issuer_ca.crt`/`root_ca_hybrid.crt`/`issuer_ca_hybrid.crt` are a **separate** pair
of files, served over HTTP by the Directory mock (`/root-ca.pem`, `/issuer-ca.pem`) for the
OPIN-Directory/PKI simulation — confirmed real via `fetch_server_keys_and_ca()`'s own live
download in this session. They are not part of the mTLS leaf's own validation chain. `item 5`
below has their own hashes.)

| Perfil | Esperado — assinatura do certificado X.509 (handshake) | Observado — certificado da folha (`mtls*.crt`, pull real do container) | Observado — raiz | PASSA/FALHA |
|---|---|---|---|---|
| Classic | RSA, PKCS1v1.5/SHA-256 | `sha256WithRSAEncryption`, RSA-4096 | `ca.crt`, mesmo algoritmo | **PASSA** |
| PQC | ML-DSA-65 em toda a cadeia | `ML-DSA-65` (OID `2.16.840.1.101.3.4.3.18`), `MLDSA65PublicKey`, 1952 bytes raw | `root_ca_pqc.crt`, mesmo algoritmo, auto-assinado | **PASSA** |
| Hybrid | RSA, PKCS1v1.5/SHA-256 — igual ao Classic; ML-DSA-65 só como extensão X.509 inerte | `sha256WithRSAEncryption`, RSA-4096 | `ca.crt` (mesma raiz classical do Classic), mesmo algoritmo | **PASSA** |

**Evidência da extensão ML-DSA inerte no Hybrid (lida diretamente no código-fonte e no
certificado real, não deduzida):** `mock-service-os/mock_mtls/main.go` (não tocado, só lido) diz
textualmente: "mtls_hybrid.crt/.key: an ordinary RSA cert/key pair **as far as crypto/tls itself
is concerned** -- the ML-DSA-65 material rides along inertly as three non-critical X.509
extensions the TLS handshake itself never looks at." Confirmado no certificado real:
`mtls_hybrid.crt` tem exatamente 3 extensões extras não reconhecidas pela biblioteca
(`2.5.29.72/73/74`, "Unknown OID") além das 4 extensões padrão de `mtls.crt` — essas são, por
desenho, as 3 extensões inertes citadas no código. Quantificação em bytes dessas 3 extensões:
ver seção 7 (nova, pedida nesta rodada).

---

## 3. Algoritmo do JWT (`alg`) e das chaves no `/jwks` (`kty`, `alg`, tamanho)

Extraído de JWTs REAIS capturados durante a execução real de 44 chamadas de cada perfil
(`result.json`'s own `calls[].jwts`, decodificado só o header, sem verificar de novo) e de
respostas REAIS de `/jwks` buscadas ao vivo (`raw_fetch.json`, mesma convenção
`fetch_server_keys_and_ca()`/`do_call()` já usa, reutilizada, não reimplementada).

| Perfil | Esperado | Observado — JWT (`alg` real, nos tokens capturados) | Observado — AS `/jwks` | Observado — RS `/jwks` | PASSA/FALHA |
|---|---|---|---|---|---|
| Classic | PS256 | `PS256` (client_assertion, request_object); id_token é JWE (`RSA-OAEP`/`A256GCM`, criptografia, não assinatura — fora do escopo PQC por desenho) | 1 entrada `sig`: `kty=RSA, alg=PS256` | 1 entrada `sig`: `kty=RSA, alg=PS256` | **PASSA** |
| PQC | ML-DSA-65 | `ML-DSA-65` (client_assertion, request_object, JARM); id_token ainda JWE `RSA-OAEP` (criptografia sempre clássica, por desenho, confirmado em `decrypt_and_verify_jwt()`'s docstring) | 1 entrada `sig`: `kty=AKP, alg=ML-DSA-65` | 1 entrada `sig`: `kty=AKP, alg=ML-DSA-65` | **PASSA** |
| Hybrid | assinatura dupla, duas entradas | 2 algoritmos reais distintos nos 28 JWTs capturados: `RS256` (client_assertion/request_object — RSA clássico puro no header, com o `pqc` claim embutido carregando a assinatura ML-DSA-65 separada, Decision 13) e `MLDSA65-RSA2048-PSS-SHA256` (artefato emitido pelo AS — Strong Nesting, Decision 9) | **1 entrada** `sig`: `kty=HYBRID, alg=MLDSA65-RSA2048-PSS-SHA256` | **2 entradas** `sig`: `kty=HYBRID, alg=MLDSA65-RSA2048-PSS-SHA256` **e** `kty=RSA, alg=RS256` (mesmo kid, cópia de compatibilidade — Decision 88) | **PASSA** (duas entradas existem — no `/jwks` do RS, não do AS; ver nota) |

**Nota concreta sobre Hybrid:** a expectativa "duas entradas" é real e confirmada — mas só no
`/jwks` do **RS** (2 entradas: a composta `HYBRID` e uma cópia `RSA`/`RS256` para compatibilidade
de descoberta, exatamente o que a Decision 88 já documentou e esta sessão confirmou de novo, ao
vivo). O `/jwks` do **AS** publica só a entrada composta `HYBRID` (1 entrada) — uma diferença
real entre os dois endpoints, não um erro: `mock_as`/`mockapi` são serviços diferentes com
implementações de `/jwks` independentes (confirmado pelos dois corpos reais, anexados em
`raw_fetch.json`). Também real e distinto de "PS256"/"RS256" simples: o header `alg` do JWT
Hybrid usa dois nomes DIFERENTES dependendo de quem assina — `RS256` para o que o cliente assina
(payload-extension, Decision 13) e o nome composto literal `MLDSA65-RSA2048-PSS-SHA256` para o
que o AS assina (Strong Nesting, Decision 9) — ambos reais, nenhum inventado, rastreados pelo
`kid` de volta às entradas reais do `/jwks` acima.

---

## 4. Verificação de assinatura ativa, confirmada em todas as 44 chamadas

| Perfil | `call_count` real | Eventos de verificação reais (`verification_timings`) | Exceção levantada? | PASSA/FALHA |
|---|---|---|---|---|
| Classic | 44 | 7 (3 `rs_response`, 2 `jarm`, 2 `id_token`) | Nenhuma — fluxo completou | **PASSA** |
| PQC | 44 | 7 (mesma composição) | Nenhuma — fluxo completou | **PASSA** |
| Hybrid | 44 | 7 (mesma composição) | Nenhuma — fluxo completou | **PASSA** |

Leitura precisa (não inflada): das 44 chamadas HTTP de cada fluxo, 7 carregam um artefato
assinado verificável (JARM, id_token, resposta do RS) — as outras 37 são CRUD/consulta sem
assinatura própria para verificar. `verify_jwt()`/`decrypt_and_verify_jwt()` levantam
`SignatureVerificationError` (que aborta o fluxo imediatamente, sem captura silenciosa em
nenhum lugar do código — confirmado lendo a classe) se qualquer verificação falhar. As 3
execuções reais aqui completaram as 44 chamadas sem excecão — ou seja, as 7 verificações de
cada uma passaram, 21/21 no total desta sessão. "Verificação ativa" confirmado: todas as 3
execuções usam a MESMA `_run_verifier()`/serviço `pqc-signer` para TODOS os perfis, inclusive
Classic (não `pyjwt.decode()` direto) — lido em `opin_flow.py`, não assumido.

---

## 5. Hash (sha256) dos arquivos de configuração e das imagens, vs v7

**Descoberta estrutural real, antes da tabela**: existe **UMA única imagem Docker** para o
gateway (`insurance-server-lambdas-mtls`, `sha256:6f8cbcfb45fb...`, confirmada via `docker
inspect` com os 3 perfis testados nesta mesma sessão — a imagem não mudou entre eles). O que
muda por perfil é só a variável de ambiente `CRYPTO_PROFILE` + os arquivos de certificado que o
binário Go carrega em tempo de execução (já hashados abaixo). Não existem "3 imagens, uma por
perfil" — a pergunta original presumia isso; reportado aqui em vez de silenciosamente responder
só com os hashes de certificado.

| Arquivo | sha256 atual | Igual à v7? | Motivo, se diferente | Muda o que é medido? |
|---|---|---|---|---|
| `certs/mtls.crt` (leaf, Classic) | `5cdfa4b8663c...` | **Sim** — último commit a tocar o arquivo (`bf57565`) é anterior ao fechamento da v7 | — | — |
| `certs/mtls_hybrid.crt` (leaf, Hybrid) | `ce77d317140...` | **Sim** — último commit (`7c722f6`) anterior ao fechamento da v7 | — | — |
| `certs/mtls_pqc.crt` (leaf, PQC) | `b0a10468c4f...` | **Sim** — último commit (`478bda5`) anterior ao fechamento da v7 (mesmo commit que mudou o cert de CLIENTE pqc, ver linha abaixo) | — | — |
| `certs/client_one.crt` (cliente, Classic) | `55b682f350a...` | **Sim** — hash idêntico ao de `thesis/results/v7/artifacts/classic/client_one.crt` | — | — |
| `certs/client_one_hybrid.crt` (cliente, Hybrid) | `32d16560bcc...` | **Sim** — idêntico a `thesis/results/v7/artifacts/hybrid/` | — | — |
| `certs/client_one_pqc.crt` (cliente, PQC) | `866fae9cfe3...` | **NÃO** — v7 tem `b768a3e4e94...` | commit `478bda5` (2026-09-29), **depois** do snapshot oficial da v7 (`f7dc39f`, 2026-09-14): "fix: make PQC's certificate chain post-quantum end-to-end" — fecha uma assimetria real (cadeia PQC da v7 tinha assunto ML-DSA-65 mas assinatura de CA ainda clássica/RSA; Hybrid já tinha assinatura de CA genuinamente ML-DSA-65). Re-emite a cadeia PQC inteiramente auto-contida em ML-DSA-65. | **Sim, intencionalmente** — bytes/tamanho da cadeia PQC mudam (OPINsize), já documentado e recomputado em `DECISIONS.md`/`METRICS_COVERAGE.md` anteriores a esta sessão. Não é uma regressão nem um erro silencioso — é a correção que fecha a Recommendation 2 de uma revisão externa. |
| `insurance-server-lambdas/docker-compose.yml` | (ver `git log`) | **NÃO** | commit `27fc794` (2026-10-22): adiciona `depends_on`/healthcheck para a dependência real do `mockapi` no `psql` (erro de ordem de boot num ambiente EC2 genuinamente novo — nunca aparecia em rehearsals locais porque o `psql` já estava de pé de trabalho anterior). | **Não** — mensagem do commit e diff confirmados: só ordem de startup, nenhuma mudança no que é medido ou como. |

---

## 6. Teste negativo por perfil (um cliente de um perfil não fecha handshake com o servidor de outro)

Três execuções reais, servidor real rodando o perfil indicado, cliente real tentando conectar
com o perfil (curva + certificado) de outro:

| Cliente | Servidor (real, ativo) | Resultado real | Evidência | PASSA/FALHA |
|---|---|---|---|---|
| Classic | PQC | `tls_kem_proxy` nunca respondeu HTTPS (timeout de 30s) — nunca completou handshake algum | `RuntimeError: tls_kem_proxy did not answer HTTPS on port 8443 within 30s` | **PASSA** |
| PQC | Hybrid | Mesmo resultado — nunca completou handshake | mesmo erro | **PASSA** |
| Hybrid | Classic | Mesmo resultado — nunca completou handshake | mesmo erro | **PASSA** |

Evidência de 2º nível (o alerta TLS real, não só o timeout do lado do cliente) — capturado nos
próprios logs do container `tls_kem_proxy` numa 4ª tentativa real (PQC cliente x Classic
servidor, modo detached para poder ler o log antes do container sumir):

```
tls_kem_proxy: relay mode on :8443 -> mtls:443 (curve=mlkem1024)
tls_kem_proxy: dial upstream mtls:443: remote error: tls: handshake failure
```

`remote error: tls: handshake failure` é o alerta TLS real que o servidor (configurado para
Classic, só oferece `CurveP384` ao cliente) envia de volta ao cliente que insiste em oferecer
`mlkem1024` — nenhum grupo em comum, rejeição real de protocolo, não uma falha de rede genérica.
Nenhum dos 4 testes teve sucesso inesperado (que seria a falha real do teste negativo).

---

## 7. Quantificação em bytes (pedido explícito, 2026-10-27, segunda rodada)

### 7a. O que a extensão ML-DSA soma ao termo de handshake do Hybrid

Medido diretamente nos certificados reais (DER, não PEM — o que realmente viaja no wire), tanto
no leaf do servidor quanto no do cliente (mTLS é mútuo — os dois são transmitidos em todo
handshake client-facing):

| Certificado | DER Classic | DER Hybrid | Delta | Das 3 extensões ML-DSA (`2.5.29.72/73/74`) | Resto (outras extensões/overhead DER) |
|---|---|---|---|---|---|
| `mtls_hybrid.crt` (leaf, servidor) | 1.482 B (`mtls.crt`) | 6.847 B | **+5.365 B** | **5.301 B** | 64 B |
| `client_one_hybrid.crt` (cliente) | 1.494 B (`client_one.crt`) | 6.859 B | **+5.365 B** | **5.301 B** | 64 B |

As 3 extensões, individualmente (`mtls_hybrid.crt`, idêntico em `client_one_hybrid.crt`):
`2.5.29.72` = 1.974 B (chave pública ML-DSA-65, 1.952 B + envelope), `2.5.29.73` = 13 B
(identificador de algoritmo), `2.5.29.74` = 3.314 B (assinatura ML-DSA-65, ~3.309 B + envelope).

Como os dois certificados (servidor + cliente) são transmitidos em cada um dos 6 handshakes
client-facing de um fluxo completo, a extensão ML-DSA soma, por si só:

**5.301 B × 2 certificados = 10.602 bytes** por handshake — **76,6%** do delta real observado
entre Classic e Hybrid nos próprios campos `mtlsHandshakeBytes` do gateway, medidos nesta mesma
sessão (Classic 5.112 B, Hybrid 18.950 B, delta real 13.838 B). Os 3.236 B restantes do delta
real vêm do próprio key share SecP384r1MLKEM1024 (maior que P-384 puro) mais os 128 B de
diferença estrutural não-ML-DSA entre os dois pares de certificado (confirmado por soma: 64 B ×
2 certificados = 128 B). Conclusão quantificada: a maior parte do custo extra de bytes do
handshake Hybrid vs Classic vem da extensão X.509 inerte (nunca lida pelo TLS), não da troca de
chaves PQC em si.

### 7b. Efeito da correção do certificado de cliente PQC no OPINsize vs a referência da v7

Medido diretamente (DER real, v7 vs atual):

| | v7 (`thesis/results/v7/artifacts/pqc/client_one_pqc.crt`) | Atual (`mock-service-os/certs/client_one_pqc.crt`) | Delta |
|---|---|---|---|
| DER | 2.953 B | 5.879 B | **+2.926 B** |
| Emissor | `CN=ca` (CA clássica, RSA) | `CN=root_ca_pqc` (auto-assinada, ML-DSA-65) | — |
| Algoritmo de assinatura | `sha256WithRSAEncryption` | `ML-DSA-65` | — |

O certificado de servidor (`mtls_pqc.crt`) sofreu, pelo mesmo commit (`478bda5`, mensagem cita os
três certificados live-handshake juntos), presumivelmente a mesma classe de mudança — mas **não
existe no repositório um snapshot da v7 do `mtls_pqc.crt`** (a pasta `v7/artifacts/` só preserva
certificados de CLIENTE) para medir o delta do lado do servidor diretamente. Reportado como
lacuna real, não preenchido com suposição.

**Desvio exato já publicado** (`pilot_acceptance.py`'s own `V8_OPINSIZE` vs seu próprio comentário
da referência v7): PQC passou de **322.895 B (v7)** para **326.799 B (V8_OPINSIZE)** — delta de
**+3.904 B (+1,21%)**, dentro da tolerância de ±3% (`OPINSIZE_TOLERANCE_PCT`).

**Tensão real, não reconciliada por este atestado**: se o delta do certificado de cliente
(+2.926 B) se propaga para `term_handshake` da mesma forma simples que a seção 7a usou para o
Hybrid (× 6 handshakes client-facing = **+17.556 B**, só do certificado de cliente, antes mesmo
de somar o lado do servidor), o efeito esperado no OPINsize seria MUITO maior que o +3.904 B
total já publicado. Esta atestação **não resolve essa discrepância** — resolver exigiria rodar a
pipeline real de `consolidate_v8.py` com os dois conjuntos de certificado lado a lado, o que é
uma mudança/execução de código fora do que esta rodada autorizou ("não altera código"). Hipótese
mais provável, sem confirmação: o artefato de fronteira de medição já documentado em
`METRICS_COVERAGE.md` ("`countingConn`'s own measurement-boundary artifact... the byte counter is
read at `ConnState -> StateActive`, which Go's HTTP server reaches strictly AFTER the
connection's FIRST REAL REQUEST has already started arriving") pode fazer `mtlsHandshakeBytes`
não capturar o certificado inteiro de forma linearmente proporcional ao seu tamanho real — mas
isso é uma hipótese, não uma conclusão medida. **Reportado em aberto, não forçado a fechar.**

---

## Resumo e decisão de bloqueio

**Nenhuma FALHA sem explicação concreta foi encontrada.** A seção 2 foi reescrita (2026-10-27,
segunda rodada) para separar explicitamente a camada de assinatura do certificado X.509
(PKCS1v1.5 nos três perfis) da camada de assinatura do JWT (PS256/ML-DSA-65/dual) — com essa
separação, as três linhas PASSAM; a formulação original da expectativa, não o sistema, é que
conflava as duas camadas. As duas diferenças reais vs v7 (seção 5) têm motivo documentado e
conhecido (uma delas é uma correção intencional já registrada em `DECISIONS.md`, a outra é
puramente ordem de startup, sem efeito no que é medido). A seção 7 quantificou em bytes o custo
real da extensão ML-DSA inerte do Hybrid (10.602 B/handshake, 76,6% do delta vs Classic) e deixou
**uma tensão real, explicitamente em aberto** entre o delta medido do certificado de cliente PQC
(+2.926 B, real) e o delta total já publicado do OPINsize (+3.904 B) — não forçada a fechar sem
dado.

**Conclusão: piloto 3 e a campanha NÃO estão bloqueados por este atestado.** Se a formulação da
expectativa em si (não o sistema) precisar de correção — por exemplo, separar explicitamente
"algoritmo do certificado TLS" de "algoritmo do JWT" nos critérios de aceite — isso é uma decisão
de Luciano sobre o documento de expectativas, não algo que este atestado resolve por conta
própria.

## Nota operacional (achada e corrigida durante esta sessão, não um bug do sistema)

A primeira tentativa de validar o perfil PQC falhou com `ValueError: Unknown key type:
2.16.840.1.101.3.4.3.18` porque o `python` do PATH deste shell é o Python de sistema
(`cryptography==46.0.3`, sem suporte a ML-DSA), não o `.venv` do projeto
(`thesis/scripts/.venv`, `cryptography==50.0.0`). Confirmado como um problema de ambiente, não
de código, reproduzindo o mesmo erro contra o código original via `git stash` antes de prosseguir
(mesma investigação já registrada em `DECISIONS.md`, Decision 90). Todas as medições reais deste
atestado usam `.venv/Scripts/python.exe` explicitamente.

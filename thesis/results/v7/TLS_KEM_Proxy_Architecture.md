# tls_kem_proxy — Arquitetura e Evolução

Este documento descreve `thesis/scripts/tls_kem_proxy/` — a infraestrutura de teste
(não parte do sistema OPIN em si) que permite ao `opin_flow.py` dirigir tráfego real
contra o gateway mTLS sob os grupos de troca de chave pós-quânticos/híbridos
(`MLKEM1024`, `X25519MLKEM768`), que a própria stack Python/OpenSSL usada pelo
script não sabe negociar. Cobre por que ele existe, como funciona por dentro, e a
evolução real dele ao longo da sessão — três bugs genuínos encontrados,
investigados e corrigidos, não hipotéticos. Todo número e toda linha de log citados
aqui vêm de medições e capturas reais já registradas em `thesis/results/v5/`,
`thesis/results/v6/Level 1/` e `thesis/results/v7/DECISIONS.md` — este documento é a
referência arquitetural consolidada, não uma repetição dessas investigações.

---

## 1. Por que ele existe

O gateway mTLS (`mock-service-os/mock_mtls`, escrito em Go) oferece, desde o
trabalho de Nível 1 (troca de chave), grupos de key exchange que só existem em
implementações recentes de TLS 1.3: `MLKEM1024` (ML-KEM puro, sem componente
clássico) e `X25519MLKEM768` (X25519 + ML-KEM-768 combinados). O Go 1.23+ já
suporta os dois nativamente em `crypto/tls`, sem biblioteca externa — mas o cliente
que dirige os testes, `opin_flow.py`, é Python, usando `requests`/`urllib3` sobre o
OpenSSL do sistema. Esse OpenSSL não reconhece nenhum dos dois grupos: uma conexão
tentando negociá-los falha com `handshake_failure` (o mesmo tipo de limite,
aliás, já documentado neste projeto para chaves ML-DSA-65 nativas — ver
`thesis/results/v7/DECISIONS.md`, Decision 5, para o caso irmão desse problema do
lado da apresentação de certificado, não da troca de chave).

Esse não é um problema novo neste projeto — é a mesma classe de limite que já
motivou `_run_pqc_signer()` (`opin_flow.py`), o helper Docker que assina
ML-DSA-65 delegando a um binário Go, porque `pyjwt`/`cryptography` também não
sabem fazer isso sozinhos. `tls_kem_proxy` aplica exatamente o mesmo princípio —
"delegar a um helper Go quando o Python não sabe fazer algo nativamente" — a uma
conexão TLS inteira, não a uma assinatura.

A diferença importante em relação a esse precedente é o **padrão de uso**: assinar
um JWT é uma operação pontual (uma chamada, um resultado), então um `docker run`
novo por assinatura foi aceitável até certo ponto — mas mesmo esse padrão já se
mostrou caro o suficiente para distorcer uma medição real (v5, Decision 8,
`thesis/results/v5/latency/DECISIONS.md`: a soma de 8 invocações `docker run --rm -i
mockopin-pqc-signer` num único fluxo PQC respondeu por praticamente 100% da
variância de `T_fluxo` entre execuções, span de 10,83s a 16,39s explicado quase
inteiramente pela soma dos tempos de assinatura, não pelo resto do fluxo). Uma
conexão TLS, ao contrário de uma assinatura, precisa se manter viva e ser
reaproveitada por múltiplas chamadas HTTP no mesmo pool — repetir o padrão "um
processo novo por operação" aqui teria multiplicado esse mesmo custo por 28
(uma por chamada HTTP do fluxo completo), não por 8. `tls_kem_proxy` existe
especificamente para evitar isso: um único processo de longa duração por execução,
não um por conexão nem um por chamada.

---

## 2. Arquitetura interna

### 2.1. Dois modos: relay e stub

`tls_kem_proxy/main.go` tem dois modos, escolhidos pela flag `-stub`:

- **Relay (padrão)**: um túnel TLS-sobre-TLS. Termina a conexão TLS local vinda do
  Python, abre uma conexão mTLS real contra o gateway com o certificado e o grupo
  de curva pedidos, e faz o *pipe* bidirecional dos bytes decifrados
  (`handleConn()`, linhas 225–252) pelo tempo de vida da conexão. Como isso nunca
  faz parsing de HTTP, os bytes exatos que o `opin_flow.py` manda (Host header
  incluso) chegam ao gateway inalterados — o roteamento por Host do lado do
  gateway funciona exatamente como funcionaria sem o proxy no meio.
- **Stub (`-stub`)**: responde toda requisição imediatamente com uma resposta fixa,
  sem nunca discar para o gateway (`runStub()`, linhas 126–137). Existe só para a
  calibração de overhead isolado do próprio processo proxy (Fase 4 do trabalho de
  Nível 1, `thesis/results/v6/Level 1/ARCHITECTURE.md`) — medir Python→proxy→Python,
  inteiramente local, sem a conexão mTLS real no meio.

Os dois lados falam TLS mesmo no salto local Python↔proxy, apesar de esse salto
nunca usar os grupos ML-KEM (`generateLocalListenerCert()`, linhas 84–119, gera um
certificado ECDSA P-256 autoassinado e descartável a cada início). A primeira
versão usava HTTP puro nesse salto e quebrou o fluxo de login: o `oidc-provider`
marca seu cookie de sessão de interação com o atributo `Secure`, e o cookie jar do
Python (`http.cookiejar`, que o `requests` usa incondicionalmente) descarta
silenciosamente cookies `Secure` numa conexão HTTP simples — confirmado ao vivo,
reproduzido de forma consistente, corrigido trocando esse listener para TLS
(comentário no topo do arquivo, linhas 9–19).

### 2.2. O túnel: uma conexão local, uma conexão real, nunca mais

A relação entre conexões é estritamente 1:1: `runRelay()` aceita uma conexão local
já terminada em TLS e, para ela, abre exatamente uma conexão mTLS real contra o
gateway (`handleConn()`) — nunca reaproveita essa conexão upstream para outra
conexão local, nunca abre mais de uma upstream para uma única conexão local. Essa
propriedade é o que preserva, do outro lado do proxy, o comportamento de pooling
que o `requests.Session()` do Python já tinha antes de o proxy existir.

### 2.3. Pooling de conexão: por que são 6, não 28 e não 1

`opin_flow.py` nunca abriu uma conexão nova por chamada HTTP — desde antes deste
proxy existir, ele já abre **3 `requests.Session()` distintas por sub-fluxo**
(uma para o AS, uma para o RS, e uma separada para `simulate_login()`, de
propósito — o comentário em `opin_flow.py` documenta que isso existe para
reproduzir "um terceiro pool de conexão separado, junto dos pools do AS e do RS").
O fluxo completo roda dois sub-fluxos (`run_insurance_flow` + `run_person_flow`):
3 pools × 2 sub-fluxos = as **6 conexões mTLS** que a equação OPINsize já usa como
`N_mTLS = 6`, para os três perfis. Cada uma dessas 6 conexões é reaproveitada
(keep-alive) por todas as chamadas HTTP que pertencem àquele pool — comportamento
padrão do `requests.Session()`, sem nenhuma intervenção do proxy.

O proxy precisa preservar exatamente essa contagem — nem 28 conexões (uma por
chamada HTTP, repetindo o erro caro do `_run_pqc_signer()`), nem 1 (colapsando
tudo, o que destruiria a comparabilidade com os perfis que não passam pelo proxy).
Como cada conexão local vira exatamente uma conexão upstream (Seção 2.2), e o
`requests.Session()` do Python já decide sozinho quantas conexões locais abrir
(via seu próprio `http.Transport`-equivalente, mantendo pool por destino), a
contagem de 6 é preservada de graça, sem o proxy precisar reimplementar nenhuma
lógica de pooling — só não pode introduzir uma divisão ou uma fusão de conexões
que não exista no lado Python.

Essa contagem foi conferida ao vivo, não assumida: instrumentando o proxy e o
gateway durante uma execução completa, a Fase 3 do trabalho de Nível 1 confirmou 6
conexões mTLS externas reais por execução (mais 1 do probe de prontidão do
`opin_flow.py`, ver Seção 3.2 abaixo) — nunca 1, nunca 28.

### 2.4. Seleção de curva por perfil

`opin_flow.py`'s `TLS_KEM_PROXY_CURVE_BY_PROFILE` (linha 455) mapeia cada perfil a
um argumento `-curve`:

```python
TLS_KEM_PROXY_CURVE_BY_PROFILE = {"classic": "classic", "pqc": "mlkem1024", "hybrid": "x25519mlkem768"}
```

`runRelay()` (`tls_kem_proxy/main.go`, linhas 159–174) traduz isso para a lista de
`CurvePreferences` que a conexão upstream vai oferecer:

```go
switch curveName {
case "classic":
    curvePreferences = []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256}
    minVersion = tls.VersionTLS12
case "mlkem1024":
    curvePreferences = []tls.CurveID{tls.MLKEM1024}
case "x25519mlkem768":
    curvePreferences = []tls.CurveID{tls.X25519MLKEM768}
}
```

Cada perfil pede exatamente um grupo — nunca uma lista com fallback clássico
misturado, deliberadamente: se o grupo pedido não estiver disponível dos dois
lados, a conexão deve falhar de forma visível (`handshake_failure`), não
degradar silenciosamente para clássico. O mesmo princípio "sem fallback silencioso"
que a porta AND dos certificados híbridos já aplica na camada de assinatura.

Existe um quarto valor, `"classical"` (não usado pela v7, mantido por
compatibilidade com diagnósticos futuros) — força `ServerName = "matls-api.local"`
no `tls.Dial` upstream, replicando deliberadamente a exceção por SNI da Seção 3.2
para servir como baseline auxiliar isolado ("Go-clássico") quando alguém precisar
decompor o custo do cliente Go separadamente do custo do próprio KEM (o problema
que motivou a Decision 2 do trabalho de Nível 1, `thesis/results/v6/Level 1/
DECISIONS.md`) — a v7 não precisa mais dessa decomposição porque, com a
unificação (Seção 3.4), não existe mais confusão Python-vs-Go entre perfis.

---

## 3. Evolução: uma narrativa de decisões reais

### 3.1. Fase 0 — confirmar que dá para fazer

Antes de desenhar qualquer coisa, a primeira pergunta foi se o Go realmente
oferece os grupos híbridos prontos, sem exigir biblioteca externa ou rascunho de
padrão pendente. Confirmado direto na documentação da mesma versão de Go já usada
no projeto (a mesma imagem que já roda o assinador ML-DSA-65): `X25519MLKEM768`,
`SecP256r1MLKEM768`, `SecP384r1MLKEM1024` e `MLKEM1024` já vêm prontos em
`crypto/tls`, de fábrica. Nada para instalar, nada para compilar — a mesma
conclusão que já valia para o suporte nativo a ML-DSA-65 usado em todo o resto
deste projeto.

### 3.2. A quebra da chamada interna `auth`→RS, e a correção por SNI

O primeiro teste ponta-a-ponta real (perfil PQC, via `tls_kem_proxy`) falhou de
forma reproduzível (3 de 3 tentativas) em `InsurerAdapter.getConsent()`, com
`InvalidGrant: invalid_grant` — a mesma forma de erro de uma race rara já
documentada (Decision 5 da v5, Decision 9 da v5/latency). A primeira hipótese foi
"a latência do proxy tornou essa race rara mais provável" — **investigada antes de
ser aceita**, por instrução padrão deste projeto de nunca aceitar uma explicação
plausível sem confirmação direta.

Os logs mostraram uma causa categoricamente diferente: `mtls`'s próprio log,
no exato instante da falha, registrava `"tls: no key exchanges supported by both
client and server"`; o log do `auth` mostrava `SSL alert number 40`
(`handshake_failure`, uma rejeição determinística de protocolo, não o `EOF` de uma
coincidência de timing). 3 de 3 reproduções, não a raridade documentada da race
original (1 em ~89 trocas de token), confirma que não é o mesmo fenômeno: o
próprio cliente HTTPS interno do `auth` (`InsurerAdapter`, que se conecta a
`matls-api.local` para checar o consentimento junto ao RS) não consegue negociar
`MLKEM1024`/`X25519MLKEM768` — o mesmo limite do Python, só que do lado do Node.

**A causa raiz**: o `tls.Config` do gateway é compartilhado por toda conexão
recebida, sem distinção de propósito. Uma decisão anterior (Decision 5, v5) já
tratava essa chamada interna específica como excepcionalmente clássica na
dimensão de *assinatura* (usa um certificado de transporte fixo, "sem relação com
`CRYPTO_PROFILE`") — fixar `CurvePreferences` para o gateway inteiro estendeu essa
variação por perfil para a dimensão de *troca de chave*, sem carregar adiante a
mesma isenção, quebrando a única chamada que a Decision 5 já tinha reservado.

**A correção**: diferenciação por SNI, usando um hook que o gateway já tinha —
`GetConfigForClient` (usado até então só para registrar o início do handshake).
Confirmado que o cliente interno do `auth` sempre se conecta literalmente a
`matls-api.local`, e que o cliente HTTPS do Node define o SNI automaticamente para
esse mesmo hostname — nenhum código em `opin_flow.py`/`tls_kem_proxy` jamais
alveja esse hostname (o tráfego externo usa `api.local`; o próprio `tls.Dial`
upstream do proxy usa `"mtls"` como SNI padrão), então não há risco de
sobreposição entre os dois sinais:

```go
cfg.GetConfigForClient = func(hello *tls.ClientHelloInfo) (*tls.Config, error) {
    if hello.ServerName == "matls-api.local" {
        return &internalCallerConfig, nil  // CurvePreferences clássico, MinVersion 1.2
    }
    return nil, nil  // sem override -- usa o grupo do perfil normalmente
}
```

Não é um mecanismo de isolamento novo — é a mesma regra "clássico fixo, sem
relação com `CRYPTO_PROFILE`" da Decision 5, agora estendida à dimensão que esta
etapa adicionou, expressa através de um hook que o gateway já tinha. Confirmado
também que essa conexão interna nunca fez parte do que `N_mTLS`/
`mTLS_handshake_bytes` medem (vêm inteiramente das conexões que o
`requests.Session()` do Python abre, identificadas pelo seu próprio `remoteAddr` —
a chamada interna do `auth` é uma conexão backend-only, com seu próprio
`remoteAddr`, nunca incluída em nenhuma das duas métricas) — manter essa conexão
clássica não muda nada que já foi ou já é reportado.

Este mesmo mecanismo foi reverificado com muito mais rigor já dentro da v7,
quando uma investigação de cobertura (SAD × implementação × `artifacts/`)
encontrou 35 handshakes clássicos coexistindo com handshakes `X25519MLKEM768` sob
o mesmo `CRYPTO_PROFILE=hybrid`: instrumentando `GetConfigForClient` com um log
explícito e cruzando, conexão por conexão, contra os handshakes capturados, a
correspondência foi 1:1 — as mesmas 35 aplicações da exceção, os mesmos 35
`remoteAddr`, nenhum handshake clássico sem essa explicação (`thesis/results/v7/
DECISIONS.md`, Decision 6, e `artifacts/{pqc,hybrid}/README.md`, Seção 4).

### 3.3. O bug do `"localhost"` — uma discrepância de ~1000x que não foi aceita sem explicação

A primeira rodada do lote de latência mostrou um "overhead do proxy" de +10 a
+12 segundos por execução completa — mas a calibração isolada do próprio processo
proxy (modo stub, Seção 2.1) tinha medido só ~2ms. Uma discrepância de quase 1000x
entre a calibração e o número do lote real **não foi aceita como "o proxy custa
mais do que pensávamos"** — foi investigada com três hipóteses nomeadas antes de
qualquer conclusão:

1. **O modo stub pula uma etapa que o caminho real sempre paga** (o handshake
   upstream) — parcialmente verdade estruturalmente, mas um teste controlado
   Go-a-Go (conexão reaproveitada, aquecida) mediu o custo real do modo relay,
   handshake upstream incluso, em 4,50ms contra 1,99ms direto — mesma ordem de
   grandeza do stub, não 1000x mais. Descartada como explicação da discrepância.
2. **O overhead não é o proxy, é algo que só aparece no fluxo completo** —
   **confirmada como a causa real**. Instrumentação por fase do fluxo Python
   mostrou cada conexão NOVA custando ~2,03–2,06s, contra ~2–3ms numa conexão
   REAPROVEITADA na mesma sessão. Isolando a variável (mesmo destino, só o
   hostname mudando):

   | Host usado para alcançar o `tls_kem_proxy` | Custo de conexão nova |
   |---|---|
   | `localhost:8443` | **2,095s** |
   | `127.0.0.1:8443` | **0,033s** |

   Um "happy eyeballs" IPv6→IPv4 clássico: o Python resolve a string literal
   `"localhost"` para `::1` primeiro, essa tentativa trava/falha, e só depois cai
   para `127.0.0.1` — custando ~2,1s por ocorrência. As três variáveis
   `AUTH_CONNECT_HOST`/`API_CONNECT_HOST`/`DIRECTORY_CONNECT_HOST` do
   `opin_flow.py` construíam o destino do proxy como `f"localhost:{porta}"`. Com
   `N_mTLS = 6` conexões novas, nunca reaproveitadas entre pools, por execução
   completa: 2,095s × 6 ≈ **12,57s** — batendo quase exatamente com o overhead
   observado no lote (+10,66s PQC / +11,98s Híbrido a 0ms). A calibração de stub
   nunca via isso porque descarta de propósito o primeiro request (aquecimento) e
   depois mede 200 requisições reaproveitadas na mesma sessão — exatamente a
   única amostra onde o "happy eyeballs" ocorre é a que a calibração já joga fora.
3. **A decomposição contra o baseline "Go-clássico" está capturando algo a
   mais** — parcialmente verdade, mas sem invalidar a conclusão sobre o custo do
   KEM: o baseline usa exatamente o mesmo caminho `"localhost"`, então o bug
   afeta os dois lados igualmente e se cancela nessa subtração específica (a
   tabela "delta do KEM", de -0,35s a +1,13s, continua válida). O que estava
   errado era a tabela separada de "overhead do proxy" (Go-clássico vs. Clássico
   direto da v5): o lado v5 nunca passou pelo proxy nem pela string
   `"localhost"`, então o gap contaminado caiu inteiro nessa comparação
   específica.

**Correção**: trocar `f"localhost:{TLS_KEM_PROXY_PORT}"` por
`f"127.0.0.1:{TLS_KEM_PROXY_PORT}"` nas três variáveis `*_CONNECT_HOST`
(`opin_flow.py`, linhas 228–230 no estado atual). Validado em três níveis:

| Medição | Antes | Depois |
|---|---|---|
| `fetch_server_keys_and_ca` (3 conexões novas) | 4,149s | **0,064s** |
| Sub-fluxo de seguros, total | 10,547s | **5,621s** |
| Fluxo completo (28 chamadas, Híbrido, 0ms) | ~21–22s | **10,635s** |

O número pós-correção (10,635s, troca de chave ML-KEM real incluída) fica quase
exatamente sobre o `T_fluxo` do Híbrido já existente na v5, a 0ms (10,7295s —
só assinatura, sem proxy, sem KEM). O gap que o lote atribuía a "overhead da
arquitetura de ponte" é, removido o artefato de DNS, estatisticamente
indistinguível de zero — **todo o lote de latência precisou ser refeito** com a
correção aplicada antes de o relatório poder ser considerado válido.

### 3.4. A unificação da v7 — o Clássico passa a usar o mesmo cliente

Até a v6 (trabalho de Nível 1), `tls_kem_proxy` só existia para PQC e Híbrido — o
Clássico conectava direto ao gateway, sem proxy nenhum, porque não precisava
negociar nenhum grupo que o Python não soubesse fazer. Isso criava uma variável de
confusão real para qualquer comparação de latência entre Clássico e os outros
dois perfis: parte de qualquer diferença medida vinha do sistema sob teste (a
troca de chave em si), e parte vinha de qual *implementação de cliente TLS*
(Python direto vs. Go via proxy) estava em uso — uma investigação inteira (v6,
Decision 6/7) foi dedicada a tentar decompor um gap de latência que acabou tendo
boa parte de sua causa nessa própria confusão.

A v7 (Decision 1, `thesis/results/v7/DECISIONS.md`) elimina essa confusão pela
raiz: os três perfis passam a usar o mesmo cliente Go (`tls_kem_proxy`), variando
só a curva pedida — `"classic"` para o Clássico (as mesmas curvas clássicas que já
eram o padrão do gateway, sem nenhum truque de SNI necessário, já que
`CRYPTO_PROFILE=classic` nunca ativa a exceção da Seção 3.2), `"mlkem1024"` para
PQC, `"x25519mlkem768"` para Híbrido. `_USE_TLS_KEM_PROXY` (`opin_flow.py`, linha
215) passa a ser `True` para os três perfis, não só dois:

```python
_USE_TLS_KEM_PROXY = _CRYPTO_PROFILE_FOR_ROUTING in ("classic", "pqc", "hybrid")
```

Com isso, o baseline auxiliar "Go-clássico" que a v6 precisou inventar para
decompor o custo do cliente Go do custo do próprio KEM (Seção 2.4 acima, Decision
2 da v6) deixa de ser necessário daqui para frente — não existe mais nenhum
perfil medido por uma implementação de cliente diferente dos outros dois.

---

## 4. Referência ao código

**`thesis/scripts/tls_kem_proxy/main.go`** (todo o binário do proxy):
- Comentário de topo (linhas 1–46) — visão geral dos dois modos e da garantia de
  1 conexão local → 1 conexão upstream.
- `main()` (linhas 66–82) — parsing de flags, escolha de modo.
- `generateLocalListenerCert()` (linhas 84–119) — certificado ECDSA P-256
  descartável do lado Python-facing.
- `runStub()` (linhas 126–137) — modo de calibração de overhead isolado.
- `runRelay()` (linhas 139–218) — seleção de `CurvePreferences`/`MinVersion` por
  `-curve` (switch nas linhas 161–174), incluindo o caso legado `"classical"`
  (linhas 190–202) que força `ServerName = "matls-api.local"`.
- `handleConn()` (linhas 225–252) — o túnel 1:1, `io.Copy` bidirecional.

**`thesis/scripts/opin_flow.py`**:
- `_USE_TLS_KEM_PROXY` (linha 215) — perfis que passam pelo proxy (os três, desde
  a v7).
- `AUTH_CONNECT_HOST`/`API_CONNECT_HOST`/`DIRECTORY_CONNECT_HOST` (linhas 228–230)
  — `127.0.0.1`, não `"localhost"` (Seção 3.3), desde que `_USE_TLS_KEM_PROXY` é
  verdadeiro.
- `TLS_KEM_PROXY_CURVE_BY_PROFILE` (linha 455) — mapeamento perfil→curva.
- `start_tls_kem_proxy()` (linhas 458–520) — sobe o container de longa duração
  (`docker run`, sem `--rm` implícito num processo por chamada — um processo por
  execução inteira, ao contrário de `_run_pqc_signer()`), monta os argumentos
  `-cert`/`-key`/`-curve`.
- `_wait_for_tls_kem_proxy_ready()` (linhas 523–548) — espera um round-trip HTTP
  real, não um simples connect TCP (o `go run` compila a frio antes de aceitar
  conexões).
- `stop_tls_kem_proxy()` (linha 551 em diante) — encerramento explícito pelo nome
  fixo do container.

**`mock-service-os/mock_mtls/main.go`**:
- `serverCurvePreferences`/`init()` — configuração de curva por
  `CRYPTO_PROFILE` do lado do gateway (ver `thesis/results/v7/artifacts/{pqc,
  hybrid}/README.md`, Seção 4, para a citação de linha exata mais recente).
- `GetConfigForClient` — a exceção por SNI da Seção 3.2 (`hello.ServerName ==
  "matls-api.local"`), com o comentário do código já atualizado
  (`thesis/results/v7/DECISIONS.md`, Decision 6) para deixar essa exceção
  explícita ao lado da política "sem fallback silencioso".

**Decisões e narrativas completas** (este documento resume; os originais têm o
detalhe investigativo passo a passo):
- `thesis/results/v6/Level 1/ARCHITECTURE.md` — o plano original, fase por fase.
- `thesis/results/v6/Level 1/DECISIONS.md`, Decision 1 (SNI), Decision 2 (baseline
  Go-clássico), Decision 3 (bug do `"localhost"`), Decision 4 (degradação do
  Docker Desktop).
- `thesis/results/v5/latency/DECISIONS.md`, Decision 8 — o precedente do custo de
  spawn de subprocess (`_run_pqc_signer()`) que motivou o desenho de processo
  único e longa duração deste proxy.
- `thesis/results/v7/DECISIONS.md`, Decision 1 (unificação dos três perfis),
  Decision 5 (certificado local Python→proxy, reprodutibilidade PQC/Híbrido) e
  Decision 6 (reconfirmação da exceção por SNI, correspondência 1:1).

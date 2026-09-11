# Arquitetura — Cobertura do Nível 1 (troca de chave do TLS)

## O que é este documento

Este é o documento de acompanhamento de um trabalho novo: fazer o handshake mTLS (a parte
que estabelece a conexão segura entre cliente e servidor) também usar criptografia
pós-quântica na troca de chave, não só nas assinaturas.

## Por que este trabalho existe

No documento `thesis/docs/Cruzamento_SAD_vs_Experimentos.md`, cruzamos o que o SAD propõe
com o que os Experimentos 1/2/3 (v5) já cobrem, e achamos uma lacuna: o SAD classifica a
troca de chave do TLS (o mecanismo chamado ECDHE) como urgente pra migrar — porque um adversário pode gravar o tráfego de hoje e descriptografar no futuro,
assim que tiver um computador quântico bom o suficiente (o chamado ataque "colher agora,
decifrar depois"). Mas nos Experimentos 1/2/3, essa troca de chave continua 100% clássica nos
três perfis (Clássico, PQC, Híbrido) — só a assinatura foi migrada até agora.
Este é o trabalho que fecha (parte d)essa lacuna.

## O que entra e o que não entra

**Entra**: a troca de chave do handshake TLS/mTLS — hoje feita só com curvas elípticas
clássicas (ECDHE), passa a usar um mecanismo híbrido que combina a curva clássica com um
algoritmo pós-quântico (ML-KEM).

**Não entra**: a criptografia dos dados em si (o `id_token` e as respostas da API, protegidas por
um envelope chamado JWE, usando RSA-OAEP). Essa parte já foi investigada e confirmada como
**impossível de fazer hoje** — não existe ainda um padrão publicado (JOSE/COSE) que diga como
representar uma chave ML-KEM dentro de um JWE, e a biblioteca usada no projeto não tem esse
suporte.

## Como vai funcionar, em resumo

O gateway mTLS (escrito em Go) é o sistema que estamos testando. No início de toda conexão
TLS, antes de qualquer dado ser trocado, cliente e servidor precisam concordar numa chave
secreta que vai criptografar o resto da conversa — sem nunca transmitir essa chave em texto
claro. Esse acordo é a "troca de chave", e é uma etapa completamente separada da assinatura do
certificado (que só prova identidade). Hoje, esse acordo é feito só com ECDHE — um mecanismo
baseado em curvas elípticas, cuja segurança depende de um problema matemático que o
algoritmo de Shor resolve num computador quântico.

Existem duas formas de trazer o ML-KEM (o algoritmo pós-quântico de encapsulamento de chave)
pra essa etapa, e este trabalho usa as duas, uma em cada perfil que muda:

- **No perfil Híbrido**, o ML-KEM **soma** ao ECDHE, rodando em paralelo — a chave final da
  sessão é derivada da combinação dos dois resultados, não só de um. Segue a mesma lógica de
  "porta AND" que já usamos nas assinaturas híbridas (Seção 4 do documento de arquitetura da
  v5): pra decifrar a conversa, não basta quebrar o ECDHE nem só o ML-KEM — precisa quebrar
  os dois ao mesmo tempo.
- **No perfil PQC**, o ML-KEM **substitui** o ECDHE inteiramente — sem nenhuma curva clássica
  junto, do mesmo jeito que a assinatura desse perfil já é ML-DSA-65 puro, sem RSA nenhum.
  Aqui não tem porta AND com nada clássico, porque esse perfil deliberadamente não mantém
  nenhuma parte clássica em lugar nenhum.

O Clássico não muda — continua só com ECDHE, como sempre foi.

Na prática, isso já vem pronto na biblioteca padrão do Go que o projeto usa — os grupos híbridos
(como `X25519MLKEM768`, que combina a curva clássica X25519 com o ML-KEM-768) já existem
como opção de configuração em `crypto/tls`. Fazer o gateway usar isso é, em essência, mudar a
lista de grupos na configuração do TLS (`mock_mtls/main.go`), não escrever o
mecanismo criptográfico do zero.

---

## Fase 0 — Verificar se dá pra fazer, e como (concluída)

Antes de decidir qualquer coisa, precisávamos confirmar se o gateway (o sistema que estamos
testando) consegue de fato fazer essa troca de chave híbrida.

Fomos direto checar a documentação da versão do Go que o projeto já usa (a mesma imagem que
já roda o assinador ML-DSA-65) e ela já vem com os grupos de troca de chave híbrida prontos
pra usar:

```
X25519MLKEM768     (curva clássica + ML-KEM-768)
SecP256r1MLKEM768
SecP384r1MLKEM1024
MLKEM1024          (só pós-quântico, sem parte clássica)
```

Nada pra instalar, nada pra compilar — já vem de fábrica na mesma versão do Go que o projeto já
usa hoje.

**Conclusão da Fase 0**: dá pra fazer. Não existe nenhum padrão em falta bloqueando esse
caso — o mecanismo já está disponível, pronto pra ser configurado.

---

## Fase 1 — Decidir o desenho da troca de chave em cada perfil

Antes de implementar qualquer coisa, precisamos fechar algumas decisões de desenho. Aqui está
a proposta, com o raciocínio por trás de cada uma — **pendente de aprovação antes de seguir
pra Fase 2**.

### Decisão confirmada: os 3 perfis, não só o Híbrido

Continuam existindo só 3 perfis — Clássico, PQC, Híbrido, nenhum quarto — mas a correção
agora vale para os três, cada um levado até a sua própria lógica:

| Perfil | Assinatura (já existe) | Troca de chave (hoje) | Troca de chave (proposta) |
|---|---|---|---|
| Clássico | RSA, só clássica | ECDHE clássico | **sem mudança** — já está certo |
| PQC | ML-DSA-65, só pós-quântica | ECDHE clássico | **ML-KEM puro**, sem parte clássica |
| Híbrido | RSA+ML-DSA-65, as duas juntas | ECDHE clássico | **ECDHE+ML-KEM híbrido**, as duas juntas |

A ideia é simples de enunciar: **a troca de chave de cada perfil deve seguir a mesma filosofia
que a assinatura daquele perfil já segue**. Hoje isso só é verdade pro Clássico — PQC e Híbrido
têm uma assinatura que já reflete o nome do perfil, mas uma troca de chave que ainda não reflete
nada disso, os três usando exatamente a mesma configuração clássica
([mock-service-os/mock_mtls/main.go:440](mock-service-os/mock_mtls/main.go#L440)). Esse
descompasso é o que este trabalho corrige — em PQC e Híbrido, não só num dos dois.

### Consequência: dois perfis da v5 ficam desatualizados, não só um

**Os números de PQC *e* de Híbrido que já existem na v5** (tabela de tamanho, relatório de
latência, gráficos) vão ficar desatualizados assim que essas mudanças entrarem, porque toda
execução dos dois perfis vai ter uma conexão diferente da que foi medida antes — não dá pra
"somar" o efeito do KEM por cima do que já existe, precisa remedir os dois perfis do zero. É o
mesmo tipo de virada que aconteceu quando a v5 substituiu a v3/v4 — só que dessa vez são dois
perfis específicos dentro da própria v5 que ficam pra trás, não o lote inteiro. **O Clássico
continua intocado e válido** — é o único dos três que já estava correto desde o início.

Quando a Fase 5 (lote completo) estiver pronta e aprovada, será preciso voltar nos seguintes
documentos e atualizar as colunas "PQC" e "Híbrido" (não só "Híbrido"):
- `thesis/results/v5/size/tabela_final_v5.md` e `final_comparative_table_v5.md`
- `thesis/results/v5/size/CONSOLIDATED_REPORT.md`
- `thesis/results/v5/latency/CONSOLIDATED_REPORT.md`
- `thesis/results/v5/docs/Arquitetura_Tecnica_Experimento3_v5.md` (Seção 9 e 9.1)
- `thesis/results/v5/latency/boxplot_pqc_v5.png` e `boxplot_hibrido_v5.png`
- `thesis/docs/Cruzamento_SAD_vs_Experimentos.md` (a tabela de cobertura, já que o Nível 1
  passa a estar coberto nos dois perfis que faziam sentido cobrir)

Isso não precisa ser feito agora — só fica registrado aqui como pendência pra Fase 6
(Relatório), pra não esquecermos nenhum lugar que cita o número antigo.

### O motivo de isolar certo, em cada perfil

O raciocínio de isolamento de variável continua valendo, aplicado separadamente dentro de cada
perfil: a troca de chave nova entra sobre a mesma assinatura já validada daquele perfil (ML-DSA-
65 puro no PQC, RSA+ML-DSA-65 no Híbrido), sem mexer em mais nada. Assim, qualquer
diferença que aparecer nas métricas de cada perfil "novo" em relação à sua versão anterior na v5
só pode vir da troca de chave — que é exatamente o que este trabalho quer medir, perfil por
perfil.

### Qual grupo usar em cada perfil

O Go já oferece quatro opções: `X25519MLKEM768`, `SecP256r1MLKEM768`,
`SecP384r1MLKEM1024`, e `MLKEM1024` (esse último, sem nenhuma curva clássica combinada).

- **Híbrido → `X25519MLKEM768`**: é o grupo que navegadores (Chrome) e provedores grandes
  (Cloudflare) já usam por padrão em produção hoje, então é o que tem mais chance de
  representar o caminho real de adoção do modelo híbrido, não só uma escolha de laboratório.
- **PQC → `MLKEM1024`**: a única das quatro opções sem nenhum componente clássico
  misturado — é o par certo pra um perfil cuja assinatura também não tem nenhum RSA junto.
  Usar um dos grupos híbridos aqui misturaria a filosofia "só pós-quântico" do perfil com uma
  parte clássica que ele deliberadamente não tem em nenhum outro lugar.

**Limitação aceita, e documentada como tal — não como escolha neutra.** Conferimos direto na
documentação do Go (`go doc crypto/tls`, mesma imagem já usada no projeto) que **não existe
um `MLKEM768` puro** — as únicas quatro opções são as já listadas, e a única sem parte clássica
é `MLKEM1024`. Isso significa que o componente ML-KEM do PQC (categoria de segurança NIST 5)
fica num nível diferente do componente ML-KEM que mora dentro do `X25519MLKEM768` do
Híbrido (ML-KEM-768, categoria 3) — os dois perfis passam a usar "tamanhos" de ML-KEM
diferentes um do outro, não por escolha de projeto, mas porque essa é a única opção pura que o
Go oferece. É exatamente o mesmo tipo de situação já registrada no
[thesis/results/v4/ARCHITECTURE.md](thesis/results/v4/ARCHITECTURE.md), Seção 5, quando o
componente RSA do JWT híbrido ficou em 2048 bits em vez dos 3072 que combinariam melhor
com o nível de segurança do ML-DSA-65 — lá, por continuidade com o que já tinha sido medido;
aqui, por não existir alternativa pura na biblioteca. Fica registrado como limitação conhecida,
não como equivalência real entre os dois perfis nesse ponto específico.

### O que muda e o que fica igual

**Deve mudar, em PQC e em Híbrido**: `mTLS_handshake_bytes` (a chave pública do ML-KEM-768
sozinha já tem 1.184 bytes, o ciphertext mais 1.088 — bem mais que os ~32-66 bytes de uma troca
de chave clássica; `MLKEM1024`, usado no PQC, é ainda maior), e por consequência o `OPINsize`
e os totais de tráfego do AS/RS/cliente, que dependem do tamanho do handshake. Latência
(`T_fluxo`) também deve mudar, pelo menos um pouco, nos dois perfis, porque mais bytes
trafegando têm custo de transmissão.

**Não deve mudar, em nenhum dos dois**: tamanho dos JWTs, tamanho do certificado,
`JWK_PK_size` — nada disso depende da troca de chave, só da assinatura, que continua idêntica à
de cada perfil hoje. Vamos confirmar isso no piloto (Fase 4), não só assumir.

**Clássico**: nada muda, em nenhuma métrica — é o único perfil que não é remedido.

### Estrutura de dados

Mesma convenção já usada na v5, guardada numa pasta separada até ser aprovada e só então
substituir a v5 oficialmente:

```
thesis/results/v6/Level 1/experiment2 - PQC/
  {cenário}ms/
    runs/run01..10.json
    median_metrics.json
    report.md

thesis/results/v6/Level 1/experiment3 - Hybrid/
  {cenário}ms/
    runs/run01..10.json
    median_metrics.json
    report.md
```

O Clássico não precisa ser remedido — continua valendo o dado já existente na v5. São o PQC e
o Híbrido que rodam de novo, completos (6 cenários × 10 execuções, tamanho e latência, cada
um).

## Fase 2 — Implementação

Mapeamento de onde cada peça é tocada, por quê, e o que se espera de cada mudança —
**pendente de aprovação antes de escrever qualquer código**.

### 1. O gateway (`mock_mtls/main.go`) — a mudança central

Hoje a configuração TLS do gateway tem uma lista fixa de curvas clássicas
([mock-service-os/mock_mtls/main.go:440](mock-service-os/mock_mtls/main.go#L440)):

```go
CurvePreferences: []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256},
```

Isso passa a variar por perfil, conforme a Fase 1 (`CRYPTO_PROFILE` já governa qual certificado
é servido — a curva passa a ser mais um item condicionado ao mesmo valor):

```go
// PQC: só ML-KEM, sem nenhuma curva clássica junto.
CurvePreferences: []tls.CurveID{tls.MLKEM1024},

// Híbrido: o grupo combinado.
CurvePreferences: []tls.CurveID{tls.X25519MLKEM768},

// Clássico: sem mudança nenhuma.
CurvePreferences: []tls.CurveID{tls.CurveP521, tls.CurveP384, tls.CurveP256},
```

Duas decisões importantes aqui, valendo pros dois perfis que mudam:

- **Sem lista de curvas clássicas junto, nem no PQC nem no Híbrido.** De propósito — se o
  grupo escolhido não estiver disponível dos dois lados, a conexão deve falhar de forma clara,
  não cair silenciosamente para uma curva clássica sem ninguém perceber. É o mesmo cuidado
  que já tomamos com a porta AND dos certificados híbridos: preferimos um erro visível a uma
  degradação silenciosa.
- **`MinVersion` sobe pra TLS 1.3** nesses dois perfis. Os grupos novos só existem dentro do
  TLS 1.3 — não faz sentido deixar `VersionTLS12` como piso pra eles. **Confirmado ao vivo, não
  suposto**: testamos o gateway `CRYPTO_PROFILE=classic` já rodando (`openssl s_client` e o
  mesmo cliente Python que o `opin_flow.py` usa) e os dois negociaram `TLSv1.3` sem forçar nada
  — o Clássico já usa TLS 1.3 na prática hoje, mesmo com `VersionTLS12` como piso permitido.
  Ou seja, subir o piso pra 1.3 em PQC/Híbrido não introduz uma segunda variável nova junto
  com o KEM — é só deixar explícito (`MinVersion: tls.VersionTLS13`) o que já acontece de fato.

Os certificados continuam sendo exatamente os mesmos que cada perfil já usa (`mtls_pqc.crt`/
`.key` e `client_one_pqc.crt`/`.key` no PQC; `mtls_hybrid.crt`/`.key` e
`client_one_hybrid.crt`/`.key` no Híbrido) — só a forma como a chave de sessão é combinada
muda. **Nada muda em [certs/main.go](mock-service-os/certs/main.go).**

### 2. A ponte para rodar os testes — um pequeno proxy em Go, não uma chamada por requisição

O [opin_flow.py](thesis/scripts/opin_flow.py) não consegue negociar nenhum dos dois grupos
novos sozinho (o motivo já está registrado na Fase 0) — isso vale tanto pro PQC quanto pro
Híbrido agora, não só um dos dois. A forma mais simples de resolver seria repetir o padrão do
assinador ML-DSA-65 — chamar um programinha em Go a cada operação que precisar disso. Mas
esse padrão, aplicado aqui, teria um problema real: o fluxo completo faz **28 chamadas HTTP por
execução**, e já vimos, na v5 (Decision 8), que ficar disparando um `docker run` novo a cada
chamada introduz uma variação de tempo que não é do sistema sendo medido, é só do jeito de
rodar o teste — e isso contaminaria justamente a métrica de latência que queremos medir com
precisão.

**Nem uma coisa nem outra — precisa copiar o padrão que já existe hoje, nem mais nem menos.**
Fomos conferir como o `opin_flow.py` já se conecta, e a resposta não é "uma conexão pra tudo"
nem "uma conexão por chamada": ele abre **3 `requests.Session()` distintas por sub-fluxo**
(`simulate_login()` usa a sua própria, de propósito, separada da sessão principal do AS e da do
RS — o comentário no próprio código, em `opin_flow.py:568-571`, já explica que isso existe
justamente pra reproduzir "um terceiro pool de conexão separado, junto dos pools do AS e do
RS"), e o fluxo completo roda dois sub-fluxos (`run_insurance_flow` + `run_person_flow`) — 3
pools × 2 sub-fluxos = as **6 conexões mTLS** que já conhecemos como `N_mTLS = 6`, o mesmo
parâmetro fixo usado na equação OPINsize pros três perfis hoje. Cada uma dessas 6 conexões é
reaproveitada (keep-alive) por todas as chamadas HTTP que pertencem àquele pool — isso já é
comportamento do `requests.Session()` de hoje, sem proxy nenhum.

O proxy precisa preservar exatamente essa contagem, nem criar 28 conexões (uma por chamada
HTTP) nem colapsar tudo numa só. A forma mais direta de garantir isso sem reimplementar a
lógica de pooling é deixar o transporte HTTP padrão do Go (`http.Transport`, que já reaproveita
conexão por destino automaticamente) cuidar disso, mantendo a mesma separação de destino que
o Python já usa hoje — e **confirmar na Fase 3**, contando de verdade quantos handshakes
chegam no gateway durante uma execução completa, que o total bate com 6, não com outro
número.

1. No início de cada execução do fluxo, sobe um processo Go que escuta numa porta local comum
   (ex.: `localhost:8443`), falando HTTP simples — sem TLS nenhum nesse lado.
2. Cada requisição que chega é encaminhada pro gateway de verdade, com o grupo e o certificado
   do perfil ativo (`client_one_pqc` ou `client_one_hybrid`) — reaproveitando a conexão mTLS já
   aberta pra aquele mesmo pool, e só abrindo uma nova quando for, de fato, um pool diferente
   (mesma lógica que o `requests.Session()` do Python já aplica hoje, só que do lado do proxy).
3. O [opin_flow.py](thesis/scripts/opin_flow.py), quando `CRYPTO_PROFILE` é `pqc` ou `hybrid`, só troca a URL base que já usa
   (`https://mtls.local/...`) por `http://localhost:8443/...` — o resto do fluxo (ordem das
   chamadas, lógica de negócio, tudo) continua idêntico ao que já existe hoje. Clássico continua
   indo direto no gateway, sem proxy nenhum.

Como o "salto" entre Python e o proxy é local (mesma máquina, sem rede de verdade no meio), a
expectativa é que o tempo que ele acrescenta à medição seja pequeno — mas isso vai ser medido
de verdade no piloto (Fase 4), não aceito de graça.

### 3. Automação ([median_automation.py](thesis/scripts/median_automation.py), [latency_automation.py](thesis/scripts/latency_automation.py))

Mudança pequena: quando `CRYPTO_PROFILE` é `pqc` ou `hybrid`, subir o proxy da Fase 2.2 no
início de cada execução (ou uma vez por lote, a decidir na prática) e derrubar no fim. O resto —
sequência de cenários, número de execuções, critério de descarte de aquecimento — continua
igual ao que já existe hoje. Só o Clássico não usa o proxy, já que é o único perfil que não muda
de mecanismo de troca de chave.

### 4. O que fica intocado

Vale deixar explícito, porque o alcance da mudança é menor do que parece à primeira vista:
[certs/main.go](mock-service-os/certs/main.go) (nenhum certificado novo), a lógica de assinatura
híbrida em qualquer componente
([hybridSigning.js](mock-service-os/mock_as/utils/opin/hybridSigning.js),
[ResponseSigningService.java](insurance-server-lambdas/src/main/java/com/raidiam/trustframework/mockinsurance/crypto/ResponseSigningService.java),
[payloadExtensionVerification.js](mock-service-os/mock_as/utils/opin/payloadExtensionVerification.js)
— nada disso muda), e os JWKS já publicados. Este trabalho toca só a camada de transporte —
como a conexão é estabelecida — nunca o que é assinado ou como.

## Fase 3 — Prova criptográfica standalone

Antes de confiar em qualquer número do piloto, precisamos provar, isoladamente, que a
engenharia está fazendo o que diz que faz — sem depender de olhar pras métricas finais pra
inferir isso indiretamente.

**O que vai ser testado, especificamente:**

1. **O grupo negociado é mesmo o esperado, em cada perfil.** Capturar o `ConnectionState` do
   Go (ou o log do handshake do lado do proxy) e confirmar, pra uma conexão de cada perfil, que
   o grupo realmente usado foi `MLKEM1024` no PQC e `X25519MLKEM768` no Híbrido — não uma
   negociação silenciosa pra outra coisa. Teste negativo de propósito: apontar um cliente sem
   suporte a esses grupos contra o gateway nesses dois perfis e confirmar que a conexão **falha
   de forma visível**, não cai pra clássico (é a mesma garantia que já documentamos na Fase 2,
   agora testada de verdade, não só configurada).
2. **O número de conexões mTLS bate com 6, não com 1 nem com 28.** Contar, direto no log do
   gateway ou instrumentando o proxy, quantos handshakes de verdade acontecem durante uma
   execução completa do fluxo (`run_insurance_flow` + `run_person_flow`) passando pelo proxy —
   tem que dar exatamente 6, igual ao que Clássico e PQC (antes desta mudança) já produzem sem
   proxy nenhum. Se der outro número, o proxy está juntando ou separando conexões de um jeito
   que não reflete o comportamento real, e precisa ser corrigido antes de qualquer medição valer.
3. **O restante do fluxo continua funcionando fim a fim.** Rodar o fluxo completo (28 chamadas)
   uma vez em cada perfil (PQC e Híbrido) através do proxy e confirmar que termina sem erro, com
   as mesmas respostas de negócio de sempre — a mudança é só na camada de transporte, então
   nada na lógica de consentimento/token/dados deve quebrar.

### Resultado (concluída)

Um bloqueio real apareceu no meio do caminho — não estava previsto neste plano, está documentado
em detalhe em `DECISIONS.md` (Decision 1 deste diretório). Resumo: mudar o `CurvePreferences` do
gateway inteiro quebrou uma chamada interna do próprio `auth` (`InsurerAdapter.getConsent()`, que
já era clássica por decisão anterior, Decision 5 da v5) — corrigido diferenciando por SNI
(`hello.ServerName == "matls-api.local"` continua clássico; qualquer outro usa o grupo do perfil).
Depois da correção, os três itens acima foram confirmados nos dois perfis:

| Item | PQC | Híbrido |
|---|---|---|
| Grupo negociado (positivo) | `MLKEM1024`, confirmado no log do proxy e do gateway | `X25519MLKEM768`, idem |
| Teste negativo (cliente incompatível) | Falha visível (`Cipher is (NONE)`), sem downgrade | Idem |
| Conexões mTLS externas | 7 = 6 reais + 1 do probe de prontidão do proxy (a excluir na Fase 5) | Idem, 7 |
| Conexões internas (`auth`→RS) | 7, todas `CurveP256` (correção da SNI funcionando) | Idem, 7 |
| Fluxo completo (28 chamadas) | Sucesso, reproduzido 2x | Sucesso |

O número "6" em si não aparece diretamente no log (aparece "7"), mas está totalmente explicado:
o probe de prontidão do `opin_flow.py` (`_wait_for_tls_kem_proxy_ready`) abre uma conexão real
extra antes do fluxo começar. Fica registrado aqui como item a excluir da contagem oficial quando
a Fase 5 (lote completo) rodar — não é um bug, é uma conexão de infraestrutura de teste que não
deve entrar na métrica.

## Fase 4 — Piloto

Um cenário (0ms), 10 execuções, em cada um dos dois perfis que mudam (PQC e Híbrido) —
antes de autorizar o lote completo de 6 cenários.

**O que o piloto mede, além do de sempre:**

1. **As métricas de sempre** — `mTLS_handshake_bytes`, `OPINsize`, `T_fluxo` — comparadas
   contra os valores atuais da v5 pra confirmar que a diferença aparece onde esperamos (handshake
   e o que depende dele) e não aparece onde não deveria (JWTs, certificado, `JWK_PK_size`).
2. **Calibração isolada do overhead do próprio proxy**, feita **antes** de aceitar como
   desprezível qualquer diferença de tempo. O proxy roda num modo à parte, só pra essa
   calibração: responde direto (um eco, ou uma resposta fixa) sem tocar o gateway nenhuma vez.
   Mede-se o tempo de ida e volta Python↔proxy nesse modo, isoladamente, e só depois compara
   esse número contra o `T_fluxo` total medido com o proxy real (proxy↔gateway incluso). Se o
   overhead isolado do proxy for uma fração pequena e estável do T_fluxo total, a suposição de
   "desprezível" fica confirmada com número, não assumida.
3. **Confirmação de que a Fase 3 se sustenta em execução repetida**, não só numa vez: as 10
   execuções do piloto devem produzir sempre 6 conexões mTLS (não variar), e sempre o grupo
   esperado — qualquer variação aqui é um problema a investigar antes do lote completo, não
   uma média a aceitar.

Reportado antes de autorizar o lote completo (Fase 5), com os três pontos acima respondidos com
número, não com expectativa.

### Resultado (concluída)

**Calibração do proxy** (feita antes de qualquer piloto, modo eco): mediana 1,91ms, média 2,02ms
por chamada — desprezível frente a T_fluxo em segundos.

**Um problema real apareceu no meio do caminho**: a métrica `handshake_bytes` do primeiro piloto
saiu *menor* com ML-KEM do que o número clássico da v5, o oposto do esperado. Investigado a fundo
(capturas de `ClientHello` decompostas, teste controlado isolando só a curva) — a causa não é o
ML-KEM, é a troca do cliente TLS (Python→Go via proxy) mudando a comparação de base. Documentado
em detalhe no `DECISIONS.md` (Decision 2). Solução: um baseline auxiliar "Go-clássico" (mesmo
cliente Go, curva clássica), usado só para calcular o delta do ML-KEM de forma isolada — nunca
substitui o Clássico oficial da v5 para nenhuma outra comparação da tese.

**Piloto completo (primeira rodada), 0ms, 10 execuções por linha, 0% de spread em tamanho:**

| Métrica | Go-clássico (baseline auxiliar) | PQC (Go+KEM) | Híbrido (Go+KEM) |
|---|---|---|---|
| `mtls_handshake_bytes` | PQC: 13.525 · Híbrido: 15.743 | 16.605 (Δ +3.080) | 18.023 (Δ +2.280) |
| `jwt_size_avg_bytes` | — (não remedido, não depende do cliente TLS) | 5.458,81 (idêntico à v5) | 7.324,81 (idêntico à v5) |
| `client_cert_der_bytes` | — | 2.953 (idêntico à v5) | 6.859 (idêntico à v5) |
| `T_fluxo` mediana | — | 20,99s | 21,82s |
| `T_fluxo` spread | — | 3,12% | 5,47% |
| Conexões mTLS externas | — | 7 = 6 reais + 1 do probe de prontidão | 7, idem |
| Conexões internas (`auth`→RS) | — | 7, `CurveP256` | 7, `CurveP256` |

**Nota importante sobre `handshake_bytes`**: essa linha usa uma referência diferente do resto da
tabela — o "Go-clássico" em vez do Clássico oficial da v5 — porque é a única comparação válida
pra essa métrica específica (ver `DECISIONS.md`, Decision 2, pro motivo técnico completo). Todas
as outras métricas continuam comparáveis diretamente contra a v5, sem ressalva.

**Os `T_fluxo` desta primeira rodada do piloto (20,99s/21,82s) foram posteriormente invalidados**
e não são os números finais. Autorizado o lote completo com base neles (tamanho estava correto,
que é o que mais importava para a Fase 5 de tamanho), mas a mesma discrepância que a calibração
do proxy já sinalizava (~2ms em modo eco vs os ~1,7-2s por conexão implícitos aqui) foi investigada
a fundo depois, por exigência explícita, e revelou uma causa real: `opin_flow.py` resolvia o
proxy local por `"localhost"`, disparando um fallback IPv6→IPv4 de ~2,1s por conexão nova em cada
uma das 6 conexões mTLS do fluxo (Decision 3, `DECISIONS.md`). Corrigido (`"localhost"` →
`"127.0.0.1"`), o piloto foi refeito do zero: um resíduo de ~2s específico do Híbrido apareceu,
foi investigado (não aceito como ruído) e rastreado a degradação cumulativa do ambiente Docker
Desktop ao longo da sessão, não ao KEM nem ao certificado Híbrido (Decision 4). **Piloto final,
pós-correção, ambiente validado por 2h20m de medições estáveis:**

| Métrica | Go-clássico/PQC-cert | PQC (Go+KEM) | Go-clássico/Hybrid-cert | Híbrido (Go+KEM) |
|---|---|---|---|---|
| `T_fluxo` mediana | 9,81s | 10,18s | 11,79s | 10,90s |
| `T_fluxo` spread | 15,1% | 26,3% | 15,7% | 16,8% |

Ambos dentro de ~0,2s da v5 (PQC 10,13s, Híbrido 10,73s) — piloto aprovado para o lote completo
com estes números como referência, não os da primeira rodada.

## Fase 5 — Lote completo

**Etapa 1 (tamanho), concluída**: 240 execuções (6 cenários × 10 × 4 séries: PQC+KEM,
Go-clássico/PQC-cert, Híbrido+KEM, Go-clássico/Hybrid-cert). 0% de spread em toda métrica, todo
cenário — idêntico ao piloto, sem exceção. 1 retry de execução inteira (Híbrido/30ms, race já
conhecida das Decisions 5/9). Rodada com um bug de assentamento não descoberto ainda (Decision 5)
na troca para PQC — sem consequência, já que tamanho não depende de tempo.

**Etapa 2 (latência), concluída**, após corrigir o bug de assentamento e confirmar (Decision 5)
que ele funciona corretamente nas duas trocas de perfil: 240 execuções, 0 falhas, 0 retries.
Delta do ML-KEM desprezível (-0,12s a +0,44s) em todos os 6 cenários, não só em 0ms. Uma
comparação v6-vs-v5 mostrou v6 mais rápido em alta latência — investigada antes de aceitar como
achado (Decision 6): é um efeito de implementação do cliente TLS (Go vs Python), não do Nível 1.

Números completos e tabelas em `CONSOLIDATED_REPORT.md`.

## Fase 6 — Relatório

`CONSOLIDATED_REPORT.md` (este diretório) tem o relatório final consolidado — tamanho, latência,
confiabilidade da execução e localização dos dados. Pendências que ficam para fora do escopo do
Nível 1 em si (atualizar documentos da v5 que citam números pré-Nível-1, atualizar o cruzamento
SAD) estão listadas na seção final desse relatório.

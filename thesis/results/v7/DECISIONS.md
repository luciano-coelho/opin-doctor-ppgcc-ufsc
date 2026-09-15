# Decisions — v7 (rodada final consolidada)

## 1. Unificação dos 3 perfis sob o mesmo cliente/proxy Go — eliminando de vez a variável de confusão Python-vs-Go que dominou a investigação do Nível 1 (v6)

**Contexto.** A v5 mediu Clássico, PQC e Híbrido com o cliente Python direto,
sem troca de chave pós-quântica nenhuma (ECDHE clássico nos três perfis). O
Nível 1 (`thesis/results/v6/Level 1/`) migrou a troca de chave de PQC e
Híbrido para ML-KEM, mas só desses dois perfis — e só foi possível porque
Python/OpenSSL não sabe negociar grupos ML-KEM, exigindo uma ponte
(`tls_kem_proxy`, cliente Go) só para PQC/Híbrido, enquanto o Clássico
continuou em Python direto.

Essa divisão (Clássico em Python, PQC/Híbrido em Go via proxy) introduziu
exatamente o tipo de variável de confusão que este projeto tenta eliminar em
todo experimento: qualquer diferença entre Clássico e os outros dois perfis
passou a carregar, embutido, um efeito de implementação de cliente TLS, não
só o efeito da criptografia em si. O histórico completo dessa investigação
está em `thesis/results/v6/Level 1/DECISIONS.md`:

- **Decision 2**: `handshake_bytes` saiu *menor* com ML-KEM que o número
  clássico da v5 — o oposto do esperado. Causa: comparar Python/OpenSSL
  (v5) contra Go (v6) não isola o efeito do ML-KEM, é uma comparação de
  clientes TLS diferentes. Precisou de um baseline auxiliar "Go-clássico"
  só para ter uma referência mesmo-cliente.
- **Decision 3**: um artefato de resolução de DNS (`"localhost"` vs
  `"127.0.0.1"`) específico do processo proxy inflou `T_fluxo` em
  ~10-12s, inicialmente mal-atribuído a "overhead da arquitetura de
  proxy".
- **Decision 6**: mesmo depois de corrigido o artefato acima, v6 (com
  proxy) apareceu consistentemente *mais rápido* que a v5 (Python direto)
  em cenários de alta latência — rastreado a uma diferença de eficiência
  de round-trip entre os clientes TLS do Go e do Python, confirmada só com
  um teste controlado dedicado.
- **Decision 7**: uma tentativa de fechar esse resíduo levou a uma
  atribuição causal errada (confundida com uma chamada interna
  auth→RS que na verdade já é filtrada por certificado antes de qualquer
  estatística oficial) — corrigida depois de auditoria direta do dado já
  commitado.

Cada uma dessas decisões só existiu porque **dois clientes TLS diferentes
(Python e Go) estavam sendo comparados entre si**, além da criptografia.
Nenhuma delas seria necessária se todos os perfis usassem o mesmo cliente
desde o início.

**Decisão.** A partir da v7, **os três perfis — Clássico, PQC e Híbrido —
rodam pelo mesmo `tls_kem_proxy`, variando só o grupo de troca de chave**:

| Perfil | Grupo de troca de chave | Curva no `tls_kem_proxy` |
|---|---|---|
| Clássico | ECDHE clássico (P-521/P-384/P-256) | `-curve classic` |
| PQC | `MLKEM1024` | `-curve mlkem1024` |
| Híbrido | `X25519MLKEM768` | `-curve x25519mlkem768` |

O Clássico nunca precisou de nenhum truque de SNI (o carve-out da Decision
1 do v6, `matls-api.local` → curvas clássicas): o próprio `CRYPTO_PROFILE=
classic` já deixa `mock_mtls`'s `serverCurvePreferences` no seu valor
padrão, que já é essa mesma lista clássica
(`mock-service-os/mock_mtls/main.go`, variável de pacote, não tocada pelo
`init()` para o caso `classic`). Bastou adicionar o valor `"classic"` ao
`switch` de curvas do `tls_kem_proxy` (`thesis/scripts/tls_kem_proxy/
main.go`) — sem forçar SNI, ao contrário do valor `"classical"` já
existente (que força `matls-api.local` e continua existindo só para
eventuais reruns diagnósticos do baseline "Go-clássico" da v6, hoje
obsoleto).

**Consequência prática**: com os três perfis no mesmo cliente,
**o baseline auxiliar "Go-clássico" da v6 deixa de ser necessário** — não
existe mais nenhum efeito de implementação de cliente para isolar, então
qualquer diferença entre perfis na v7 é, por construção, só efeito da
criptografia (assinatura + troca de chave) sendo medida. Isso simplifica a
v7 para 3 perfis × 6 cenários × 10 execuções (tamanho e latência,
separadamente) — sem a quarta série "baseline" que o Nível 1 precisou.

**Mudanças de código.**
- `thesis/scripts/tls_kem_proxy/main.go`: novo valor `"classic"` no
  `switch` de curvas (linha do `runRelay`), classical `CurvePreferences`
  sem forçar SNI — distinto do `"classical"` pré-existente.
- `thesis/scripts/opin_flow.py`: `_USE_TLS_KEM_PROXY` agora inclui
  `"classic"`; `TLS_KEM_PROXY_CURVE_BY_PROFILE` ganha a entrada
  `"classic": "classic"`. `AUTH_CONNECT_HOST`/`API_CONNECT_HOST`/
  `DIRECTORY_CONNECT_HOST` passam a apontar pro proxy também para o
  Clássico (antes iam direto pro gateway).
- `thesis/scripts/switch_crypto_profile.py`: removida a exceção que pulava
  o proxy para `"classic"`.
- `thesis/scripts/median_automation.py`/`latency_automation.py`: nenhuma
  mudança de lógica necessária — já chamavam `start_tls_kem_proxy()`
  incondicionalmente, contando com o próprio retorno `None` da função para
  perfis não reconhecidos; `"classic"` agora é reconhecido.

**O que isso não muda**: a assinatura de cada perfil continua exatamente a
mesma da v5/v4 (RSA puro no Clássico, ML-DSA-65 puro no PQC, RSA+ML-DSA-65
no Híbrido, payload-extension para JWTs de cliente) — só a camada de troca
de chave TLS e o cliente que a executa mudaram. Ver Decision 2 para o
escopo completo (fusão Nível 1 + Nível 2 num único lote de medição).

## 2. Escopo: Nível 1 (troca de chave) e Nível 2 (assinatura) medidos juntos, não mais em lotes separados

**Decisão.** Cada perfil roda de uma vez com sua arquitetura de assinatura
final (idêntica à v5/v4) *e* sua troca de chave correspondente (idêntica ao
Nível 1 do v6, agora também para o Clássico, que já estava correto). Não
há mais uma v5 "só assinatura" e um v6 "só troca de chave" separados — a
v7 é o retrato único e final dos dois níveis juntos, substituindo ambas.

## 3. Protocolo de coleta — mesmo rigor já validado na v5 e no Nível 1 (v6)

- 6 cenários de latência (0/14/30/140/225/320ms) × 10 execuções × 3
  perfis, para tamanho e para latência, nesta ordem (tamanho completo,
  sabatina, aprovação; depois latência).
- `runs/run01..10.json` (mais `run00_warmup.json` na latência) como fonte
  primária; `median_metrics.json`/`report.md` (ou `MEDIAN_REPORT.md`) como
  derivado — mesma convenção da v5.
- Relógio monotônico para `T_fluxo`, sem remoção de outliers, retry conta
  só a partir da tentativa bem-sucedida, assentamento após toda troca de
  `CRYPTO_PROFILE` (`switch_crypto_profile.py`, Decision 4/5 do v6),
  checkpoints de anomalia antes de aceitar qualquer cenário como fechado.
- Estrutura: `thesis/results/v7/size/experiment{1,2,3} -
  {Classic,PQC,Hybrid}/{cenário}ms/` e `.../latency/...`, espelhando a v5.
- `thesis/results/v7/artifacts/`: uma captura não-estatística (1 amostra,
  não 10) por perfil dos artefatos criptográficos reais em uso —
  certificado, JWT real decodificado, entrada JWKS real, evidência do
  grupo de troca de chave negociado no handshake. Detalhe e cronograma na
  Fase correspondente, não bloqueia o lote de tamanho/latência.

## 4. `total_bytes_exchanged` do Clássico sobe +376 bytes na v7 em relação à v5 — causa principal confirmada, resíduo pequeno não fechado

**Contexto.** Na sabatina da Etapa de tamanho, o Clássico da v7 mostrou
`total_bytes_exchanged` = 66.828 contra 66.452 da v5 (+376 bytes), apesar
de `handshake_bytes` ter caído 4.666 bytes (9.785 → 5.119) no mesmo perfil
-- perguntado explicitamente se o total inclui o handshake (não inclui) e,
se não inclui, de onde vêm os +376.

**Confirmado, não suposto.** `total_bytes_exchanged` (`baseline_automation.
py:643-644,706`) é `sum(req_bytes + resp_bytes for c in all_calls)` --
tráfego de aplicação (headers HTTP + corpo) medido client-side, nunca toca
`gateway_metrics`/`handshake_bytes`. As duas métricas são independentes por
design; não há razão para se moverem juntas.

**Causa principal, confirmada via `git log -S` e medição ao vivo.** Toda
lógica de `host_header=` em `opin_flow.py` (o parâmetro em `do_call()` e o
`session.headers["Host"] = AUTH_HOST` de `simulate_login()`) foi introduzida
no commit `e88e373` -- o mesmo commit do Nível 1 (v6) que criou o
`tls_kem_proxy`. Faz sentido: o proxy tunela bytes crus, não roteia por
Host, então o cliente precisa declarar o Host explicitamente para o
roteamento HTTP continuar funcionando através dele -- necessário desde
sempre para PQC/Híbrido (v6), e agora, com a unificação da v7 (Decision 1),
também para o Clássico, que nunca precisou disso enquanto conectava direto
ao gateway. Medido ao vivo (instrumentando `header_bytes()` num fluxo
Clássico completo, 28 chamadas): os headers `Host:` somam exatamente **520
bytes**, nenhum dos quais existia antes desse commit -- confirmado via
`git log -S` que nenhuma dessas linhas predata o Nível 1.

**Resíduo não fechado, reportado com essa precisão.** 520 bytes de `Host:`
novo excede os 376 observados -- sobram **~144 bytes (≈5 bytes/chamada)**
que precisariam ter caído em outro lugar para compensar exatamente. Descartada
diferença de versão do `requests` (2.34.2 fixado em `requirements.txt`,
mesmo venv desde sempre neste projeto). Não investigado além disso --
**decisão do usuário, explícita**: o resíduo é ~0,2% do total trafegado do
Clássico, pequeno demais para comprometer qualquer conclusão da tese,
categoricamente diferente do gap de latência do Nível 1 (Decision 6/7 do
v6), que era uma fração grande de um número que sustentava um achado
central. Registrado como confirmado-na-causa-principal,
não-fechado-no-resíduo, sem arredondar para 100% nem reabrir investigação
que o próprio usuário julgou desnecessária.

## 5. Reprodutibilidade PQC/Híbrido quebrada nesta máquina por mudança externa de ambiente — corrigida removendo uma apresentação de certificado local que nunca teve efeito real

**Contexto.** Ao construir `thesis/results/v7/artifacts/pqc/`, um script de
captura standalone (`thesis/scripts/_capture_pqc_artifacts.py`) falhou ao
rodar o fluxo PQC real: `ssl.SSLError: [SSL: EE_KEY_TOO_SMALL]`, ao tentar
carregar `client_one_pqc.crt/.key` para a conexão HTTPS local
(`127.0.0.1:8443`, o listener do `tls_kem_proxy`). A hipótese inicial —
que isso fosse uma particularidade só do script de diagnóstico — foi
testada diretamente a pedido do usuário, e refutada: `median_automation.
run_once("pqc", 0)`, chamando `opin_flow.run_insurance_flow()`/
`run_person_flow()` **sem nenhuma modificação** (o caminho de código exato
que gerou o lote de tamanho/latência PQC da v7, commitado em 2026-09-12),
falhou nesta máquina agora com o mesmo erro, na mesma chamada
(`do_call()` → `session.request(cert=cert, ...)` → `urllib3` →
`ssl.SSLContext.load_cert_chain()`).

**Causa raiz, confirmada.** `do_call()` recebe `cert` de
`get_client_cert_paths(crypto_profile)`, calculado uma vez no topo de
`run_insurance_flow()`/`run_person_flow()` e usado, sem distinção, tanto
para a perna real (Go→gateway, dentro do `tls_kem_proxy`, iniciada por
`start_tls_kem_proxy()`) quanto para a perna local
(Python→`tls_kem_proxy`, via `requests`). A perna local **nunca precisou de
certificado nenhum**: `tls_kem_proxy`'s listener local
(`thesis/scripts/tls_kem_proxy/main.go`, `generateLocalListenerCert()`)
constrói seu `tls.Config` sem definir `ClientAuth` — o padrão do Go é
`tls.NoClientCert`, confirmado lendo o código, não suposto — então
qualquer certificado que o Python apresentasse ali sempre foi descartado
sem verificação. Isso nunca causou problema para Clássico/Híbrido porque
`client_one.crt`/`client_one_hybrid.key` são chaves RSA comuns, que o
OpenSSL sempre soube carregar independentemente de serem realmente
necessárias. Para PQC, `client_one_pqc.key` é uma chave ML-DSA-65 nativa
(PKCS8) que o OpenSSL 3.0 padrão deste host não consegue analisar — testado
isoladamente, sem nenhuma atividade de rede envolvida
(`ssl.SSLContext.load_cert_chain()` sozinho já falha com o mesmo erro).

**Por que isso quebrou agora e não em 2026-09-12.** Os arquivos
`client_one_pqc.crt`/`.key` no repositório não mudaram (confirmado via
`git status` e timestamps — Aug 8/Aug 22, muito antes da v7). O mesmo
código, sem nenhuma edição, gerou um lote de 180 execuções PQC bem-sucedidas
há um dia e falha agora. A causa mais provável é uma atualização externa
do OpenSSL/Windows entre as duas datas, fora do controle deste projeto —
não determinada com mais precisão que isso (não investigada além do
necessário para confirmar que não é um problema deste código ou dos
certificados commitados).

**Correção aplicada.** Nova função `get_local_leg_cert_paths()` em
`opin_flow.py`, usada apenas nas duas atribuições de `cert` dentro de
`run_insurance_flow()`/`run_person_flow()` (não em `start_tls_kem_proxy()`,
que continua usando `get_client_cert_paths()` real para a perna que
importa): para `pqc`/`hybrid`, retorna `None` — nenhum certificado é mais
apresentado na perna local, para nenhum dos dois perfis. `classic` não foi
alterado (nunca esteve quebrado, e o escopo desta correção é os dois
perfis afetados).

**Por que a correção é segura.** Remove exclusivamente algo cosmético: uma
apresentação de certificado que o listener local nunca inspecionava, nunca
usava para decidir nada, e cuja ausência não muda em nada qual identidade
chega ao gateway real — essa continua sendo definida inteiramente pela
conexão Go→gateway dentro do `tls_kem_proxy`, iniciada com o certificado
real (`get_client_cert_paths()`, inalterado) antes de qualquer chamada
HTTP acontecer. Não altera `client_cert_der_bytes()` (mede o arquivo do
disco diretamente, nunca tocou essa perna), não altera nenhuma métrica de
handshake/bytes já coletada (todas vêm do `mock_mtls`'s
`countingConn`/log do gateway, do lado da conexão real, nunca do lado
Python↔proxy), e não altera o comportamento de nenhum perfil que já
funcionava (`classic` intocado; `hybrid` só deixa de fazer algo que nunca
teve efeito).

**Escopo da correção — não invalida nem exige refazer nada já commitado.**
O lote de tamanho/latência PQC/Híbrido da v7 (2026-09-12) já foi coletado
com sucesso nesta mesma máquina, antes da mudança externa de ambiente que
quebrou a reprodutibilidade — esse dado permanece válido e não foi
re-coletado. Esta correção existe unicamente para que uma nova coleta PQC
nesta máquina, no futuro (por exemplo, para reproduzir os resultados da
tese numa banca ou auditoria), volte a funcionar. Confirmado ao vivo,
depois da correção: `median_automation.run_once("pqc", 0)` — o mesmo
código oficial, agora sem a apresentação cosmética — completou um fluxo
PQC real de 28 chamadas com sucesso.

**Nota à parte, não investigada, fora de escopo**: `git status` também
mostrou `thesis/results/v6/Level 1/size/experiment2 - PQC/320ms/` com
`median_metrics.json`/3 `runs/*.json` modificados desde 2026-09-11 (antes
de qualquer trabalho desta sessão v7), reduzindo `run_count` de 10 para 3
nesse cenário. Não investigado nem corrigido — decisão explícita do
usuário: v6 deixa de ser fonte oficial assim que a v7 for consolidada
(mesmo status histórico de v1–v4), não vale o tempo de investigar um dado
que já será descontinuado.

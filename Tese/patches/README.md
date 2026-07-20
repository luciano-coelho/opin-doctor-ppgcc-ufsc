# Patches — Conformance Suite

`insurance-server-lambdas/conformance-suite/` é clonada sob demanda (`make setup-cs`) a partir de `gitlab.com/raidiam-conformance/open-insurance/open-insurance-brasil`, e é ignorada pelo git deste projeto (`insurance-server-lambdas/.gitignore`). Por isso as versões modificadas desses arquivos ficam preservadas aqui — sem isso, os patches se perderiam a cada novo clone.

## Como aplicar

Depois de rodar `make setup-cs` (clona `conformance-suite/`), copie estes arquivos para os caminhos equivalentes dentro da pasta clonada, sobrescrevendo os originais:

| Arquivo aqui | Destino em `insurance-server-lambdas/conformance-suite/` |
|---|---|
| `testmodule-support/OpinSetDirectoryInfo.java` | `src/main/java/net/openid/conformance/opin/testmodule/support/OpinSetDirectoryInfo.java` |
| `testmodule-support/CheckOpinDirectoryApiBase.java` | `src/main/java/net/openid/conformance/opin/testmodule/support/CheckOpinDirectoryApiBase.java` |
| `testmodule-support/CheckOpinDirectoryDiscoveryUrl.java` | `src/main/java/net/openid/conformance/opin/testmodule/support/CheckOpinDirectoryDiscoveryUrl.java` |
| `testmodule-support/OpinCallDirectoryParticipantsEndpoint.java` | `src/main/java/net/openid/conformance/opin/testmodule/support/OpinCallDirectoryParticipantsEndpoint.java` |
| `server-dev/Dockerfile` | `server-dev/Dockerfile` (corrige quebra de linha malformada + imagem base descontinuada) |
| `httpd/Dockerfile-static` | `httpd/Dockerfile-static` (corrige imagem base `debian:buster` descontinuada) |

Depois de copiar, rebuilde o jar (`make setup-cs` novamente — fase de build, ~15-20min) e recrie o container: `docker-compose up -d --force-recreate cs-server` dentro de `insurance-server-lambdas/`.

## Por que esses patches existem

A suíte, por padrão, valida (e em um caso, chama diretamente) o Directory real da Raidiam (`*.sandbox.directory.opinbrasil.com.br`), com URLs **hardcoded** em código-fonte — não configuráveis via JSON. Rodando 100% offline/local, isso falha com erro de TLS (`unknown_ca`) ou com a mensagem "Testing for Brazil certification must be done using the Brazil directory". Os patches:

1. **`OpinSetDirectoryInfo`** — passa a usar `directory.discoveryUrl`/`apibase`/`keystore` do config em vez das URLs fixas da Raidiam.
2. **`CheckOpinDirectoryApiBase`** / **`CheckOpinDirectoryDiscoveryUrl`** — passam a aceitar `https://directory/` como URL válida, além das da Raidiam.
3. **`OpinCallDirectoryParticipantsEndpoint`** — monta a URL de `/participants` a partir de `directory.apibase` do config, em vez de uma URL fixa.

Ver `../README.md` para o contexto completo de como esses patches se encaixam na coleta de baseline.

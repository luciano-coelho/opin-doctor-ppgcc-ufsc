# Tese — Automação de Baseline (Migração PQC)

Ferramentas e dados coletados para a tese de doutorado sobre migração de criptografia clássica para pós-quântica (PQC) no ecossistema Open Insurance Brasil (OPIN), usando o ambiente local **MockOPIN** como banco de testes.

## Estrutura

```
Tese/
├── README.md                     este arquivo
├── scripts/
│   ├── baseline_automation.py    automação principal: cria planos, roda os
│   │                              módulos "happy path", exporta logs e calcula
│   │                              as métricas de baseline
│   └── check_plan_modules.py     script de diagnóstico rápido — cria um plano
│                                  e imprime os nomes exatos dos módulos que a
│                                  Conformance Suite reconhece (útil antes de
│                                  adicionar um novo plano em PLANS)
├── config/
│   ├── config_template_consents_v3.json   config validado do plano
│   │                                        "Insurance consents api test V3.0.0"
│   └── config_template_person_v2.json     config validado do plano
│                                            "person_test-plan_v2.0.0"
├── resultados/
│   └── baseline/
│       ├── RELATORIO_BASELINE.md          relatório final tabulado
│       ├── metricas_baseline.json         métricas agregadas (bytes, latência
│       │                                    por endpoint, tamanhos de JWT)
│       └── <plano>__<modulo>_<timestamp>.json   logs brutos exportados da
│                                                  Conformance Suite, sem
│                                                  qualquer alteração
├── logs/
│   └── execution_log_20260720.txt         stdout completo da execução que
│                                            gerou os resultados atuais
└── patches/
    └── ...                                 versoes patchadas dos arquivos da
                                             Conformance Suite (ver patches/README.md
                                             — necessario porque essa pasta e
                                             clonada sob demanda e ignorada pelo git)
```

## Pré-requisitos de infraestrutura

A automação depende do ambiente MockOPIN completo rodando (`make run-with-cs` na raiz do projeto), **com patches aplicados no código-fonte da Conformance Suite** (preservados em [`patches/`](patches/README.md) já que essa pasta é clonada sob demanda e ignorada pelo git) — sem eles a suíte tenta validar contra o Directory real da Raidiam e falha imediatamente:

| Arquivo (em `insurance-server-lambdas/conformance-suite/src/main/java/net/openid/conformance/opin/testmodule/support/`) | Mudança |
|---|---|
| `OpinSetDirectoryInfo.java` | usa `directory.discoveryUrl`/`apibase`/`keystore` do config em vez de URLs fixas do sandbox Raidiam |
| `CheckOpinDirectoryApiBase.java` | aceita `https://directory/` como URL válida (além das da Raidiam) |
| `CheckOpinDirectoryDiscoveryUrl.java` | aceita `https://directory/.well-known/openid-configuration` como URL válida |
| `OpinCallDirectoryParticipantsEndpoint.java` | monta a URL de `/participants` a partir de `directory.apibase` em vez de URL fixa |

Depois de qualquer alteração nesses arquivos é preciso rebuildar (`make setup-cs` — fase de build, ~15-20min) e recriar o container: `docker-compose up -d --force-recreate cs-server`.

**Nota sobre o `preflight`:** mesmo com os patches, o módulo `opin-consents_api_preflight_test-module_v3` sempre termina com `result=FAILED`. Isso vem de duas condições internas da própria lib da suíte (`OpinCheckDirectoryDiscoveryUrl`/`OpinCheckDirectoryApiBase`, empacotadas num `.jar` de dependência — não editáveis) que insistem em exigir o Directory real da Raidiam. Como são `continue-on-failure`, o resto do fluxo roda normalmente e o tráfego real é capturado no log — só o rótulo de resultado fica errado. É esperado e documentado no próprio script.

## Configurações (`config/`)

Os dois arquivos usam **`"alias": "mock"` obrigatoriamente** — a Conformance Suite monta o `redirect_uri` OAuth como `https://.../test/a/{alias}/callback`, e o único `redirect_uri` registrado para o `client_one` (em `insurance-server-lambdas/software_statement.json`) é `.../test/a/mock/callback`. Qualquer outro alias quebra a autenticação com `redirect_uri did not match any of the client's registered redirect_uris`.

Certificados, JWKS e CA usados nos configs vêm de `mock-service-os/certs/` (client_one).

## Como rodar

```bash
cd Tese/scripts
python baseline_automation.py
```

Alguns módulos (os que criam/consultam consentimento de verdade) pausam em `status=WAITING` esperando login + consentimento manual — o script imprime a URL no terminal e continua o polling sozinho assim que detecta o redirect real. Credenciais do usuário mock: `usuario1@seguradoramodelo.com.br` / `P@ssword01`.

Para investigar um plano novo antes de automatizar:

```bash
python check_plan_modules.py
```

## Métricas coletadas

- **Bytes totais trocados** no fluxo completo (OPINsize clássico) — soma de headers + body de todas as chamadas HTTP reais.
- **Latência por endpoint** — média, P50, P95, P99, calculada a partir dos timestamps de request/response no log da suíte.
- **Tamanho de cada JWT** encontrado nos payloads (client assertions, request objects, tokens) — o dado central para comparar com o tamanho de assinaturas PQC.
- **Número total de requisições** HTTP no fluxo.

Essas métricas compõem a baseline em criptografia clássica; o próximo passo da pesquisa é repetir a coleta com os algoritmos PQC habilitados e comparar.

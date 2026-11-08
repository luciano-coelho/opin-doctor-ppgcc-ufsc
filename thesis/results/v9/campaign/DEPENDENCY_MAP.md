# Mapa de dependências — gateway, proxy, pqc-signer (e o backend que o gateway precisa)

Decisão do Luciano, item 2 (pós-Decisão 82): enumerar toda dependência
de execução dos três componentes próprios da v9 — hostnames, portas,
volumes, variáveis de ambiente, arquivos e imagens — e dizer **onde**
cada uma resolve e **quem a fornece numa AWS real**. Levantado lendo
direto o código (`orchestrator.py`, `business.go`/`business_server.go`,
`opin_flow.py`), nunca suposto. Nenhuma linha abaixo ficou "só local" —
a última (AUTH_URI/API_GATEWAY_URI) foi corrigida pela própria Decisão
83, já refletida aqui.

## Gateway (`mockopin-v9-gateway`)

| Dependência | Tipo | Valor/forma | Quem fornece na AWS real |
|---|---|---|---|
| Imagem docker | imagem | pinada em `PINS.json["images"]["gateway"]` | `deliver_images.py` (1º salto) + `SSHExecutor._deliver_image` (2º salto, Decisão 68) |
| Porta 443 | porta | publicada no host (`-p 443:443`) | `_launch_gateway`, Decisão 70 |
| `/real-certs` | volume (RO) | `mock-service-os/certs` | `deliver_source.py.COMMON_FILES` → servidor (e clientes) |
| `/certs` (embutido na imagem, build-time) | arquivo baked-in | certificado de servidor mTLS por perfil | `COPY certs /certs` no Dockerfile, a partir de `certs/generated` — confirmado byte-a-byte idêntico ao que está em disco hoje (Decisão 75) |
| `HTTP_MODE=business` | env | fixo | `_launch_gateway` |
| `TICKETS_DISABLED=true` | env | fixo | `_launch_gateway` |
| `CRYPTO_PROFILE` | env | por perfil (`classico`/`pqc`/`hibrido-v8`/`hibrido-and`) | `_launch_gateway` |
| `KEYLOG_PATH` | env | só na captura dedicada | `_launch_gateway(keylog=True)` |
| hostname `auth` (`AUTH_URI`, default `http://auth:3000`) | resolução de nome | rede Docker `insurance-server-lambdas_default` + `--network-alias` | **Decisão 83** — container `auth` (backend de negócio) na mesma rede, subido por `start_block` ANTES do gateway |
| hostname `mockapi` (`API_GATEWAY_URI`, default `http://mockapi:8080`) | resolução de nome | idem | **Decisão 83** — container `mockapi`, idem |
| `directory/` (`root-ca.pem`/`issuer-ca.pem`) | servido pelo PRÓPRIO gateway | nenhuma dependência externa | `business.go.directoryHandler`, lê `REAL_CERTS_DIR` |

## Backend de negócio (Decisão 83 — dependência do gateway, não um componente "da v9" em si)

| Serviço | Imagem | Depende de | Health check real |
|---|---|---|---|
| `auth` | `insurance-server-lambdas-auth` (reconstruída) | `localstack` (healthy), `mongodb` (started) | `curl -sf http://127.0.0.1:3000/jwks` |
| `mockapi` | `raidiam-insurance-lambdas` (existente, ver Decisão 83 exceção) | `psql` (healthy) | `docker logs ...mockapi-1 \| grep "Startup completed"` |
| `mongo_seed` | `insurance-server-lambdas-mongo_seed` (reconstruída) | `mongodb` | nenhum (job que roda e sai) |
| `psql`/`localstack`/`mongodb` | imagens estoque, pinadas por digest exato DENTRO do `docker-compose.yml` | — | healthchecks nativos do próprio `docker-compose.yml` |

As 3 CUSTOM (`auth`/`mongo_seed`/`mockapi`) entregues ao SERVIDOR por
`deliver_images.py` (1º salto) + `SSHExecutor._deliver_backend_images`
(2º salto, uma vez por fleet). As 3 ESTOQUE (`psql`/`localstack`/
`mongodb`) NUNCA passam por esse mecanismo (Decisão 87, achado real:
`docker save` de uma imagem referenciada só por digest nunca
preserva nome/digest através de save/load, confirmado ao vivo num
`docker:25-dind` limpo) — `docker compose up` as resolve direto
(pull do registro público, mesmo digest exato já fixado no compose).
`docker-compose.yml` + configs pequenos entregues por
`deliver_source.py.SERVER_ONLY_FILES` (Decisão 83).

## Proxy (`mockopin-v9-proxy` / `tls_kem_proxy`)

| Dependência | Tipo | Valor/forma | Quem fornece na AWS real |
|---|---|---|---|
| Imagem docker | imagem | pinada em `PINS.json["images"]["proxy"]` | `deliver_images.py` + `_deliver_image` → CLIENTE |
| `/certs` | volume (RO) | `thesis/results/v9/certs/generated` | `deliver_source.py.CLIENT_ONLY_FILES` → cliente |
| Endereço do gateway | rede | IP REAL do host (`_server_gateway_ip` — privado se co-localizado/L0, público se não) | `orchestrator.py._server_gateway_ip`, Decisão 27/43/45 — NUNCA um alias Docker (o proxy roda numa instância DIFERENTE do gateway) |

## pqc-signer (`mockopin-pqc-signer`)

| Dependência | Tipo | Valor/forma | Quem fornece na AWS real |
|---|---|---|---|
| Imagem docker | imagem | pinada em `PINS.json["images"]["pqc-signer"]` | `deliver_images.py` + `_deliver_image` → CLIENTE (Decisão 58) |
| Porta/volume externos | — | nenhum | `start_pqc_signer_service` só fala com o proxy localmente, dentro do mesmo cliente |

## Camada de aplicação do cliente (`opin_flow.py`, via `campaign_client_runner.py`)

| Dependência | Tipo | Valor/forma | Quem fornece na AWS real |
|---|---|---|---|
| `thesis/scripts/*.py` | arquivos | `opin_flow.py`/`campaign_client_runner.py`/etc. | `deliver_source.py.COMMON_FILES` → servidor+clientes |
| `thesis/scripts/requirements.txt` | dependências Python | `pip3 install --require-hashes` | `deliver_source.py.install_client_requirements` → clientes (Decisão 71) |
| `mock-service-os/certs` | volume/arquivos | certificados de aplicação do lado do cliente | `deliver_source.py.COMMON_FILES` → servidor+clientes |

## Conclusão

Nenhuma dependência listada acima ainda é "só local" — a última que
era (AUTH_URI/API_GATEWAY_URI, hostname `auth`/`mockapi`) foi corrigida
pela própria Decisão 83, no mesmo pedido que gerou esta tabela.

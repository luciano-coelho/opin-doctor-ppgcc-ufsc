# Dependency map — gateway, proxy, pqc-signer (and the backend the gateway needs)

Luciano's decision, item 2 (post-Decision 82): enumerate every runtime
dependency of the three components that are v9's own — hostnames, ports,
volumes, environment variables, files, and images — and state **where**
each one resolves and **who provides it on a real AWS**. Compiled by reading
the code directly (`orchestrator.py`, `business.go`/`business_server.go`,
`opin_flow.py`), never assumed. No line below remains "local only" —
the last one that was (AUTH_URI/API_GATEWAY_URI) was fixed by Decision
83 itself, already reflected here.

## Gateway (`mockopin-v9-gateway`)

| Dependency | Type | Value/form | Who provides it on real AWS |
|---|---|---|---|
| Docker image | image | pinned in `PINS.json["images"]["gateway"]` | `deliver_images.py` (1st hop) + `SSHExecutor._deliver_image` (2nd hop, Decision 68) |
| Port 443 | port | published on the host (`-p 443:443`) | `_launch_gateway`, Decision 70 |
| `/real-certs` | volume (RO) | `mock-service-os/certs` | `deliver_source.py.COMMON_FILES` → server (and clients) |
| `/certs` (baked into the image at build time) | baked-in file | per-profile mTLS server certificate | `COPY certs /certs` in the Dockerfile, from `certs/generated` — confirmed byte-for-byte identical to what is on disk today (Decision 75) |
| `HTTP_MODE=business` | env | fixed | `_launch_gateway` |
| `TICKETS_DISABLED=true` | env | fixed | `_launch_gateway` |
| `CRYPTO_PROFILE` | env | per profile (`classico`/`pqc`/`hibrido-v8`/`hibrido-and`) | `_launch_gateway` |
| `KEYLOG_PATH` | env | only in the dedicated capture | `_launch_gateway(keylog=True)` |
| hostname `auth` (`AUTH_URI`, default `http://auth:3000`) | name resolution | Docker network `insurance-server-lambdas_default` + `--network-alias` | **Decision 83** — the `auth` container (business backend) on the same network, started by `start_block` BEFORE the gateway |
| hostname `mockapi` (`API_GATEWAY_URI`, default `http://mockapi:8080`) | name resolution | same | **Decision 83** — the `mockapi` container, same |
| `directory/` (`root-ca.pem`/`issuer-ca.pem`) | served by the gateway ITSELF | no external dependency | `business.go.directoryHandler`, reads `REAL_CERTS_DIR` |

## Business backend (Decision 83 — a dependency of the gateway, not a "v9" component in its own right)

| Service | Image | Depends on | Real health check |
|---|---|---|---|
| `auth` | `insurance-server-lambdas-auth` (rebuilt) | `localstack` (healthy), `mongodb` (started) | `curl -sf http://127.0.0.1:3000/jwks` |
| `mockapi` | `raidiam-insurance-lambdas` (existing, see Decision 83 exception) | `psql` (healthy) | `docker logs ...mockapi-1 \| grep "Startup completed"` |
| `mongo_seed` | `insurance-server-lambdas-mongo_seed` (rebuilt) | `mongodb` | none (a job that runs and exits) |
| `psql`/`localstack`/`mongodb` | stock images, pinned by exact digest INSIDE `docker-compose.yml` | — | native health checks from `docker-compose.yml` itself |

The 3 CUSTOM ones (`auth`/`mongo_seed`/`mockapi`) are delivered to the SERVER by
`deliver_images.py` (1st hop) + `SSHExecutor._deliver_backend_images`
(2nd hop, once per fleet). The 3 STOCK ones (`psql`/`localstack`/
`mongodb`) NEVER go through this mechanism (Decision 87, a real finding:
`docker save` of an image referenced only by digest never
preserves name/digest across save/load, confirmed live on a clean
`docker:25-dind`) — `docker compose up` resolves them directly
(pull from the public registry, the same exact digest already pinned in the compose file).
`docker-compose.yml` + small configs are delivered by
`deliver_source.py.SERVER_ONLY_FILES` (Decision 83).

## Proxy (`mockopin-v9-proxy` / `tls_kem_proxy`)

| Dependency | Type | Value/form | Who provides it on real AWS |
|---|---|---|---|
| Docker image | image | pinned in `PINS.json["images"]["proxy"]` | `deliver_images.py` + `_deliver_image` → CLIENT |
| `/certs` | volume (RO) | `thesis/results/v9/certs/generated` | `deliver_source.py.CLIENT_ONLY_FILES` → client |
| Gateway address | network | the host's REAL IP (`_server_gateway_ip` — private if co-located/L0, public otherwise) | `orchestrator.py._server_gateway_ip`, Decision 27/43/45 — NEVER a Docker alias (the proxy runs on a DIFFERENT instance from the gateway) |

## pqc-signer (`mockopin-pqc-signer`)

| Dependency | Type | Value/form | Who provides it on real AWS |
|---|---|---|---|
| Docker image | image | pinned in `PINS.json["images"]["pqc-signer"]` | `deliver_images.py` + `_deliver_image` → CLIENT (Decision 58) |
| External port/volume | — | none | `start_pqc_signer_service` only talks to the proxy locally, within the same client |

## Client application layer (`opin_flow.py`, via `campaign_client_runner.py`)

| Dependency | Type | Value/form | Who provides it on real AWS |
|---|---|---|---|
| `thesis/scripts/*.py` | files | `opin_flow.py`/`campaign_client_runner.py`/etc. | `deliver_source.py.COMMON_FILES` → server+clients |
| `thesis/scripts/requirements.txt` | Python dependencies | `pip3 install --require-hashes` | `deliver_source.py.install_client_requirements` → clients (Decision 71) |
| `mock-service-os/certs` | volume/files | client-side application certificates | `deliver_source.py.COMMON_FILES` → server+clients |

## Conclusion

None of the dependencies listed above remains "local only" — the last one
that was (AUTH_URI/API_GATEWAY_URI, hostname `auth`/`mockapi`) was fixed
by Decision 83 itself, in the same request that produced this table.

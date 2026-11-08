#!/usr/bin/env python3
"""v9, piloto: orquestrador das 60 execucoes (4 perfis x 3 rotas x
N=5), equivalente reduzido ao `campaign_run.py` real da v8 -- mesmas
convencoes (um Executor plugavel, SSH sempre pelo IP PUBLICO do
alvo -- Decisao 43/45 -- marcadores de execucao, bloco por perfil),
mas sem a maquinaria de campanha multi-dia (janelas, latin square,
orcamento de custo/tempo, chronyc) que o piloto, de 2h e 1 so bloco
por rota, nao precisa.

Dois Executors, mesmo padrao SSHExecutor/LocalExecutor da v8 real
(`campaign_run.py`, classes homonimas):

  - SSHExecutor: fala com instancias reais via `cli.run_ssh`/`cli.run_scp`
    -- SEMPRE pelo IP PUBLICO do alvo (Decisao 43/45), nunca testado
    contra AWS de verdade nesta sessao ("nada de AWS").
  - LocalExecutor: NAO sobe o stack Docker real (isso e pesado/lento
    pra um teste automatizado) -- gera dados SINTETICOS mas
    deterministicos e REALISTAS (contagens HTTP 44/28/4/4 reais,
    CurveID esperado por perfil, tamanhos de mensagem iguais aos
    baselines MEDIDOS que o proprio avaliador ja usa -- importados,
    nunca reinventados). Prova a logica de ORQUESTRACAO (cardinalidade,
    ordem, marcadores, formato aceito pelo avaliador) -- NAO prova
    nada sobre a rede/criptografia real, que so a AWS pode confirmar
    (ver thesis/results/v9/DECISIONS.md, Decisao 47).

Ordem de execucao (Decisao 23 item 2, "blocos de perfil, replicando a
v8 real"): pra CADA rota, a ordem dos 4 blocos de perfil e sorteada
(um `random.Random(seed)` por execucao do orquestrador, logado pra
reprodutibilidade/auditoria) -- dentro de um bloco, as N=5 execucoes
daquele perfil rodam em sequencia. A sondagem de prontidao (Decisao
18/36) roda uma vez por troca de bloco, ANTES do primeiro marcador
INICIO -- fora de qualquer janela, por construcao.
"""
import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402

_INTEGRATION_DIR = Path(__file__).resolve().parents[2] / "integration"
sys.path.insert(0, str(_INTEGRATION_DIR))
import evaluate_criteria as ec  # noqa: E402  -- reaproveita os baselines/constantes reais, nunca reinventa

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
ROUTES = ["L0", "L219", "L325"]
N_PER_PROFILE = 5
EXPECTED_TOTAL = len(PROFILES) * len(ROUTES) * N_PER_PROFILE  # 60
EXPECTED_CAPTURES = len(PROFILES) * len(ROUTES)  # 12

_EXPECTED_HTTP = {"http": 44, "jwts": 28, "jwks": 4, "ca": 4}


def profile_block_order(route: str, rng: random.Random, profiles: list[str] | None = None) -> list[str]:
    """Decisao 23 item 2: sorteia a ordem dos blocos de perfil pra
    UMA rota -- chamado uma vez por rota, na ordem fixa ROUTES, pelo
    MESMO `rng` (um unico seed pro orquestrador inteiro, nao um por
    rota) -- reprodutivel dado o mesmo seed, auditavel (o seed e
    sempre gravado no manifesto de saida). `profiles` (Decisao 49):
    so pra validacao manual de um bloco reduzido -- as 60/12 oficiais
    sempre usam o default (os 4 perfis reais)."""
    order = (profiles if profiles is not None else PROFILES)[:]
    rng.shuffle(order)
    return order


def execucao_marker_inicio(profile, route, run):
    return f"== EXECUCAO INICIO perfil={profile} rota={route} run={run} =="


def execucao_marker_fim(profile, route, run):
    return f"== EXECUCAO FIM perfil={profile} rota={route} run={run} =="


def _connection_ok_line(sni="mtls", remote="10.0.0.1:443"):
    return f'gateway: PERFIL connection OK remoteAddr={remote} sni="{sni}"'


def _dedicated_capture_block(profile: str) -> str:
    """Monta o bloco 'tamanho POR MENSAGEM' pra UM perfil, nos
    EXATOS baselines medidos que `evaluate_criteria.py` ja usa
    (CERTIFICATE_BASELINE/CLIENTHELLO_BASELINE/HANDSHAKE_MESSAGE_
    BASELINE, importados, nunca reinventados aqui) -- formato
    identico ao que `measure.sh` produz de verdade (colunas
    tempo\\ttipos\\ttamanhos, tipos TLS numericos: 1=ClientHello,
    2=ServerHello, 8=EncryptedExtensions, 11=Certificate,
    13=CertificateRequest, 15=CertificateVerify, 20=Finished)."""
    hb = ec.HANDSHAKE_MESSAGE_BASELINE[profile]
    cert = ec.CERTIFICATE_BASELINE[profile] - 4
    ch = ec.CLIENTHELLO_BASELINE[profile] - 4
    server_flight = [
        ("2", hb["ServerHello"] - 4), ("8", hb["EncryptedExtensions"] - 4),
        ("13", hb["CertificateRequest"] - 4), ("11", cert),
        ("15", hb["CertificateVerify_servidor"] - 4), ("20", hb["Finished_servidor"] - 4),
    ]
    client_flight = [
        ("11", hb["Certificate_cliente"] - 4),
        ("15", hb["CertificateVerify_cliente"] - 4), ("20", hb["Finished_cliente"] - 4),
    ]
    lines = [
        "tamanho POR MENSAGEM (tempo, tipos, tamanhos)",
        f"0.001\t1\t{ch}",
        "0.010\t" + ",".join(t for t, _ in server_flight) + "\t" + ",".join(str(n) for _, n in server_flight),
        "0.012\t" + ",".join(t for t, _ in client_flight) + "\t" + ",".join(str(n) for _, n in client_flight),
    ]
    return f"== Perfil: {profile} ==\n" + "\n".join(lines) + "\n== fim =="


class LocalExecutor:
    """Simulacao local (sem SSH, sem AWS) -- ver docstring do modulo."""

    def __init__(self):
        self.calls_counter = 0

    def start_block(self, profile, route):
        """Simulacao -- nada pra subir de verdade."""
        return None

    def stop_block(self, profile, route):
        return None

    def readiness_probe(self, profile, route):
        """Decisao 18/36: a sondagem de prontidao completa um
        handshake real (sni=mtls) -- UMA linha, retornada pro
        chamador escrever FORA de qualquer janela."""
        return _connection_ok_line(sni="mtls", remote="203.0.113.9:51000")

    def run_execution(self, profile, route, run):
        """Devolve o necessario pros criterios 4 e 6 de UMA execucao:
        6 linhas 'connection OK' (sni=mtls, client-facing) + 1 linha
        interna (sni=matls-api.local, pra provar que a exclusao do
        avaliador funciona) + a lista insurance/person com as
        contagens HTTP reais esperadas (44/28/4/4) + CurveID/
        DualAuthenticated do perfil."""
        lines = [_connection_ok_line(sni="mtls", remote=f"203.0.113.{10 + i}:5100{i}") for i in range(6)]
        lines.append(_connection_ok_line(sni="matls-api.local", remote="127.0.0.1:9000"))
        # 44 chamadas totais (10 insurance + 34 person), 4 /jwks (1+3),
        # 4 CA (root-ca.pem + issuer-ca.pem, 2+2), 36 chamadas de
        # "conteudo" restantes -- das quais 28 levam 1 JWT e 8 nenhum,
        # pra bater exatamente com os 44/28/4/4 reais (Decisao 17/18).
        insurance = (
            [{"endpoint": "/jwks", "jwts": []}, {"endpoint": "/root-ca.pem", "jwts": []},
             {"endpoint": "/issuer-ca.pem", "jwts": []}]
            + [{"endpoint": "/insurance", "jwts": ["a"]} for _ in range(7)]
        )
        person = (
            [{"endpoint": "/jwks", "jwts": []} for _ in range(3)]
            + [{"endpoint": "/root-ca.pem", "jwts": []}, {"endpoint": "/issuer-ca.pem", "jwts": []}]
            + [{"endpoint": "/person", "jwts": ["a"]} for _ in range(29)]
        )
        all_calls = insurance + person
        jwt_bearing = [c for c in all_calls if c["endpoint"] not in ("/jwks", "/root-ca.pem", "/issuer-ca.pem")]
        for c in jwt_bearing[28:]:
            c["jwts"] = []
        dual = True if profile == "hibrido-and" else False
        return {
            "insurance": insurance, "person": person,
            "gateway_log_lines": lines,
            "curveID": ec.EXPECTED_CURVE[profile], "dualAuthenticated": dual,
        }

    def dedicated_capture(self, profile, route):
        return _dedicated_capture_block(profile)


import re as _re


# Decisao 49 (revisao independente): o avaliador e o CLIENTE
# (opin_flow.py/campaign_client_runner.py) usam CONVENCOES DE NOME
# DIFERENTES pro mesmo perfil -- achado real, confirmado lendo
# opin_flow.py direto (V9_PROFILE_NAME, linha ~263): o gateway e o
# avaliador usam os nomes de EXIBICAO da v9 ("classico"/"hibrido-v8"),
# mas CRYPTO_PROFILE do lado do CLIENTE (opin_flow.py,
# _CRYPTO_PROFILE_FOR_ROUTING) so reconhece os nomes INTERNOS antigos
# da v8 ("classic"/"hybrid") -- "pqc" e "hibrido-and" sao os MESMOS
# nos dois lados. Usar o nome de exibicao do lado do cliente
# (ex. "hibrido-v8") faria `_USE_TLS_KEM_PROXY` dar falso (nao esta
# na lista "classic","pqc","hybrid","hibrido-and") e o fluxo inteiro
# rodaria sem proxy, contra o alvo errado -- bug real, nunca
# exercitado antes desta rodada.
CLIENT_CRYPTO_PROFILE_ENV = {"classico": "classic", "pqc": "pqc", "hibrido-v8": "hybrid", "hibrido-and": "hibrido-and"}
# Decisao 50 (revisao independente): achado real, distinto do mapa do
# CLIENTE acima -- o BACKEND local (`auth`/`mongo_seed`/`mockapi`,
# `mock-service-os/mock_as`) so conhece 3 perfis de JWT/assinatura
# ("classic"/"pqc"/"hybrid", `crypto-profiles/*.json` -- confirmado,
# nao existe `hibrido-and.json`). Hibrido-AND nunca introduziu um
# esquema de assinatura/JWT proprio -- AND e so o mecanismo de
# AUTENTICACAO TLS (par de certificados no handshake); pro lado da
# aplicacao (JWKS, algoritmo de assinatura, client_one), hibrido-and
# reusa INTEGRALMENTE a config "hybrid" (confirmado tambem no carve-
# out interno do gateway, Decisao 44: `op_hybrid.crt`, nunca um
# "op_hibrido_and.crt" separado). Setar CRYPTO_PROFILE=hibrido-and
# pro BACKEND faria `configuration.js` tentar ler
# `crypto-profiles/hibrido-and.json` (inexistente) e travar -- achado
# ao vivo, nao suposto.
BACKEND_CRYPTO_PROFILE_ENV = {"classico": "classic", "pqc": "pqc", "hibrido-v8": "hybrid", "hibrido-and": "hybrid"}
_INTERNAL_CALLER_SNI = "matls-api.local"  # mesma convencao de evaluate_criteria.py

_CONNECTION_OK_LOG_RE = _re.compile(
    r'gateway: \S+ connection OK remoteAddr=(?P<addr>\S+) sni="(?P<sni>[^"]*)"'
    r'(?: curve=(?P<curve>\S+) dualAuthenticated=(?P<dual>\S+))?'
)


class SSHExecutor:
    """Fala com instancias reais -- SEMPRE pelo IP PUBLICO do alvo
    (Decisao 43/45), nunca o privado, so pra SSH. `inventory` e o
    dict que `terraform output -json inventory` produz (ver
    thesis/results/v9/terraform/outputs.tf).

    Decisao 49 (revisao independente, item 1): o comando remoto REAL
    -- reaproveitado, nao reinventado, do `campaign_run.py` real da
    v8 (`SSHExecutor.run_one_execution`/`start_block_proxies`/
    `stop_block_proxies`, 720 execucoes reais, zero erros) -- usa o
    script generico e ja compartilhado `campaign_client_runner.py`
    (`thesis/scripts/`, nao e v8-especifico: so chama
    `latency_automation.run_once_timed_with_retry()`, que por sua vez
    chama `opin_flow.run_insurance_flow`/`run_person_flow` -- a MESMA
    logica de fluxo que `LocalExecutor` da v8 real e o proprio
    `opin_flow.py` sempre usaram). O que a v9 mudou, e SO isso: (a)
    `V9_HARNESS=1` no ambiente (pra usar o proxy/gateway da v9, nao o
    `tls_kem_proxy`/`mtls` reais); (b) a traducao de nome de perfil
    acima (`CLIENT_CRYPTO_PROFILE_ENV`); (c) certificados duplos
    (Hibrido-AND) e grupos de troca de chave sao decididos inteiramente
    DENTRO de `opin_flow.py`/`tls_kem_proxy`/no gateway a partir do
    MESMO `CRYPTO_PROFILE`, nenhuma linha nova aqui precisa saber
    disso."""

    TLS_KEM_PROXY_CONTAINER = "tls_kem_proxy_run"
    PQC_SIGNER_CONTAINER = "pqc_signer_service_run"

    def __init__(self, inventory, key_path=None, gateway_container="v9-mtls", local_shim_bridge_join=False):
        self.inventory = inventory
        self.key_path = key_path
        self.gateway_container = gateway_container
        self._block_start_utc = {}
        # Decisao 49: SO pra validacao local via shim -- quando
        # REMOTE_GATEWAY_HOST esta setado, opin_flow.start_tls_kem_proxy
        # NUNCA junta `--network insurance-server-lambdas_default`
        # (linha 1094/1152 do arquivo real -- correto pro caso remoto
        # de verdade, onde o alvo e um IP roteavel de verdade, sem
        # precisar de rede Docker nenhuma). Nesta maquina, o alias
        # "mtls" so existe NESSA rede -- entao, so pra esta validacao,
        # conecta tambem o gateway na rede "bridge" (a mesma que o
        # proxy acaba usando) e descobre o IP real dele ali, em vez de
        # depender do nome. Numa instancia EC2 real, `gw_ip` ja e um
        # IP de verdade (Decisao 27/43/45) -- este bloco nunca executa.
        self.local_shim_bridge_join = local_shim_bridge_join

    def _server_ip(self):
        return self.inventory["server"]["public_ip"]

    def _client_ip(self, route):
        return self.inventory["clients"][route]["public_ip"]

    def _server_gateway_ip(self, route):
        """Decisao 27 item 1/outputs.tf `colocated`: so o trafego de
        GATEWAY (443, dentro da execucao real do cliente) usa o IP
        PRIVADO do servidor pro cliente co-localizado -- SSH (acima)
        nunca usa isso. Decisao 49/Emenda 13: o inventario e os
        clientes SEMPRE discam o EIP (ver `_client_ip`/SSH acima) --
        este metodo so decide o alvo de GATEWAY/443 que o PROXIO
        DENTRO do cliente disca, nunca o alvo de SSH."""
        client = self.inventory["clients"][route]
        return self.inventory["server"]["private_ip"] if client.get("colocated") else self.inventory["server"]["public_ip"]

    def _env_prefix(self, env: dict) -> str:
        return " ".join(f"{k}={v}" for k, v in env.items())

    def _client_env(self, profile, server_gw_ip):
        return {
            "V9_HARNESS": "1",
            "CRYPTO_PROFILE": CLIENT_CRYPTO_PROFILE_ENV[profile],
            "REMOTE_GATEWAY_HOST": server_gw_ip,
        }

    def _gateway_logs(self, since_iso, until_iso):
        """`docker logs -t --since ... --until ...` no CONTAINER DO
        GATEWAY -- mesma chamada que `stop_block_proxies`/
        `run_one_execution` da v8 real fazem (so troca o nome fixo do
        container, `self.of.GATEWAY_CONTAINER`/
        `insurance-server-lambdas-mtls-1`, pelo equivalente da v9)."""
        proc = cli.run_ssh(self._server_ip(),
                            f"docker logs -t --since {since_iso} --until {until_iso} {self.gateway_container}",
                            key_path=self.key_path)
        return (proc.stdout or "") + (proc.stderr or "")

    def _connection_ok_lines(self, log_text):
        """Extrai as linhas 'connection OK' de verdade do log do
        gateway -- devolve as linhas CRUAS (pro log combinado) e os
        campos decodificados (sni/curve/dualAuthenticated), nunca
        inventados."""
        raw_lines, parsed = [], []
        for line in log_text.splitlines():
            m = _CONNECTION_OK_LOG_RE.search(line)
            if m:
                raw_lines.append(line.strip())
                parsed.append(m.groupdict())
        return raw_lines, parsed

    def start_block(self, profile, route):
        """Decisao 49: reusa o padrao real de `start_block_proxies`
        (v8) -- troca o perfil do GATEWAY e sobe proxy+signer
        DETACHED antes de qualquer execucao cronometrada do bloco.

        **Limitacao honesta, registrada aqui (nao escondida):** a
        troca de perfil do GATEWAY em si, pro `docker run
        {self.gateway_container}` usado nesta validacao LOCAL, e um
        atalho SO pra esta validacao (o container `v9-mtls` que esta
        sessao sobe manualmente, substituindo o `mtls` real no
        `insurance-server-lambdas_default`) -- a v8 real troca o
        perfil do servidor via `switch_crypto_profile.py`
        (`docker compose up -d --force-recreate auth mtls mongo_seed
        mockapi`), que NAO conhece a v9 (nunca importa nem referencia
        o gateway/proxy da v9). Pra um piloto remoto de verdade, esse
        script precisa de uma versao v9-consciente (ou um override de
        compose que troque so o servico `mtls` pela imagem da v9) --
        isso NAO existe ainda, gap separado do pedido desta rodada
        (que era so a invocacao do CLIENTE)."""
        self._block_start_utc[(profile, route)] = datetime.now(timezone.utc)
        if self.local_shim_bridge_join:
            # Achado real desta rodada (Decisao 49): trocar SO o
            # gateway nao basta -- `auth` roda com seu PROPRIO
            # CRYPTO_PROFILE (visto ao vivo: "Crypto profile: classic
            # (signingAlgs: PS256)" no log dela), que determina o
            # algoritmo de assinatura/JWKS que ela espera do token do
            # cliente. Sem trocar `auth`/`mongo_seed`/`mockapi`
            # tambem, um bloco hibrido-v8 contra uma `auth` ainda em
            # "classic" devolve 401 em /token -- confirmado ao vivo,
            # nao suposto (ver Decisao 49). Mesmo comando (literal,
            # exceto por excluir "mtls", que a v9 substitui pelo seu
            # proprio container acima) que `switch_crypto_profile.py`
            # real usa.
            backend_profile = BACKEND_CRYPTO_PROFILE_ENV[profile]
            cli.run_ssh(self._server_ip(),
                        f'cd "$(pwd)/../../insurance-server-lambdas" && '
                        f"CRYPTO_PROFILE={backend_profile} docker compose --profile main "
                        f"up -d --force-recreate auth mongo_seed mockapi && "
                        # Decisao 49: switch_crypto_profile.py real espera health
                        # de verdade (chronyc/psql/retry) -- aqui, so um poll
                        # simples nos dois servicos que o settling de fato
                        # chama, ate os dois responderem. `mockapi`
                        # (Java/Micronaut, Hibernate) demora de verdade pra
                        # subir (~30s, confirmado ao vivo nos logs) -- achado
                        # ao vivo: 502 Bad Gateway em /jwks (via api.local,
                        # roteado pro mockapi) sem esperar especificamente por
                        # ele, so por auth (rapido, ~3s) nao bastava.
                        f"for i in $(seq 1 30); do curl -sf http://127.0.0.1:3000/jwks >/dev/null 2>&1 && break; sleep 1; done && "
                        # `mockapi` (Java/Micronaut, Hibernate metamodel scan)
                        # demora ~30s pra subir de verdade -- confirmado ao
                        # vivo nos logs dele -- e devolve conexao recusada OU
                        # respostas inconsistentes nesse meio tempo (nao um
                        # unico codigo de erro confiavel pra sondar com
                        # curl). Espera fixa, generosa, em vez de um poll
                        # fragil: mais simples e mais robusto pra esta
                        # validacao local.
                        f"for i in $(seq 1 45); do "
                        f"docker logs insurance-server-lambdas-mockapi-1 2>&1 | grep -q 'Startup completed' && break; "
                        f"sleep 1; done",
                        key_path=self.key_path, connect_timeout=90)
        cli.run_ssh(self._server_ip(), f"docker rm -f {self.gateway_container} 2>/dev/null; true", key_path=self.key_path)
        cli.run_ssh(self._server_ip(),
                    f"docker run -d --name {self.gateway_container} "
                    f"--network insurance-server-lambdas_default "
                    f"--network-alias mtls --network-alias matls-auth.local --network-alias auth.local "
                    f"--network-alias matls-api.local --network-alias api.local --network-alias directory "
                    f"-e HTTP_MODE=business -e TICKETS_DISABLED=true -e CRYPTO_PROFILE={profile} "
                    # Decisao 52 (item 4): KEYLOG_PATH sempre ligado, em
                    # TODO bloco (nao so quando dedicated_capture vai
                    # rodar) -- aditivo, nao muda nenhum comportamento
                    # do gateway em si (so grava um arquivo extra que
                    # mais ninguem le se dedicated_capture nao for
                    # chamado). E o MESMO arquivo que dedicated_capture
                    # vai ler depois, via `docker exec`, pra decifrar o
                    # pcap com tshark -- sem precisar de volume
                    # compartilhado nenhum (o arquivo nunca sai do
                    # filesystem do proprio container do gateway antes
                    # de ser copiado por `docker cp`/`docker exec cat`).
                    f"-e KEYLOG_PATH=/tmp/v9_keylog.txt "
                    f"-v $(pwd)/../../mock-service-os/certs:/real-certs:ro mockopin-v9-gateway",
                    key_path=self.key_path)
        # Espera o gateway de verdade terminar de subir (carregar os
        # certs, abrir :443) antes do proxy tentar discar -- achado ao
        # vivo (Decisao 49): sem isso, a primeira chamada do proxy
        # pode cair numa janela em que o container ja existe mas ainda
        # nao esta aceitando conexao, devolvendo 502 rio abaixo.
        cli.run_ssh(self._server_ip(),
                    f"for i in $(seq 1 30); do docker logs {self.gateway_container} 2>&1 | grep -q 'listening on' && break; sleep 1; done",
                    key_path=self.key_path)
        if self.local_shim_bridge_join:
            cli.run_ssh(self._server_ip(), f"docker network connect bridge {self.gateway_container}", key_path=self.key_path)
            ip_proc = cli.run_ssh(
                self._server_ip(),
                f"docker inspect {self.gateway_container} --format '{{{{.NetworkSettings.Networks.bridge.IPAddress}}}}'",
                key_path=self.key_path,
            )
            bridge_ip = ip_proc.stdout.strip()
            if not bridge_ip:
                raise RuntimeError(f"start_block {profile}/{route}: nao consegui descobrir o IP de {self.gateway_container} na rede bridge")
            self.inventory["server"]["private_ip"] = bridge_ip
            self.inventory["server"]["public_ip"] = bridge_ip
        gw_ip = self._server_gateway_ip(route)
        env = self._client_env(profile, gw_ip)
        py_code = ("import opin_flow as of; of.start_tls_kem_proxy(%s, detached=True); "
                   "of.start_pqc_signer_service(%s)") % (json.dumps(env["CRYPTO_PROFILE"]), json.dumps(env["CRYPTO_PROFILE"]))
        remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(env)} python3 -c {json.dumps(py_code)}"
        proc = cli.run_ssh(self._client_ip(route), remote_cmd, key_path=self.key_path)
        if proc.returncode != 0:
            raise RuntimeError(f"start_block {profile}/{route}: falhou subindo proxy/signer: {proc.stderr}")

    def stop_block(self, profile, route):
        """Mesmo comando (literal) que `stop_block_proxies` da v8
        real usa -- `docker stop`+`docker rm -f`, os dois containers
        fixos (`tls_kem_proxy_run`/`pqc_signer_service_run`)."""
        remote_cmd = (f"docker stop {self.TLS_KEM_PROXY_CONTAINER} {self.PQC_SIGNER_CONTAINER} 2>/dev/null; "
                      f"docker rm -f {self.TLS_KEM_PROXY_CONTAINER} {self.PQC_SIGNER_CONTAINER} 2>/dev/null; true")
        cli.run_ssh(self._client_ip(route), remote_cmd, key_path=self.key_path)
        self._block_start_utc.pop((profile, route), None)

    def readiness_probe(self, profile, route):
        """Decisao 18/36: UMA execucao de 'settling', mesmo padrao
        real da v8 (`SETTLING_RUNS` loop em `start_block_proxies`) --
        roda de verdade, mas NUNCA entra em `execucoes_calls`/
        `criterio6_rows` (chamada FORA de qualquer marcador INICIO/
        FIM). Devolve a linha 'connection OK' real do gateway pra essa
        chamada (sni=mtls, client-facing) -- se nenhuma aparecer no
        log (gateway lento pra logar, ou handshake falhou), levanta
        alto em vez de inventar uma linha."""
        t0 = datetime.now(timezone.utc)
        gw_ip = self._server_gateway_ip(route)
        env = self._client_env(profile, gw_ip)
        remote_argv = f"campaign_client_runner.py --label settling_{profile}_{route}"
        remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(env)} python3 {remote_argv}"
        proc = cli.run_ssh(self._client_ip(route), remote_cmd, key_path=self.key_path)
        if proc.returncode != 0:
            raise RuntimeError(f"readiness_probe {profile}/{route}: execucao de settling falhou: {proc.stderr}")
        t1 = datetime.now(timezone.utc)
        log_text = self._gateway_logs(t0.isoformat(), t1.isoformat())
        raw_lines, parsed = self._connection_ok_lines(log_text)
        client_facing = [ln for ln, p in zip(raw_lines, parsed) if p["sni"] != _INTERNAL_CALLER_SNI]
        if not client_facing:
            raise RuntimeError(
                f"readiness_probe {profile}/{route}: nenhuma linha 'connection OK' client-facing encontrada "
                f"no log do gateway entre {t0.isoformat()} e {t1.isoformat()} -- settling nao confirmado"
            )
        return client_facing[0]

    def run_execution(self, profile, route, run):
        """Decisao 49: a invocacao real -- `campaign_client_runner.py`
        (reaproveitado, nao reescrito), com os 3 ajustes da v9
        (V9_HARNESS, traducao de nome de perfil, REMOTE_GATEWAY_HOST
        por rota). O resultado real tem UMA lista `calls` ja
        fundida (insurance+person, `latency_automation.run_once_timed`
        sempre funde as duas antes de devolver) -- guardada sob
        `"insurance"` com `"person": []` (o avaliador soma as duas de
        qualquer forma, `_http_counts_for_calls`, nunca separa de
        volta; ver Decisao 49)."""
        t0 = datetime.now(timezone.utc)
        gw_ip = self._server_gateway_ip(route)
        env = self._client_env(profile, gw_ip)
        label = f"{profile}_{route}_{run}"
        remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(env)} python3 campaign_client_runner.py --label {label}"
        proc = cli.run_ssh(self._client_ip(route), remote_cmd, key_path=self.key_path)
        if proc.returncode != 0:
            raise RuntimeError(f"execucao {label}: falhou (rc={proc.returncode}): {proc.stderr}")
        try:
            result = json.loads(proc.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError) as e:
            raise RuntimeError(f"execucao {label}: saida remota nao-JSON: {e}\nstdout={proc.stdout!r}") from None
        t1 = datetime.now(timezone.utc)

        log_text = self._gateway_logs(t0.isoformat(), t1.isoformat())
        raw_lines, parsed = self._connection_ok_lines(log_text)
        client_facing = [p for p in parsed if p["sni"] != _INTERNAL_CALLER_SNI]
        curve_id = client_facing[0]["curve"] if client_facing and client_facing[0]["curve"] else ec.EXPECTED_CURVE.get(profile)
        dual_auth = (client_facing[0]["dual"] == "true") if client_facing and client_facing[0]["dual"] else (profile == "hibrido-and")

        return {
            "insurance": result.get("calls", []), "person": [],
            "gateway_log_lines": raw_lines,
            "curveID": curve_id, "dualAuthenticated": dual_auth,
        }

    def _primary_iface(self, host):
        """Decisao 52 (pedido independente, item 4): a interface
        PRIMARIA do host, via a propria rota default dele -- nunca
        hardcoded (varia entre familias de instancia EC2: `ens5` com
        driver ENA nas familias atuais, `eth0` em AMIs/familias mais
        antigas) e, por construcao, nunca loopback (a rota default
        nunca aponta pra `lo`)."""
        proc = cli.run_ssh(host, "ip -o -4 route show to default | awk '{print $5}' | head -1", key_path=self.key_path)
        iface = proc.stdout.strip()
        if not iface:
            raise RuntimeError(f"_primary_iface({host}): nao consegui descobrir a interface primaria (saida vazia, stderr={proc.stderr!r})")
        return iface

    def dedicated_capture(self, profile, route):
        """Decisao 52 (pedido independente, item 4) -- substitui o
        placeholder da Decisao 49 (que so lia um arquivo que nunca era
        escrito).

        **Ponto de captura, definido e justificado:** a interface
        PRIMARIA do SERVIDOR (`_primary_iface`), porta 443 -- NUNCA a
        loopback. Isso vale inclusive no cenario L0 co-localizado:
        `_server_gateway_ip` (Decisao 49/Emenda 13) faz o cliente
        discar sempre o IP PRIVADO real do servidor, nunca 127.0.0.1
        -- logo TODO trafego mTLS cliente-facing, nos 3 roteiros,
        cruza essa interface de verdade, nunca so a loopback da
        propria maquina.

        **Decifragem:** `KEYLOG_PATH=/tmp/v9_keylog.txt`, ligado em
        TODO bloco desde `start_block` (aditivo, Decisao 52) -- lido
        do PROPRIO filesystem do container do gateway via `docker exec
        cat` depois da captura, sem precisar de volume compartilhado
        nenhum.

        **Extracao:** tshark via a imagem `mockopin-v9-measure` ja
        construida pro T6 (tem tcpdump+tshark instalados, Decisao
        14) -- aqui so LEITURA de arquivo (`-r pcap`), nenhuma captura
        de rede nova dentro do container; mesmos campos/formato que
        `measure.sh` ja usa (`tls.handshake.type`/`.length`), pro
        avaliador (`_message_sizes_for_profile`) ler sem mudanca.

        **Conexao capturada:** UMA execucao de 'settling' dedicada
        (mesmo padrao e mesma garantia de `readiness_probe` -- roda
        FORA de qualquer marcador INICIO/FIM, nunca entra nas
        contagens dos criterios 4/6), disparada do CLIENTE enquanto o
        tcpdump do servidor esta rodando."""
        server_ip = self._server_ip()
        pcap_path = f"/tmp/criterio1_{profile}_{route}.pcap"
        keylog_path = f"/tmp/criterio1_keylog_{profile}_{route}.txt"
        tcpdump_log = f"/tmp/criterio1_tcpdump_{profile}_{route}.log"

        iface = self._primary_iface(server_ip)

        start_proc = cli.run_ssh(
            server_ip,
            f"sudo sh -c 'nohup tcpdump -i {iface} -s 0 -w {pcap_path} \"tcp port 443\" "
            f"> {tcpdump_log} 2>&1 & echo $!'",
            key_path=self.key_path,
        )
        tcpdump_pid = start_proc.stdout.strip().splitlines()[-1] if start_proc.stdout.strip() else ""
        if not tcpdump_pid.isdigit():
            raise RuntimeError(
                f"dedicated_capture {profile}/{route}: tcpdump nao iniciou "
                f"(stdout={start_proc.stdout!r} stderr={start_proc.stderr!r})"
            )

        try:
            gw_ip = self._server_gateway_ip(route)
            env = self._client_env(profile, gw_ip)
            remote_argv = f"campaign_client_runner.py --label criterio1_capture_{profile}_{route}"
            remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(env)} python3 {remote_argv}"
            trigger = cli.run_ssh(self._client_ip(route), remote_cmd, key_path=self.key_path)
            if trigger.returncode != 0:
                raise RuntimeError(f"dedicated_capture {profile}/{route}: conexao de disparo falhou: {trigger.stderr}")
        finally:
            # sleep antes do kill: da tempo da conexao de disparo
            # terminar de verdade antes de cortar a captura no meio.
            cli.run_ssh(server_ip, f"sleep 1; sudo kill {tcpdump_pid} 2>/dev/null; sleep 1; true", key_path=self.key_path)

        cli.run_ssh(server_ip, f"docker exec {self.gateway_container} cat /tmp/v9_keylog.txt > {keylog_path}", key_path=self.key_path)

        tshark_proc = cli.run_ssh(
            server_ip,
            f"docker run --rm -v {pcap_path}:{pcap_path}:ro -v {keylog_path}:{keylog_path}:ro "
            f"--entrypoint tshark mockopin-v9-measure "
            f'-r {pcap_path} -o "tls.keylog_file: {keylog_path}" -Y tls.handshake '
            f"-T fields -e frame.number -e tls.handshake.type -e tls.handshake.length -E aggregator=,",
            key_path=self.key_path,
        )
        lines = ["tamanho POR MENSAGEM (frame, tipos, tamanhos)"]
        for raw_line in tshark_proc.stdout.strip().splitlines():
            cols = raw_line.split("\t")
            if len(cols) < 3 or not cols[1] or not cols[2]:
                continue
            lines.append(f"{cols[0]}\t{cols[1]}\t{cols[2]}")
        if len(lines) == 1:
            raise RuntimeError(
                f"dedicated_capture {profile}/{route}: tshark nao extraiu nenhuma mensagem de handshake "
                f"(pcap vazio ou keylog nao decifrou) -- stdout={tshark_proc.stdout!r} stderr={tshark_proc.stderr!r}"
            )
        return f"== Perfil: {profile} ==\n" + "\n".join(lines) + "\n== fim =="


def run_pilot(executor, seed: int, out_dir: Path, n_per_profile: int = N_PER_PROFILE, smoke: bool = False,
              routes: list[str] | None = None, profiles: list[str] | None = None,
              skip_dedicated_captures: bool = False) -> dict:
    """Roda `n_per_profile` execucoes por bloco (perfis x rotas,
    default os 4x3 reais) + as 12 capturas dedicadas, escreve todos
    os artefatos no formato que `evaluate_criteria.py --aws-dir`
    espera. Devolve um resumo (cardinalidade, ordem por rota, seed).

    `smoke=True` (Decisao 48/Emenda 12 ao pre-registro v9-prereg):
    `n_per_profile` continua livre pro CHAMADOR escolher (a porta de
    fumaca usa 1), mas o manifesto fica marcado explicitamente como
    `"smoke": true` e `out_dir` tem que ser um diretorio PROPRIO,
    nunca reaproveitado pelas 60 execucoes reais -- a porta de fumaca
    NUNCA conta pro total oficial do piloto, mesmo que gere artefatos
    no MESMO formato (pra poder ser avaliada pelos mesmos criterios).

    `routes`/`profiles` (Decisao 49): reduzem a grade pra validacao
    manual de UM bloco especifico (ex.: 1 perfil x 1 rota x N
    execucoes) -- nunca usado pelas 60/12 oficiais, que sempre passam
    o default (todas as rotas/perfis).

    `skip_dedicated_captures`: as 12 capturas do criterio 1 sao uma
    responsabilidade SEPARADA (Decisao 41, produtores dedicados) --
    a porta de fumaca (Decisao 48) e a validacao manual de bloco
    (Decisao 49) pulam essa parte de proposito, pra nao confundir
    "12 execucoes de fumaca" com "12 capturas do criterio 1", dois
    "12" sem nenhuma relacao entre si."""
    routes = routes if routes is not None else ROUTES
    profiles = profiles if profiles is not None else PROFILES
    out_dir.mkdir(parents=True, exist_ok=True)
    capturas_dir = out_dir / "criterio1_capturas"
    capturas_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    combined_log_lines = []
    execucoes_calls = []
    criterio6_rows = []
    route_orders = {}

    for route in routes:
        order = profile_block_order(route, rng, profiles=profiles)
        route_orders[route] = order
        for profile in order:
            combined_log_lines.append(f"== Perfil: {profile} ==")
            executor.start_block(profile, route)
            combined_log_lines.append(executor.readiness_probe(profile, route))
            for run in range(1, n_per_profile + 1):
                combined_log_lines.append(execucao_marker_inicio(profile, route, run))
                result = executor.run_execution(profile, route, run)
                combined_log_lines.extend(result["gateway_log_lines"])
                combined_log_lines.append(execucao_marker_fim(profile, route, run))
                execucoes_calls.append({
                    "profile": profile, "route": route, "run": run,
                    "insurance": result["insurance"], "person": result["person"],
                })
                criterio6_rows.append({
                    "profile": profile, "route": route, "run": run,
                    "curveID": result["curveID"], "dualAuthenticated": result["dualAuthenticated"],
                    "keylog_evidence": True,
                })
            executor.stop_block(profile, route)

    if not skip_dedicated_captures:
        for profile in PROFILES:
            for route in ROUTES:
                block = executor.dedicated_capture(profile, route)
                (capturas_dir / f"{profile}_{route}.log").write_text(block, encoding="utf-8")

    combined_log_path = out_dir / "piloto_combined.log"
    combined_log_path.write_text("\n".join(combined_log_lines) + "\n", encoding="utf-8")

    calls_path = out_dir / "piloto_calls.json"
    calls_path.write_text(json.dumps(execucoes_calls, indent=2, ensure_ascii=False), encoding="utf-8")

    criterio6_path = out_dir / "criterio6_execucoes.json"
    criterio6_path.write_text(json.dumps(criterio6_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    expected_total = len(profiles) * len(routes) * n_per_profile
    manifest = {
        "seed": seed, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "smoke": smoke, "n_per_profile": n_per_profile,
        "route_orders": route_orders,
        "total_execucoes": len(execucoes_calls), "expected_total": expected_total,
        "total_capturas": EXPECTED_CAPTURES,
        "combined_log": str(combined_log_path), "calls_json": str(calls_path),
        "criterio6_json": str(criterio6_path), "capturas_dir": str(capturas_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


SMOKE_N_PER_PROFILE = 1
SMOKE_EXPECTED_TOTAL = len(PROFILES) * len(ROUTES) * SMOKE_N_PER_PROFILE  # 12


def run_smoke_gate(executor, seed: int, out_dir: Path) -> dict:
    """Decisao 48 (Emenda 12 ao pre-registro v9-prereg): 1 execucao
    por perfil x rota (12 no total, NUNCA contadas nas 60 oficiais) --
    roda ANTES do bloco cronometrado, so com `SSHExecutor` real,
    contra as instancias de verdade recem-subidas. Critério de
    abortar: QUALQUER uma das 12 execucoes falhando (excecao,
    `insurance`/`person` vazios, ou qualquer criterio avaliavel por
    execucao-unica dando FAIL) e motivo pra abortar o piloto inteiro
    e destruir -- nunca prosseguir pras 60 execucoes reais sobre uma
    infraestrutura que a propria porta de fumaca ja mostrou com
    problema."""
    manifest = run_pilot(executor, seed, out_dir, n_per_profile=SMOKE_N_PER_PROFILE, smoke=True)
    execucoes = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))
    failures = []
    for entry in execucoes:
        counts = ec._http_counts_for_calls(entry)
        if counts != _EXPECTED_HTTP:
            failures.append({"profile": entry["profile"], "route": entry["route"],
                              "esperado": _EXPECTED_HTTP, "obtido": counts})
    manifest["smoke_ok"] = manifest["total_execucoes"] == SMOKE_EXPECTED_TOTAL and not failures
    manifest["smoke_failures"] = failures
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["simulate", "ssh"], default="simulate")
    ap.add_argument("--seed", type=int, default=20261107)
    ap.add_argument("--out", required=True)
    ap.add_argument("--inventory-json", help="obrigatorio no modo --mode ssh (terraform output -json inventory)")
    ap.add_argument("--ssh-key", help="caminho da chave privada do piloto (modo ssh)")
    ap.add_argument("--smoke", action="store_true",
                     help="Decisao 48: porta de fumaca, 1 execucao por perfil x rota (12, nunca contadas nas 60)")
    args = ap.parse_args()

    if args.mode == "simulate":
        executor = LocalExecutor()
    else:
        if not args.inventory_json:
            ap.error("--mode ssh exige --inventory-json")
        inventory = json.load(open(args.inventory_json, encoding="utf-8"))
        executor = SSHExecutor(inventory, key_path=args.ssh_key)

    if args.smoke:
        manifest = run_smoke_gate(executor, args.seed, Path(args.out))
    else:
        manifest = run_pilot(executor, args.seed, Path(args.out))
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if args.smoke and not manifest["smoke_ok"]:
        # Decisao 49 (Emenda 12, revisada): este script NUNCA destroi
        # nada por conta propria -- so reporta e sai com erro. A
        # decisao de corrigir e repetir (dentro das 4h do
        # autodesligamento) ou mandar destruir e SEMPRE do Luciano,
        # nunca automatica (ver DECISIONS.md).
        print("\n*** PORTA DE FUMACA REPROVADA -- PAUSADO. ***", file=sys.stderr)
        print("Nao executado: nenhum destroy automatico. Decisao do Luciano:", file=sys.stderr)
        print("  (a) corrigir e repetir --smoke dentro da janela de 4h, ou", file=sys.stderr)
        print("  (b) mandar destruir (cleanup.py).", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

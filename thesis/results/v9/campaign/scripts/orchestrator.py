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
# Decisao 65 (achado real, ao vivo, no Passo 8 do ensaio real): o
# controle roda Python 3.9 (Amazon Linux 2023 base) -- `list[str] |
# None` (PEP 604, uniao com `|`) so existe a partir do 3.10 e quebra
# na DEFINICAO da funcao, antes de qualquer `--help`. `from __future__
# import annotations` adia a avaliacao de toda anotacao pra string
# (nunca inspecionada em runtime por este modulo -- nenhum `get_type_
# hints`/dataclass aqui) -- zero mudanca de comportamento, so
# compatibilidade com o Python real do controle.
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import preflight  # noqa: E402  -- Decisao 53, item 4: pre-requisitos de captura por host

_INTEGRATION_DIR = Path(__file__).resolve().parents[2] / "integration"
sys.path.insert(0, str(_INTEGRATION_DIR))
import evaluate_criteria as ec  # noqa: E402  -- reaproveita os baselines/constantes reais, nunca reinventa

# Decisao 55, item 1: PINS.json e o UNICO lugar onde o hash/Image ID
# esperado de cada imagem fica registrado -- NUNCA escrito por
# nenhum codigo deste modulo (so lido). Alterar o arquivo exige
# Emenda numerada explicita em DECISIONS.md (ver o proprio campo
# "_policy" dentro dele) -- nunca uma gravacao automatica.
PINS_PATH = Path(__file__).resolve().parents[1] / "PINS.json"
_PINS_CACHE = None


def load_pins(pins_path=PINS_PATH):
    """Le PINS.json -- cacheado no MODULO (nao por instancia de
    Executor), ja que o arquivo e compartilhado por qualquer
    orquestrador que rode no mesmo processo (piloto ou a futura
    campanha oficial, Decisao 55 item 1: "a oficial com os pins do
    piloto passa")."""
    global _PINS_CACHE
    if _PINS_CACHE is not None:
        return _PINS_CACHE
    if not Path(pins_path).is_file():
        raise RuntimeError(f"load_pins: {pins_path} nao encontrado -- PINS.json e obrigatorio, nunca opcional")
    _PINS_CACHE = json.loads(Path(pins_path).read_text(encoding="utf-8"))
    return _PINS_CACHE

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
ROUTES = ["L0", "L219", "L325"]
N_PER_PROFILE = 5
# Decisao 60, item 4: limiar de RELATORIO (nunca aborta por conta
# propria) pro 2o salto de `_deliver_image` -- 10 minutos, pedido
# explicito pro ensaio de infraestrutura.
DELIVERY_SLOW_THRESHOLD_SECONDS = 600
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

    def capture_ready_check(self):
        """Decisao 53, item 4c: LocalExecutor nunca tem infraestrutura
        real pra checar (sem SSH, sem instancia) -- sempre `go=True`,
        sem nenhum host. So o SSHExecutor de fato roda os 5 probes."""
        return {"go": True, "checks": []}


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

    def __init__(self, inventory, key_path=None, gateway_container="v9-mtls", local_shim_bridge_join=False,
                 images_staging_dir=None):
        self.inventory = inventory
        self.key_path = key_path
        self.gateway_container = gateway_container
        self._block_start_utc = {}
        # Decisao 59 (achado real: o controle NUNCA roda docker --
        # confirmado em PILOT_READINESS.md, "pki_relay.py/collect_
        # artifacts.py/cleanup.py... nunca invocam docker" --
        # orchestrator.py tem que respeitar a MESMA regra agora que
        # roda de dentro do controle). `deliver_images.py`, rodando na
        # maquina do OPERADOR (onde Docker existe), encosta os .tar +
        # `gateway_binary_info.json` + o binario `gateway` extraido
        # AQUI, num diretorio LOCAL do controle -- `_deliver_image`/
        # `_verify_gateway_binary` so leem arquivo local (Path, nunca
        # cli._run/docker) e falam com o HOST por scp/ssh, nunca
        # invocam `docker` localmente.
        self.images_staging_dir = Path(images_staging_dir) if images_staging_dir else Path.home() / "images"
        # Decisao 54, item 1: verificacao scp+sha256sum -c do binario
        # do gateway -- acumulado pra entrar no manifesto de cada bloco.
        self.gateway_binary_verifications = []
        # Decisao 55, item 2: docker load no HOST, carregado a partir
        # do .tar ja estagiado no controle -- uma entrada por entrega
        # de imagem (gateway/proxy/pqc-signer/measure).
        self.image_delivery_verifications = []
        # Decisao 58, achado 18: sondagem TCP pura, uma vez por rota,
        # ANTES de qualquer entrega/execucao cara daquela rota --
        # mesmo papel que `preflight_tcp.py` tinha na v8 real.
        self._tcp_preflight_done = set()
        self.tcp_preflight_results = []
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

    def _read_staged_gateway_binary_info(self):
        """Decisao 59: substitui `_local_gateway_binary_info` (achado
        real -- extrair com `docker create`/`docker cp`/`docker run`
        exigia Docker LOCAL, e o controle (onde este processo roda de
        verdade) nunca tem Docker, confirmado em PILOT_READINESS.md).
        A EXTRACAO (docker create/cp/run) agora acontece so na maquina
        do OPERADOR, dentro de `deliver_images.py` -- este metodo so
        LE o resultado ja estagiado (`gateway_binary_info.json`,
        arquivo LOCAL do controle, nunca cli._run/docker). A
        CONFERENCIA contra PINS.json e refeita AQUI tambem (nao so
        confiada no que `deliver_images.py` ja checou do lado do
        operador) -- fail-closed contra o PINS.json que o PROPRIO
        controle tem (pode ter ficado desatualizado/divergente do que
        o operador tinha no momento da extracao)."""
        info_path = self.images_staging_dir / "gateway_binary_info.json"
        if not info_path.is_file():
            raise RuntimeError(
                f"_read_staged_gateway_binary_info: {info_path} nao encontrado -- rode deliver_images.py "
                f"primeiro (operador -> controle, antes de qualquer start_block)"
            )
        info = json.loads(info_path.read_text(encoding="utf-8"))
        pins = load_pins()
        pin_sha256 = pins["images"]["gateway"]["binary_sha256"]
        if info["sha256"] != pin_sha256:
            raise RuntimeError(
                f"_read_staged_gateway_binary_info: sha256 do binario estagiado NAO bate com PINS.json "
                f"(copia do CONTROLE) -- esperado {pin_sha256}, obtido {info['sha256']}. Alterar PINS.json "
                f"exige Emenda numerada explicita em DECISIONS.md, nunca uma atualizacao automatica."
            )
        info["pin_matched"] = True
        info["pins_path"] = str(PINS_PATH)
        return info

    def _verify_gateway_binary(self, profile, route):
        """Decisao 54, item 1 -- implementa o mecanismo JA PRE-
        REGISTRADO (`v9-prereg`, secao "Entrega do binario": "operador
        `scp` o `gateway`/`proxy` (mais o `.sha256`) pro controle,
        controle `scp` pra cada instancia de destino... cada instancia
        roda `sha256sum -c` antes de usar"). Decisao 59: o binario
        `gateway` tambem vem ESTAGIADO no controle (`deliver_images.py`
        o copiou pra `images_staging_dir`, extraido na maquina do
        OPERADOR) -- este metodo so faz o SEGUNDO salto (controle ->
        host), scp de um arquivo LOCAL, nunca docker.

        Fecha o laco completo (nao so o transporte): depois de
        confirmar que o binario chegou intacto, `start_block` ainda
        confere que o binario DENTRO do container que vai de fato
        rodar (`docker exec ... sha256sum /gateway`) bate com o MESMO
        hash -- senao a verificacao do transporte provaria pouco (a
        imagem Docker podia ter sido construida de um binario
        diferente do que foi copiado aqui)."""
        info = self._read_staged_gateway_binary_info()
        local_bin_path = self.images_staging_dir / "gateway"
        if not local_bin_path.is_file():
            raise RuntimeError(
                f"_verify_gateway_binary {profile}/{route}: {local_bin_path} nao encontrado -- rode "
                f"deliver_images.py primeiro"
            )
        server_ip = self._server_ip()
        remote_dir = "~/pki/gateway_verify"
        remote_bin = f"{remote_dir}/gateway"
        remote_sha = f"{remote_dir}/gateway.sha256"

        cli.run_ssh(server_ip, f"mkdir -p {remote_dir}", key_path=self.key_path)
        scp_proc = cli.run_scp(str(local_bin_path), f"ec2-user@{server_ip}:{remote_bin}", key_path=self.key_path)
        if scp_proc.returncode != 0:
            raise RuntimeError(f"_verify_gateway_binary {profile}/{route}: scp do binario falhou: {scp_proc.stderr}")

        # sha256sum -c exige o formato "<hash>  <nome>" -- escrito
        # remotamente (nunca local) pra nao precisar de um segundo
        # scp so pra um arquivo de uma linha.
        cli.run_ssh(server_ip, f'echo "{info["sha256"]}  gateway" > {remote_sha}', key_path=self.key_path)
        verify_proc = cli.run_ssh(server_ip, f"cd {remote_dir} && sha256sum -c gateway.sha256", key_path=self.key_path)

        verification = {
            "profile": profile, "route": route,
            "sha256_expected": info["sha256"],
            "go_version_m": info["go_version_m"], "go_build_version": info["go_build_version"],
            "toolchain_build_metadata": info["toolchain_build_metadata"],
            "pin_matched": info["pin_matched"], "pins_path": info["pins_path"],
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
            "transfer_sha256sum_c_ok": verify_proc.returncode == 0,
            "transfer_sha256sum_c_output": (verify_proc.stdout + verify_proc.stderr).strip(),
            "running_container_sha256_ok": None, "running_container_sha256_output": None,
        }
        self.gateway_binary_verifications.append(verification)
        if verify_proc.returncode != 0:
            raise RuntimeError(
                f"_verify_gateway_binary {profile}/{route}: sha256sum -c FALHOU no transporte -- binario "
                f"adulterado ou corrompido, abortando ANTES de qualquer execucao: {verification['transfer_sha256sum_c_output']}"
            )
        return verification

    def _verify_running_gateway_binary(self, verification):
        """Segunda metade do laco (ver docstring de
        `_verify_gateway_binary`) -- chamada DEPOIS que
        `_launch_gateway` sobe o container, ainda antes de qualquer
        execucao cronometrada."""
        server_ip = self._server_ip()
        proc = cli.run_ssh(server_ip, f"docker exec {self.gateway_container} sha256sum /gateway", key_path=self.key_path)
        output = (proc.stdout + proc.stderr).strip()
        running_sha = output.split()[0] if output.split() else ""
        ok = proc.returncode == 0 and running_sha == verification["sha256_expected"]
        verification["running_container_sha256_ok"] = ok
        verification["running_container_sha256_output"] = output
        if not ok:
            raise RuntimeError(
                f"_verify_running_gateway_binary {verification['profile']}/{verification['route']}: "
                f"o binario DENTRO do container {self.gateway_container} nao bate com o verificado no "
                f"transporte -- abortando antes de qualquer execucao (saida: {output!r})"
            )

    def _deliver_image(self, image_key, host):
        """Decisao 59 (achado real: o controle nunca roda docker,
        confirmado em PILOT_READINESS.md -- `docker save | ssh ...
        docker load` da Decisao 55 exigia Docker LOCAL na maquina que
        executa `_deliver_image`, que e o CONTROLE agora que
        `orchestrator.py` roda de la). Segundo salto do modelo restaurado
        da v8 (`deliver_images.sh` real): o .tar JA chegou no controle
        via `deliver_images.py` (primeiro salto, operador -> controle,
        com Docker so do lado do operador) -- este metodo so faz scp
        do ARQUIVO LOCAL pro host e `ssh host docker load`, nunca
        docker localmente. Depois do load, confere o Image ID
        carregado contra PINS.json -- `docker load` e deterministico
        (nunca um rebuild), entao o MESMO Image ID tem que aparecer
        sempre, em qualquer instancia, pro mesmo `docker save` de
        origem. Fail-closed: levanta ANTES de qualquer execucao se
        divergir."""
        pins = load_pins()
        docker_image = pins["images"][image_key]["docker_image"]
        expected_id = pins["images"][image_key]["image_id"]

        local_tar_path = self.images_staging_dir / f"{image_key}.tar"
        if not local_tar_path.is_file():
            raise RuntimeError(
                f"_deliver_image({image_key}, {host}): {local_tar_path} nao encontrado no controle -- "
                f"rode deliver_images.py primeiro (operador -> controle)"
            )
        # Decisao 60, item 4 (pedido independente): tempo real do 2o
        # salto (controle -> host) -- scp do .tar + docker load +
        # conferencia de Image ID, pra reportar no ensaio por host/
        # imagem (nunca uma estimativa). `DELIVERY_SLOW_THRESHOLD_
        # SECONDS` e so um limiar de RELATORIO (marca `"slow": true`)
        # -- a decisao de abortar por demora e sempre do Luciano,
        # lendo o relatorio, nunca automatica.
        tar_bytes = local_tar_path.stat().st_size
        t0 = time.monotonic()
        remote_tar = f"~/{image_key}.tar"
        scp_proc = cli.run_scp(str(local_tar_path), f"ec2-user@{host}:{remote_tar}", key_path=self.key_path)
        if scp_proc.returncode != 0:
            raise RuntimeError(f"_deliver_image({image_key}, {host}): scp do tar pro host falhou: {scp_proc.stderr}")

        load_proc = cli.run_ssh(host, f"docker load < {remote_tar} && rm -f {remote_tar}", key_path=self.key_path)
        if load_proc.returncode != 0:
            raise RuntimeError(f"_deliver_image({image_key}, {host}): docker load no host falhou: {load_proc.stderr}")

        id_proc = cli.run_ssh(host, f"docker image inspect {docker_image} --format '{{{{.Id}}}}'", key_path=self.key_path)
        elapsed_seconds = time.monotonic() - t0
        loaded_id = id_proc.stdout.strip()
        ok = id_proc.returncode == 0 and loaded_id == expected_id
        self.image_delivery_verifications.append({
            "image_key": image_key, "docker_image": docker_image, "host": host,
            "expected_image_id": expected_id, "loaded_image_id": loaded_id, "ok": ok,
            "tar_bytes": tar_bytes, "elapsed_seconds": round(elapsed_seconds, 1),
            "slow": elapsed_seconds > DELIVERY_SLOW_THRESHOLD_SECONDS,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        if not ok:
            raise RuntimeError(
                f"_deliver_image({image_key}, {host}): Image ID carregado ({loaded_id!r}) nao bate com "
                f"PINS.json ({expected_id!r}) -- abortando ANTES de qualquer execucao"
            )

    def _launch_gateway(self, profile, keylog=False):
        """Decisao 52 (Emenda 14): fatorado de `start_block` pra ser
        reusado por `dedicated_capture` tambem -- o UNICO lugar que
        decide se o gateway sobe com `KEYLOG_PATH` ou nao.
        `keylog=False` (usado por `start_block`, toda janela
        CRONOMETRADA) nunca passa a flag -- o gateway nunca escreve
        keylog ali, nenhum I/O extra por handshake durante qualquer
        das 60 execucoes reais. `keylog=True` (usado SO por
        `dedicated_capture`, Decisao 52 item 2) reinicia o MESMO
        container com a flag acrescentada -- a reinicializacao
        acontece inteiramente DENTRO do laco separado de capturas
        dedicadas de `run_pilot` (depois que as 60 execucoes e seus
        `stop_block` ja terminaram, nunca entre elas), entao nenhum
        dado ja medido e alterado por ela."""
        keylog_flag = "-e KEYLOG_PATH=/tmp/v9_keylog.txt " if keylog else ""
        # Decisao 58 (achado real desta rodada): `$(pwd)/../../mock-
        # service-os/certs` so faz sentido quando `cli.run_ssh` dispara
        # de verdade pro HOST REMOTO -- la, `$(pwd)` resolve pro
        # diretorio padrao do login SSH (`/home/ec2-user`), nunca pro
        # layout relativo do repo local; `/home/ec2-user/../../mock-
        # service-os/certs` nao existe em nenhuma instancia real, e
        # nada neste pacote jamais entregava nada ali -- confirmado
        # lendo `deliver_source.py` (Decisao 58, novo: entrega
        # `mock-service-os/certs` pra `~/mock-service-os/certs`,
        # espelhando o layout relativo do repo sob `~`, mesmo padrao
        # que `deliver_source.sh` real da v8 ja usava). `~` (expandido
        # pelo PROPRIO shell remoto, nunca por este processo) e o
        # caminho correto pro caso remoto de verdade. `local_shim_
        # bridge_join=True` (SO validacao local, Decisao 49) continua
        # usando `$(pwd)/../../...` -- o shim local (`_LocalShellShim`)
        # roda com `cwd=scripts_cwd`, onde essa expressao relativa
        # resolve pro `mock-service-os/certs` de VERDADE deste
        # repositorio; mudar pra `~` quebraria essa validacao (o HOME
        # desta maquina de desenvolvimento nao e a raiz do repo).
        real_certs_mount = (
            "$(pwd)/../../mock-service-os/certs" if self.local_shim_bridge_join
            else "~/mock-service-os/certs"
        )
        cli.run_ssh(self._server_ip(), f"docker rm -f {self.gateway_container} 2>/dev/null; true", key_path=self.key_path)
        cli.run_ssh(self._server_ip(),
                    f"docker run -d --name {self.gateway_container} "
                    f"--network insurance-server-lambdas_default "
                    f"--network-alias mtls --network-alias matls-auth.local --network-alias auth.local "
                    f"--network-alias matls-api.local --network-alias api.local --network-alias directory "
                    f"-e HTTP_MODE=business -e TICKETS_DISABLED=true -e CRYPTO_PROFILE={profile} "
                    f"{keylog_flag}"
                    f"-v {real_certs_mount}:/real-certs:ro mockopin-v9-gateway",
                    key_path=self.key_path)
        # Espera o gateway de verdade terminar de subir (carregar os
        # certs, abrir :443) antes do proxy tentar discar -- achado ao
        # vivo (Decisao 49): sem isso, a primeira chamada do proxy
        # pode cair numa janela em que o container ja existe mas ainda
        # nao esta aceitando conexao, devolvendo 502 rio abaixo.
        cli.run_ssh(self._server_ip(),
                    f"for i in $(seq 1 30); do docker logs {self.gateway_container} 2>&1 | grep -q 'listening on' && break; sleep 1; done",
                    key_path=self.key_path)

    def _tcp_preflight(self, route):
        """Decisao 58, achado 18: mesma checagem, mesma justificativa
        literal do `tcp_check_from_client` real da v8 (`preflight_tcp.py`)
        -- conecta via `/dev/tcp` DE DENTRO do CLIENTE (nunca do
        controle: a v8 ja registrou que o caminho de rede e diferente,
        e o caso co-localizado depende especificamente do IP PRIVADO
        do servidor, que so o cliente de fato disca). Roda UMA vez por
        rota (nao por bloco/perfil -- a rota e o SG nunca mudam entre
        perfis), ANTES de qualquer entrega de imagem/verificacao cara
        -- barato, falha rapido se o Security Group/VPC estiver
        errado, sem esperar o resto do `start_block` pra descobrir."""
        if route in self._tcp_preflight_done:
            return
        gw_ip = self._server_gateway_ip(route)
        timeout = 5
        cmd = f"timeout {timeout} bash -c 'echo > /dev/tcp/{gw_ip}/443' && echo OK || echo FAIL"
        proc = cli.run_ssh(self._client_ip(route), cmd, key_path=self.key_path)
        ok = "OK" in (proc.stdout or "")
        self.tcp_preflight_results.append({"route": route, "gateway_ip": gw_ip, "ok": ok,
                                            "output": (proc.stdout + proc.stderr).strip()})
        self._tcp_preflight_done.add(route)
        if not ok:
            raise RuntimeError(
                f"_tcp_preflight {route}: cliente nao alcancou {gw_ip}:443 por TCP puro -- "
                f"provavel Security Group/VPC errado, abortando ANTES de qualquer entrega de imagem "
                f"(saida: {(proc.stdout + proc.stderr).strip()!r})"
            )

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
        self._tcp_preflight(route)
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
        # Decisao 55, item 2: entrega por save/load, NUNCA build na
        # instancia -- ANTES de qualquer verificacao/execucao.
        self._deliver_image("gateway", self._server_ip())
        verification = self._verify_gateway_binary(profile, route)
        self._launch_gateway(profile)
        self._verify_running_gateway_binary(verification)
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
        # Decisao 55, item 2: o proxy roda no CLIENTE, via save/load
        # tambem -- nunca `docker build` la (opin_flow.start_tls_kem_
        # proxy so faz `docker run`, presume a imagem ja presente).
        self._deliver_image("proxy", self._client_ip(route))
        # Decisao 58 (Emenda, achado real desta rodada): of.start_pqc_
        # signer_service() (chamado embaixo, pra TODOS os 4 perfis,
        # sem nenhum desvio V9_HARNESS -- diferente de start_tls_kem_
        # proxy, que TEM um) faz `docker run -d ... mockopin-pqc-signer
        # node server.mjs` incondicionalmente. NENHUM codigo deste
        # pacote jamais entregava essa imagem ao cliente antes desta
        # correcao -- mesma classe de bug que a v8 encontrou e corrigiu
        # em deliver_images.sh (CLIENT_IMAGES nunca chegavam ao
        # cliente). Agora pinada em PINS.json e entregue pela MESMA via
        # `_deliver_image` (save/load, fail-closed) que gateway/proxy
        # ja usam -- nunca um mecanismo novo.
        self._deliver_image("pqc-signer", self._client_ip(route))
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

    def capture_ready_check(self):
        """Decisao 53, item 4c: fail-closed, chamado pelo smoke gate
        ANTES de qualquer execucao -- hoje, so o servidor roda tcpdump/
        docker exec/tshark de verdade (ver `dedicated_capture`), entao
        a lista de hosts e so `[self._server_ip()]`."""
        return preflight.run_capture_preflight([self._server_ip()], key_path=self.key_path)

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
        tcpdump do servidor esta rodando.

        **KEYLOG_PATH, Emenda 14 (correcao desta rodada):** `run_pilot`
        roda as 12 capturas dedicadas num laco SEPARADO, depois que as
        60 execucoes (e os `stop_block` de cada bloco) ja terminaram --
        entao o gateway que esta rodando neste ponto pode ser de
        QUALQUER perfil (o ultimo bloco da grade), nunca garantido ser
        o perfil desta captura especifica. Por isso esta funcao chama
        `start_block` (sobe backend/proxy/signer certos pro PERFIL
        desta captura, SEM keylog) e, so entao, `_launch_gateway(...,
        keylog=True)` reinicia so o gateway, acrescentando
        KEYLOG_PATH -- a UNICA chamada deste modulo que liga essa flag.
        As duas reinicializacoes acontecem inteiramente dentro deste
        laco de capturas dedicadas, nunca entre uma execucao
        cronometrada e outra -- nenhum dado das 60 execucoes (ja
        gravado antes deste laco comecar) e alterado por elas."""
        self.start_block(profile, route)
        self._launch_gateway(profile, keylog=True)
        # `start_block` ja verificou o transporte e o container
        # anterior -- esta e so a MESMA imagem reiniciada (keylog=True
        # nunca muda o binario), mas confere de novo porque e um
        # container NOVO (reconfere o running_container_sha256, nunca
        # reconfere o transporte -- o binario local nao mudou).
        self._verify_running_gateway_binary(self.gateway_binary_verifications[-1])

        server_ip = self._server_ip()
        # Decisao 55, item 2: mockopin-v9-measure (tshark) tambem por
        # save/load -- nunca `docker build` na instancia.
        self._deliver_image("measure", server_ip)
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
        self.stop_block(profile, route)
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
        # Decisao 54, item 1: verificacao scp+sha256sum -c do binario
        # do gateway, uma entrada por bloco (start_block) -- lista
        # vazia pro LocalExecutor (nunca tem binario real pra
        # verificar).
        "gateway_binary_verifications": getattr(executor, "gateway_binary_verifications", []),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


SMOKE_N_PER_PROFILE = 1
SMOKE_EXPECTED_TOTAL = len(PROFILES) * len(ROUTES) * SMOKE_N_PER_PROFILE  # 12


_DEFAULT_CERTS_DIR = Path(__file__).resolve().parents[2] / "certs" / "generated"
_BYTES_DIAGNOSTIC_LOG_RE_TEMPLATE = (
    r'gateway: {profile} connection OK remoteAddr=\S+ sni="mtls"[^\n]*?'
    r'handshakeBytesIn=(\d+) handshakeBytesOut=(\d+)'
)


def _bytes_diagnostic_for_profile(log_text: str, profile: str, certs_dir) -> dict:
    """Decisao 55, item 3: compara `ec.expected_handshake_bytes`
    (baseline MEDIDO + diferenca de DER dos certificados implantados)
    contra UMA conexao client-facing real deste perfil no log dado.
    DIAGNOSTICO -- nunca o criterio 1 oficial (0B/±4B/0B continuam
    sendo o gate real, Decisao 20/29/30). Desvio != 0 aqui nunca
    aborta por conta propria -- so marca `bytes_diagnostic_needs_
    decision`, pra o Luciano decidir, mesma logica do smoke gate
    (Decisao 48)."""
    expected = ec.expected_handshake_bytes(profile, str(certs_dir))
    pattern = _BYTES_DIAGNOSTIC_LOG_RE_TEMPLATE.format(profile=_re.escape(profile))
    m = _re.search(pattern, log_text)
    if not m:
        return {"profile": profile, "ok": False, "expected": expected,
                "note": "nenhuma linha 'connection OK' client-facing encontrada pra este perfil no log"}
    measured_in, measured_out = int(m.group(1)), int(m.group(2))
    delta_in, delta_out = measured_in - expected["in"], measured_out - expected["out"]
    return {
        "profile": profile, "expected": expected,
        "measured_in": measured_in, "measured_out": measured_out,
        "delta_in": delta_in, "delta_out": delta_out,
        "ok": delta_in == 0 and delta_out == 0,
    }


def run_smoke_gate(executor, seed: int, out_dir: Path, certs_dir=_DEFAULT_CERTS_DIR) -> dict:
    """Decisao 48 (Emenda 12 ao pre-registro v9-prereg): 1 execucao
    por perfil x rota (12 no total, NUNCA contadas nas 60 oficiais) --
    roda ANTES do bloco cronometrado, so com `SSHExecutor` real,
    contra as instancias de verdade recem-subidas. Critério de
    abortar: QUALQUER uma das 12 execucoes falhando (excecao,
    `insurance`/`person` vazios, ou qualquer criterio avaliavel por
    execucao-unica dando FAIL) e motivo pra abortar o piloto inteiro
    e destruir -- nunca prosseguir pras 60 execucoes reais sobre uma
    infraestrutura que a propria porta de fumaca ja mostrou com
    problema.

    Decisao 53 (pedido independente, item 4): dois acrescimos.
    **4c, fail-closed ANTES de qualquer execucao:** `capture_ready_
    check()` roda primeiro -- se reprovar (tcpdump/sudo/imagem/
    interface ausentes), a porta de fumaca aborta imediatamente, SEM
    rodar nenhuma das 12 execucoes, com a lista exata do que falta.
    **4b, prova da captura em si:** depois das 12 execucoes (ainda
    `skip_dedicated_captures=True` -- as 12 capturas OFICIAIS do
    criterio 1 continuam responsabilidade separada, Decisao 41), roda
    UMA `dedicated_capture` de prova por PERFIL (4, nao 12 -- so pra
    validar o MECANISMO fim a fim antes de confiar nas 60/12 oficiais),
    escrita num diretorio PROPRIO (`smoke_capture_proof/`), nunca
    confundida com `criterio1_capturas/`."""
    capture_preflight = executor.capture_ready_check()
    if not capture_preflight["go"]:
        missing_summary = [
            {"host": c.get("host"), "missing": c.get("missing")}
            for c in capture_preflight["checks"] if not c.get("ok", True)
        ]
        return {
            "smoke": True, "smoke_ok": False, "aborted_before_execution": True,
            "capture_preflight": capture_preflight,
            "smoke_failures": [], "total_execucoes": 0, "expected_total": SMOKE_EXPECTED_TOTAL,
            "note": ("pre-requisitos de captura (criterio 1) reprovaram -- nenhuma execucao rodou "
                     f"(Decisao 53, item 4c): {missing_summary}"),
        }

    manifest = run_pilot(executor, seed, out_dir, n_per_profile=SMOKE_N_PER_PROFILE, smoke=True,
                          skip_dedicated_captures=True)
    execucoes = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))
    failures = []
    for entry in execucoes:
        counts = ec._http_counts_for_calls(entry)
        if counts != _EXPECTED_HTTP:
            failures.append({"profile": entry["profile"], "route": entry["route"],
                              "esperado": _EXPECTED_HTTP, "obtido": counts})

    capture_proof_dir = out_dir / "smoke_capture_proof"
    capture_proof_dir.mkdir(parents=True, exist_ok=True)
    capture_proof_rows = []
    for profile in PROFILES:
        route = ROUTES[0]  # qualquer rota prova o MECANISMO -- nunca uma das 12 capturas oficiais
        try:
            block = executor.dedicated_capture(profile, route)
            row = ec._message_sizes_for_profile(block, profile)
            (capture_proof_dir / f"{profile}.log").write_text(block, encoding="utf-8")
            capture_proof_rows.append({"profile": profile, "ok": row["ok"]})
        except Exception as e:  # noqa: BLE001 -- captura/decifragem real pode falhar de varios jeitos; nunca estoura o smoke gate inteiro sem reportar qual perfil
            capture_proof_rows.append({"profile": profile, "ok": False, "note": f"{type(e).__name__}: {e}"})
    capture_proof_ok = all(r["ok"] for r in capture_proof_rows)

    # Decisao 55, item 3: diagnostico (NUNCA o gate oficial -- os
    # limiares pre-registrados do criterio 1 continuam sendo isso).
    # Desvio != 0 PAUSA e pergunta, igual ao smoke gate -- nunca
    # aborta por conta propria, nunca e ignorado em silencio.
    combined_log_text = Path(manifest["combined_log"]).read_text(encoding="utf-8")
    bytes_diagnostic_rows = [
        _bytes_diagnostic_for_profile(combined_log_text, profile, certs_dir) for profile in PROFILES
    ]
    bytes_diagnostic_needs_decision = any(not r["ok"] for r in bytes_diagnostic_rows)

    manifest["capture_preflight"] = capture_preflight
    manifest["capture_proof_dir"] = str(capture_proof_dir)
    manifest["capture_proof_rows"] = capture_proof_rows
    manifest["capture_proof_ok"] = capture_proof_ok
    manifest["bytes_diagnostic_rows"] = bytes_diagnostic_rows
    manifest["bytes_diagnostic_needs_decision"] = bytes_diagnostic_needs_decision
    manifest["smoke_ok"] = (manifest["total_execucoes"] == SMOKE_EXPECTED_TOTAL and not failures and capture_proof_ok)
    manifest["smoke_failures"] = failures
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def exercise_start_stop(executor: "SSHExecutor", profile: str, route: str) -> dict:
    """Decisao 58, item 5 (INFRA_REHEARSAL.md): exercicio de start_
    block/stop_block REMOTOS, um perfil numa rota so (default do
    roteiro: classico/L0) -- prova que TODOS os containers (gateway,
    proxy, pqc-signer) sobem e descem de verdade, SEM nenhuma execucao
    cronometrada e SEM contar nas 60/12 oficiais (nunca chama
    run_execution/readiness_probe, nunca escreve manifest.json/
    piloto_calls.json -- so imprime um relatorio proprio, incapaz de
    ser confundido com um bloco real)."""
    report = {"profile": profile, "route": route, "started_at_utc": datetime.now(timezone.utc).isoformat()}
    executor.start_block(profile, route)
    report["start_block_ok"] = True
    report["gateway_binary_verifications"] = list(executor.gateway_binary_verifications)
    report["image_delivery_verifications"] = list(executor.image_delivery_verifications)
    report["tcp_preflight_results"] = list(executor.tcp_preflight_results)
    executor.stop_block(profile, route)
    report["stop_block_ok"] = True
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["note"] = ("exercicio de infraestrutura -- NUNCA uma execucao cronometrada, nunca conta nas "
                       "60/12 oficiais, nenhum manifest.json escrito por esta chamada")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["simulate", "ssh"], default="simulate")
    ap.add_argument("--seed", type=int, default=20261107)
    ap.add_argument("--out", required=False)
    ap.add_argument("--inventory-json", help="obrigatorio no modo --mode ssh (terraform output -json inventory)")
    ap.add_argument("--ssh-key", help="caminho da chave privada do piloto (modo ssh)")
    ap.add_argument("--images-staging-dir", help="Decisao 59: diretorio LOCAL (no controle) onde "
                     "deliver_images.py ja estagiou os .tar/gateway_binary_info.json -- default ~/images")
    ap.add_argument("--smoke", action="store_true",
                     help="Decisao 48: porta de fumaca, 1 execucao por perfil x rota (12, nunca contadas nas 60)")
    ap.add_argument("--exercise-start-stop", action="store_true",
                     help="Decisao 58, item 5: exercicio REMOTO de start_block/stop_block num unico "
                          "perfil/rota, sem execucao cronometrada, nunca contado nas 60/12 oficiais")
    ap.add_argument("--exercise-profile", default="classico")
    ap.add_argument("--exercise-route", default="L0")
    args = ap.parse_args()

    if args.mode == "simulate":
        executor = LocalExecutor()
    else:
        if not args.inventory_json:
            ap.error("--mode ssh exige --inventory-json")
        inventory = json.load(open(args.inventory_json, encoding="utf-8"))
        executor = SSHExecutor(inventory, key_path=args.ssh_key, images_staging_dir=args.images_staging_dir)

    if args.exercise_start_stop:
        report = exercise_start_stop(executor, args.exercise_profile, args.exercise_route)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    if not args.out:
        ap.error("--out e obrigatorio fora do modo --exercise-start-stop")

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

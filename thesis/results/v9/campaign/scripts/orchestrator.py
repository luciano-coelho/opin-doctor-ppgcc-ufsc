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
import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import preflight  # noqa: E402  -- Decisao 53, item 4: pre-requisitos de captura por host
import deliver_images  # noqa: E402  -- Decisao 83: BACKEND_IMAGE_KEYS, nunca duplicado aqui
import cost_tracker as ct  # noqa: E402  -- Etapa 1 do piloto v9, item 2: trava local de custo

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


# Protocolo de 5 aquecimentos full-flow por celula por janela (Decisao
# do Luciano apos a revisao final, item A): marcador PROPRIO, nunca
# "EXECUCAO INICIO/FIM" -- o parser de evaluate_criteria.py (`_execucao_
# window`, regex sobre esses marcadores) so reconhece o segundo, entao
# um aquecimento nunca e contado como execucao oficial so por existir
# no mesmo combined log.
def aquecimento_marker_inicio(profile, route, warmup):
    return f"== AQUECIMENTO INICIO perfil={profile} rota={route} warmup={warmup} =="


def aquecimento_marker_fim(profile, route, warmup):
    return f"== AQUECIMENTO FIM perfil={profile} rota={route} warmup={warmup} =="


def _connection_ok_line(sni="mtls", remote="10.0.0.1:443"):
    return f'gateway: PERFIL connection OK remoteAddr={remote} sni="{sni}"'


def _steal_pct_from_cpu_jsonl(path: Path):
    """Achado 10 (implementado, pedido do Luciano) -- mesma formula
    EXATA de `campaign_run.py._steal_pct_from_cpu_jsonl` da v8 real:
    delta cumulativo de jiffies entre a PRIMEIRA e a ULTIMA amostra do
    arquivo (nunca uma razao desde o boot). `None` se o arquivo faltar,
    tiver menos de 2 linhas, ou os campos nao fecharem -- nunca um
    numero inventado."""
    if not Path(path).is_file():
        return None
    lines = [l for l in Path(path).read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    if len(lines) < 2:
        return None
    try:
        first, last = json.loads(lines[0]), json.loads(lines[-1])
        f0 = [int(x) for x in first["proc_stat_line"].split()[1:11]]
        f1 = [int(x) for x in last["proc_stat_line"].split()[1:11]]
    except (json.JSONDecodeError, KeyError, ValueError, IndexError):
        return None
    dtotal, dsteal = sum(f1) - sum(f0), f1[7] - f0[7]
    return 100 * dsteal / dtotal if dtotal > 0 else None


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
        DualAuthenticated do perfil.

        `start_utc`/`end_utc` por chamada (pedido do Luciano, Etapa 1 --
        lacuna real encontrada na rodada de robustez: `build_consolidated_
        report_v9.py:build_latency` exige esses dois campos em TODA
        chamada, e esta simulacao nunca os gravava, quebrando a
        consolidacao sempre que rodada contra `--mode simulate`). Sem
        chamada HTTP real nenhuma pra cronometrar de verdade -- os dois
        campos sao o MESMO instante de entrada/saida desta funcao,
        mesma honestidade ja usada em `opin_flow.py` (hop nao
        cronometrado independentemente: "start_utc/end_utc sao o MESMO
        instante, nunca um par real de inicio/fim")."""
        t0 = datetime.now(timezone.utc).isoformat()
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
        t1 = datetime.now(timezone.utc).isoformat()
        for c in all_calls:
            c["start_utc"] = t0
            c["end_utc"] = t1
            # Nunca cronometrado por chamada individual nesta simulacao
            # (mesma limitacao de start_utc/end_utc acima) -- 0.0 e o
            # valor honesto, nunca um numero inventado.
            c["latency_ms"] = 0.0
        dual = True if profile == "hibrido-and" else False
        return {
            "insurance": insurance, "person": person,
            "gateway_log_lines": lines,
            "curveID": ec.EXPECTED_CURVE[profile], "dualAuthenticated": dual,
            "start_utc": t0, "end_utc": t1,
        }

    def dedicated_capture(self, profile, route, capturas_dir=None):
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
                 images_staging_dir=None, route_server=None):
        self.inventory = inventory
        # Generalizacao pra N servidores (campanha oficial, pedido do
        # Luciano): None (default) = piloto, 1 servidor so,
        # inventory["server"] (singular) -- caminho INTOCADO, byte a
        # byte igual ao de sempre. dict rota->id_de_servidor (ex.:
        # campaign_topology.CAMPAIGN_ROUTE_SERVER) = campanha oficial,
        # inventory["servers"] (plural, um dict por servidor) -- toda
        # resolucao de "qual servidor" passa por `_server_key(route)`,
        # nunca mais por `inventory["server"]` direto.
        self.route_server = route_server
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
        # Decisao 83/87: backend de negocio -- as 3 imagens CUSTOM
        # (auth/mongo_seed/mockapi) entregues UMA vez por fleet (nunca
        # por bloco -- essas imagens nunca trocam de CRYPTO_PROFILE em
        # si); psql/localstack/mongodb (estoque, ja pinadas por digest
        # exato no proprio docker-compose.yml) sao puladas direto pelo
        # `docker compose up`, nunca por este mecanismo (Decisao 87).
        # Amostras de CPU/memoria do servidor pra comparar com o que a
        # v8 ja mediu (mesmo formato de sempre, campaign_run.py.
        # _sample_cpu_mem_steal() -- /proc/stat+/proc/meminfo, nunca
        # `docker stats`).
        # Conjunto de IPs de servidor ja entregues (piloto: no maximo
        # 1 elemento, mesmo comportamento de sempre; campanha oficial:
        # ate N, um guard de idempotencia POR servidor).
        self._backend_delivered = set()
        self.cpu_mem_samples = []
        # Achado 10 (implementado, pedido do Luciano, modo campanha so
        # -- ver `_cpu_steal_sampler_start`): resultados do sampler
        # periodico real (steal% por bloco, janela inteira) + os
        # caminhos remotos em voo entre start_block/stop_block.
        self.cpu_steal_samples = []
        self._cpu_steal_sampler_paths = {}

    def _server_key(self, route=None) -> dict:
        """Resolve qual entrada do inventario usar pro servidor.
        Piloto (`self.route_server is None`): sempre a entrada UNICA
        `inventory["server"]`, `route` nunca importa -- caminho
        INTOCADO. Campanha oficial (`self.route_server` setado): usa
        `route` pra achar o id do servidor certo em `inventory
        ["servers"]` -- `route` passa a ser OBRIGATORIO (sem ele, nao
        ha como saber qual dos N servidores, fail-closed por
        TypeError/KeyError explicito, nunca um default silencioso)."""
        if self.route_server is None:
            return self.inventory["server"]
        server_id = self.route_server[route]
        return self.inventory["servers"][server_id]

    def _server_ip(self, route=None):
        return self._server_key(route)["public_ip"]

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
        server = self._server_key(route)
        return server["private_ip"] if client.get("colocated") else server["public_ip"]

    def _env_prefix(self, env: dict) -> str:
        return " ".join(f"{k}={v}" for k, v in env.items())

    def _client_env(self, profile, server_gw_ip):
        return {
            "V9_HARNESS": "1",
            "CRYPTO_PROFILE": CLIENT_CRYPTO_PROFILE_ENV[profile],
            "REMOTE_GATEWAY_HOST": server_gw_ip,
        }

    def _gateway_logs(self, since_iso, until_iso, route=None):
        """`docker logs -t --since ... --until ...` no CONTAINER DO
        GATEWAY -- mesma chamada que `stop_block_proxies`/
        `run_one_execution` da v8 real fazem (so troca o nome fixo do
        container, `self.of.GATEWAY_CONTAINER`/
        `insurance-server-lambdas-mtls-1`, pelo equivalente da v9).
        `route=None` continua resolvendo o servidor UNICO do piloto
        (`_server_ip`/`_server_key`); a campanha oficial precisa de
        `route` pra saber de qual dos N servidores ler o log."""
        proc = cli.run_ssh(self._server_ip(route),
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
        server_ip = self._server_ip(route)
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
        server_ip = self._server_ip(verification.get("route"))
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
        docker localmente.

        Decisao 68 (Emenda -- substitui a verificacao por Image ID):
        achado real, ao vivo (Decisao 67), que `docker image inspect
        .Id` diverge entre versoes diferentes de Docker mesmo pro
        MESMO `.tar`, com conteudo comprovadamente identico
        (confirmado com `docker:25-dind` -- ver PINS.json,
        `_image_identity_note`). O fail-closed agora exige, nesta
        ordem: (1) sha256 do `.tar` local igual a `tar_sha256`
        pinado (ANTES de qualquer scp -- mais barato, pega corrupcao
        antes de gastar a transferencia); (2) apos o load,
        `RootFS.Layers` do host identicas a `rootfs_layers`; (3) o
        subconjunto de `.Config` do host identico a `config_subset`;
        (4) pra imagens com binario Go proprio (`gateway`/`proxy`),
        o sha256 do binario DENTRO do container carregado, igual a
        `binary_sha256`. Image ID continua lido/registrado, so como
        campo INFORMATIVO -- nunca comparado, nunca motivo de aborto."""
        pins = load_pins()
        image_pins = pins["images"][image_key]
        docker_image = image_pins["docker_image"]
        expected_tar_sha256 = image_pins["tar_sha256"]
        expected_layers = image_pins["rootfs_layers"]
        expected_config = image_pins["config_subset"]
        binary_path = image_pins.get("binary_path_in_image")
        expected_binary_sha256 = image_pins.get("binary_sha256")

        local_tar_path = self.images_staging_dir / f"{image_key}.tar"
        if not local_tar_path.is_file():
            raise RuntimeError(
                f"_deliver_image({image_key}, {host}): {local_tar_path} nao encontrado no controle -- "
                f"rode deliver_images.py primeiro (operador -> controle)"
            )
        tar_bytes = local_tar_path.stat().st_size
        actual_tar_sha256 = hashlib.sha256(local_tar_path.read_bytes()).hexdigest()
        if actual_tar_sha256 != expected_tar_sha256:
            raise RuntimeError(
                f"_deliver_image({image_key}, {host}): sha256 do .tar estagiado no controle "
                f"({actual_tar_sha256!r}) nao bate com PINS.json ({expected_tar_sha256!r}) -- "
                f"abortando ANTES de qualquer scp"
            )

        # Decisao 60, item 4 (pedido independente): tempo real do 2o
        # salto (controle -> host) -- scp do .tar + docker load +
        # conferencia de identidade, pra reportar no ensaio por host/
        # imagem (nunca uma estimativa). `DELIVERY_SLOW_THRESHOLD_
        # SECONDS` e so um limiar de RELATORIO (marca `"slow": true`)
        # -- a decisao de abortar por demora e sempre do Luciano,
        # lendo o relatorio, nunca automatica.
        t0 = time.monotonic()
        remote_tar = f"~/{image_key}.tar"
        scp_proc = cli.run_scp(str(local_tar_path), f"ec2-user@{host}:{remote_tar}", key_path=self.key_path)
        if scp_proc.returncode != 0:
            raise RuntimeError(f"_deliver_image({image_key}, {host}): scp do tar pro host falhou: {scp_proc.stderr}")

        load_proc = cli.run_ssh(host, f"docker load < {remote_tar} && rm -f {remote_tar}", key_path=self.key_path)
        if load_proc.returncode != 0:
            raise RuntimeError(f"_deliver_image({image_key}, {host}): docker load no host falhou: {load_proc.stderr}")

        id_proc = cli.run_ssh(host, f"docker image inspect {docker_image} --format '{{{{.Id}}}}'", key_path=self.key_path)
        loaded_id = id_proc.stdout.strip()

        layers_proc = cli.run_ssh(host, f"docker image inspect {docker_image} --format '{{{{json .RootFS.Layers}}}}'", key_path=self.key_path)
        actual_layers = json.loads(layers_proc.stdout.strip()) if layers_proc.returncode == 0 and layers_proc.stdout.strip() else None
        layers_ok = actual_layers == expected_layers

        config_proc = cli.run_ssh(host, f"docker image inspect {docker_image} --format '{{{{json .Config}}}}'", key_path=self.key_path)
        full_config = json.loads(config_proc.stdout.strip()) if config_proc.returncode == 0 and config_proc.stdout.strip() else {}
        actual_config = {k: full_config.get(k) for k in ("Entrypoint", "Cmd", "Env", "ExposedPorts")}
        config_ok = actual_config == expected_config

        binary_ok = True
        actual_binary_sha256 = None
        if binary_path:
            bin_proc = cli.run_ssh(host, f"docker run --rm --entrypoint sha256sum {docker_image} {binary_path}", key_path=self.key_path)
            actual_binary_sha256 = bin_proc.stdout.split()[0] if bin_proc.returncode == 0 and bin_proc.stdout.strip() else None
            binary_ok = actual_binary_sha256 == expected_binary_sha256

        elapsed_seconds = time.monotonic() - t0
        ok = layers_ok and config_ok and binary_ok
        self.image_delivery_verifications.append({
            "image_key": image_key, "docker_image": docker_image, "host": host,
            "loaded_image_id": loaded_id, "ok": ok,
            "layers_ok": layers_ok, "config_ok": config_ok, "binary_ok": binary_ok,
            "actual_binary_sha256": actual_binary_sha256, "expected_binary_sha256": expected_binary_sha256,
            "tar_bytes": tar_bytes, "elapsed_seconds": round(elapsed_seconds, 1),
            "slow": elapsed_seconds > DELIVERY_SLOW_THRESHOLD_SECONDS,
            "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        if not ok:
            raise RuntimeError(
                f"_deliver_image({image_key}, {host}): identidade nao confere (layers_ok={layers_ok}, "
                f"config_ok={config_ok}, binary_ok={binary_ok}) -- abortando ANTES de qualquer execucao"
            )

    def _deliver_backend_images(self, route=None):
        """Decisao 83/87 (pedido do Luciano, apos a Decisao 82): entrega
        as 3 imagens CUSTOM do backend de negocio da v8 (auth/mongo_
        seed/mockapi) ao SERVIDOR, UMA vez por fleet -- mesmo mecanismo
        de sempre (`_deliver_image`, save/load + verificacao por
        conteudo contra PINS.json, Decisao 68), nenhum mecanismo novo.
        psql/localstack/mongodb (estoque) NUNCA passam por aqui --
        Decisao 87, achado real: `docker save` de uma imagem referenciada
        SO por digest nunca preserva nome/digest atraves de save/load
        (confirmado ao vivo num docker:25-dind limpo -- so um Image ID
        solto sobrevive) -- `docker compose up` ja resolve essas 3
        corretamente (pull direto do registry publico, mesmo digest
        exato que o `docker-compose.yml` ja fixa). Idempotente via
        guarda explicita (nunca reentrega a cada bloco -- so gateway/
        proxy/pqc-signer trocam de verdade por bloco, o backend custom
        nunca muda de binario, so de conteudo seedado pelo proprio
        compose)."""
        server_ip = self._server_ip(route)
        if server_ip in self._backend_delivered:
            return
        for key in deliver_images.BACKEND_IMAGE_KEYS:
            self._deliver_image(key, server_ip)
        self._backend_delivered.add(server_ip)

    def _sample_cpu_mem(self, host) -> dict:
        """Decisao 83 (pedido do Luciano, item 1: comparar CPU/memoria
        do servidor com o que a v8 ja mediu) -- MESMO formato que
        `campaign_run.py._sample_cpu_mem_steal()` ja usa (`/proc/stat`
        linha `cpu` + `/proc/meminfo`, nunca `docker stats` -- motivo
        de sempre: `/proc/stat` inclui `steal`, visivel so no nivel do
        HOST, nunca de dentro de um container)."""
        proc = cli.run_ssh(host, "cat /proc/stat | head -1; echo ---MEMINFO---; cat /proc/meminfo",
                            key_path=self.key_path)
        sample = {"sampled_at_utc": datetime.now(timezone.utc).isoformat()}
        if proc.returncode != 0:
            sample["error"] = cli.redact(proc.stderr)
            return sample
        stat_part, _, mem_part = (proc.stdout or "").partition("---MEMINFO---")
        sample["proc_stat_line"] = stat_part.strip()
        sample["proc_meminfo_raw"] = mem_part.strip()
        return sample

    # Achado 10 (lacuna conhecida desde a Decisao 58, NUNCA implementada
    # pro piloto por desenho explicito -- "precisa ser resolvida ANTES
    # de uma campanha oficial real, nao antes do piloto"): implementado
    # agora, pedido do Luciano, generalizacao N-servidores. Porta FIEL o
    # mecanismo REAL da v8 (`campaign_run.py` -- `_cpu_mem_sampler_
    # start_cmd`/`_cpu_mem_sampler_stop_cmd`/`_steal_pct_from_cpu_jsonl`,
    # nunca reinventado): sampler PERIODICO em background (1 amostra/s,
    # `/proc/stat`+`/proc/meminfo`, nunca `docker stats` -- `steal` so
    # existe no nivel do host) durante a janela INTEIRA do bloco
    # cronometrado, nao so 2 instantaneos antes/depois do backend subir
    # (o que `_sample_cpu_mem` acima ja fazia, mantido intocado). steal%
    # e DELTA entre a primeira e a ultima amostra do arquivo JSONL
    # (cumulativo desde o boot, nunca uma razao desde sempre) -- mesma
    # formula exata de `_steal_pct_from_cpu_jsonl` da v8 real.
    #
    # Gate explicito: SO roda em modo campanha (`self.route_server is
    # not None`) -- nunca no piloto, por desenho (compatibilidade, item
    # 1 do pedido: o piloto nunca ganha chamadas SSH novas que ele nao
    # tinha antes). `start_block`/`stop_block` chamam isso condicionado
    # ao MESMO `if self.route_server is not None`.
    def _cpu_steal_sampler_start(self, host, label):
        home = "/home/ec2-user"
        out_path = f"{home}/{label}.cpu_mem.jsonl"
        pid_path = f"{home}/{label}.cpu_mem.pid"
        sampler_script = (
            "import time, json\n"
            "while True:\n"
            "    with open('/proc/stat') as f:\n"
            "        stat_line = f.readline().strip()\n"
            "    with open('/proc/meminfo') as f:\n"
            "        meminfo_raw = f.read()\n"
            "    print(json.dumps({'sampled_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),"
            " 'proc_stat_line': stat_line, 'proc_meminfo_raw': meminfo_raw}), flush=True)\n"
            "    time.sleep(1)\n"
        )
        inner = f"nohup python3 -c {json.dumps(sampler_script)} > {out_path} 2>&1 & echo $! > {pid_path}"
        cli.run_ssh(host, f"setsid sh -c {json.dumps(inner)}", key_path=self.key_path)
        return out_path, pid_path

    def _cpu_steal_sampler_stop_and_collect(self, host, out_path, pid_path, local_dir: Path) -> dict | None:
        cli.run_ssh(host, f"kill $(cat {pid_path}) 2>/dev/null; sleep 1; true", key_path=self.key_path)
        local_dir.mkdir(parents=True, exist_ok=True)
        local_path = local_dir / Path(out_path).name
        scp_proc = cli.run_scp(f"ec2-user@{host}:{out_path}", str(local_path), key_path=self.key_path)
        if scp_proc.returncode != 0:
            return None
        return _steal_pct_from_cpu_jsonl(local_path)

    def _launch_gateway(self, profile, keylog=False, route=None):
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
        # Decisao 69 (achado real, ao vivo, na retomada da Fase A real):
        # `--network insurance-server-lambdas_default` so existia de
        # verdade na validacao LOCAL -- num servidor EC2 real, antes da
        # Decisao 83, essa rede nunca existia (nada subia o backend
        # la), `docker run -d` falhava (rede nao encontrada). Decisao
        # 83 (pedido do Luciano): o backend de negocio AGORA roda de
        # verdade no servidor remoto tambem (`start_block`, via `docker
        # compose`) -- essa MESMA rede passa a existir de verdade la
        # tambem (compose a cria no primeiro `up`). O gateway entra
        # nela nos DOIS modos agora (pra resolver `auth`/`mockapi` por
        # alias Docker -- `business.go`'s AUTH_URI/API_GATEWAY_URI
        # default `http://auth:3000`/`http://mockapi:8080`), MAS, so
        # no caso remoto real, TAMBEM publica a porta no host
        # (`-p 443:443`) -- o cliente (`_server_gateway_ip`) sempre
        # disca o IP do HOST na porta 443, nunca um alias Docker (so o
        # gateway, nunca o cliente, precisa resolver os aliases).
        network_flags = (
            "--network insurance-server-lambdas_default "
            "--network-alias mtls --network-alias matls-auth.local --network-alias auth.local "
            "--network-alias matls-api.local --network-alias api.local --network-alias directory "
        )
        if not self.local_shim_bridge_join:
            network_flags += "-p 443:443 "
        cli.run_ssh(self._server_ip(route), f"docker rm -f {self.gateway_container} 2>/dev/null; true", key_path=self.key_path)
        run_proc = cli.run_ssh(self._server_ip(route),
                    f"docker run -d --name {self.gateway_container} "
                    f"{network_flags}"
                    f"-e HTTP_MODE=business -e TICKETS_DISABLED=true -e CRYPTO_PROFILE={profile} "
                    f"{keylog_flag}"
                    f"-v {real_certs_mount}:/real-certs:ro mockopin-v9-gateway",
                    key_path=self.key_path)
        if run_proc.returncode != 0:
            raise RuntimeError(
                f"_launch_gateway {profile}: 'docker run -d' falhou -- abortando ANTES de qualquer "
                f"verificacao/execucao (saida: {(run_proc.stdout + run_proc.stderr).strip()!r})"
            )
        # Espera o gateway de verdade terminar de subir (carregar os
        # certs, abrir :443) antes do proxy tentar discar -- achado ao
        # vivo (Decisao 49): sem isso, a primeira chamada do proxy
        # pode cair numa janela em que o container ja existe mas ainda
        # nao esta aceitando conexao, devolvendo 502 rio abaixo.
        wait_proc = cli.run_ssh(self._server_ip(route),
                    f"for i in $(seq 1 30); do "
                    f"docker logs {self.gateway_container} 2>&1 | grep -q 'listening on' && echo FOUND && break; "
                    f"sleep 1; done",
                    key_path=self.key_path)
        if "FOUND" not in (wait_proc.stdout or ""):
            status_proc = cli.run_ssh(self._server_ip(route), f"docker ps -a --filter name={self.gateway_container} --format '{{{{.Status}}}}'", key_path=self.key_path)
            raise RuntimeError(
                f"_launch_gateway {profile}: container {self.gateway_container} nunca logou 'listening on' em "
                f"30s -- abortando ANTES de qualquer verificacao/execucao (status: "
                f"{(status_proc.stdout or '').strip()!r})"
            )

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
        errado, sem esperar o resto do `start_block` pra descobrir.

        Decisao 65 (achado real, ao vivo, na propria execucao do
        piloto): v8 tinha o `mtls` como servico de docker-compose
        PERSISTENTE (nunca recriado por `switch_crypto_profile.py`),
        entao a porta 443 sempre estava de pe quando `preflight_tcp.py`
        rodava. Na v9, `_launch_gateway` faz `docker rm -f`+`docker run`
        a cada troca de perfil -- no PRIMEIRO bloco de qualquer rota
        (ou num exercicio isolado como `--exercise-start-stop`), o
        gateway AINDA NAO EXISTE quando este metodo roda (ele e o
        PRIMEIRO passo de `start_block`, de proposito). "Connection
        refused" (RST rapido) e um resultado DIFERENTE de um timeout
        real: RST prova que o pacote chegou ao kernel do servidor e
        foi rejeitado so porque nada escuta ainda na porta --
        exatamente o esperado antes do gateway subir, e uma prova
        POSITIVA de que o Security Group/VPC deixou o pacote passar.
        So um TIMEOUT de verdade (nenhuma resposta, pacote descartado
        em silencio) e evidencia real de SG/VPC errado -- so esse caso
        aborta agora."""
        if route in self._tcp_preflight_done:
            return
        gw_ip = self._server_gateway_ip(route)
        timeout = 5
        cmd = (
            f"timeout {timeout} bash -c 'echo > /dev/tcp/{gw_ip}/443' >/dev/null 2>&1; RC=$?; "
            f"if [ $RC -eq 0 ]; then echo OK; elif [ $RC -eq 124 ]; then echo TIMEOUT; else echo REFUSED; fi"
        )
        proc = cli.run_ssh(self._client_ip(route), cmd, key_path=self.key_path)
        outcome = (proc.stdout or "").strip()
        # OK (gateway ja escutando) ou REFUSED (caminho de rede
        # confirmado, so falta a app subir) sao os dois resultados
        # ESPERADOS antes do primeiro _launch_gateway -- so TIMEOUT
        # (SG/VPC bloqueando de verdade, sem resposta nenhuma) reprova.
        ok = outcome in ("OK", "REFUSED")
        self.tcp_preflight_results.append({"route": route, "gateway_ip": gw_ip, "ok": ok, "outcome": outcome,
                                            "output": (proc.stdout + proc.stderr).strip()})
        self._tcp_preflight_done.add(route)
        if not ok:
            raise RuntimeError(
                f"_tcp_preflight {route}: cliente nao alcancou {gw_ip}:443 por TCP puro (timeout, nenhuma "
                f"resposta) -- provavel Security Group/VPC errado, abortando ANTES de qualquer entrega de "
                f"imagem (saida: {(proc.stdout + proc.stderr).strip()!r})"
            )

    def start_block(self, profile, route):
        """Decisao 49: reusa o padrao real de `start_block_proxies`
        (v8) -- troca o perfil do GATEWAY e sobe proxy+signer
        DETACHED antes de qualquer execucao cronometrada do bloco.

        Decisao 83 (pedido do Luciano, apos a Decisao 82 -- a limitacao
        honesta que este docstring registrava antes, "isso NAO existe
        ainda, gap separado desta rodada", agora fechada): o backend de
        negocio da v8 (auth/mongo_seed/mockapi, + psql/localstack/
        mongodb como dependencias do proprio `docker compose`) e
        portado de verdade -- mesmo comando, mesmos Dockerfiles/fontes,
        rodando AGORA nos dois modos (antes, so `local_shim_bridge_
        join=True`): `auth` roda com seu PROPRIO CRYPTO_PROFILE (visto
        ao vivo: "Crypto profile: classic (signingAlgs: PS256)" no log
        dela), que determina o algoritmo de assinatura/JWKS que ela
        espera do token do cliente -- sem troca-la (+ mongo_seed/
        mockapi) junto com o gateway, um bloco hibrido-v8 contra uma
        `auth` ainda em "classic" devolve 401 em /token (achado ao
        vivo, Decisao 49). `cd` escolhido pela MESMA convencao ja usada
        pra `real_certs_mount` (Decisao 58): `$(pwd)/../../...` so faz
        sentido no shim local; `~/insurance-server-lambdas` (entregue
        por `deliver_source.py`, Decisao 83) e o caminho real remoto."""
        self._tcp_preflight(route)
        self._block_start_utc[(profile, route)] = datetime.now(timezone.utc)
        # Achado 10 (implementado, modo campanha so -- ver docstring de
        # `_cpu_steal_sampler_start`): comeca a amostrar ANTES de
        # qualquer coisa do bloco, pra cobrir a janela INTEIRA.
        #
        # Paridade com a v8 real (achado desta rodada, pedido do
        # Luciano: conferir antes de supor): `campaign_run.py` real
        # SEMPRE amostrou os DOIS lados -- `_cpu_mem_sampler_start_cmd
        # (label, "server")` E `_cpu_mem_sampler_start_cmd(label,
        # "client")`, chamados juntos em todo bloco (linhas 2016-2020
        # de v8/campaign/scripts/campaign_run.py). O porte inicial da
        # Decisao 107 so cobria o servidor -- lacuna de paridade,
        # nunca uma decisao deliberada de so medir 1 lado. Fechada
        # agora: amostra os 2 hosts, rotulo distinto por lado pra
        # nunca colidir ao coletar (mesmo arquivo remoto, hosts
        # diferentes -- sem risco real de colisao la, mas o rotulo
        # LOCAL de coleta precisaria do sufixo mesmo assim).
        if self.route_server is not None:
            label = f"{profile}_{route}".replace("/", "_")
            server_out, server_pid = self._cpu_steal_sampler_start(self._server_ip(route), f"{label}_server")
            client_out, client_pid = self._cpu_steal_sampler_start(self._client_ip(route), f"{label}_client")
            self._cpu_steal_sampler_paths[(profile, route)] = {
                "server": (self._server_ip(route), server_out, server_pid),
                "client": (self._client_ip(route), client_out, client_pid),
            }
        if not self.local_shim_bridge_join:
            # Decisao 83/87: as 3 imagens CUSTOM do backend (Decisao
            # 68, mesmo mecanismo de sempre) -- uma vez por fleet,
            # nunca por bloco (nunca trocam de CRYPTO_PROFILE em si).
            self._deliver_backend_images(route)
            self.cpu_mem_samples.append(
                {"label": "antes_do_backend", "profile": profile, "route": route,
                 **self._sample_cpu_mem(self._server_ip(route))})
        compose_dir = (
            '"$(pwd)/../../insurance-server-lambdas"' if self.local_shim_bridge_join
            else "~/insurance-server-lambdas"
        )
        backend_profile = BACKEND_CRYPTO_PROFILE_ENV[profile]
        backend_proc = cli.run_ssh(self._server_ip(route),
                    f'cd {compose_dir} && '
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
                    # fragil: mais simples e mais robusto.
                    f"for i in $(seq 1 45); do "
                    f"docker logs insurance-server-lambdas-mockapi-1 2>&1 | grep -q 'Startup completed' && break; "
                    f"sleep 1; done",
                    key_path=self.key_path, connect_timeout=90)
        if backend_proc.returncode != 0:
            raise RuntimeError(
                f"start_block {profile}/{route}: subir o backend de negocio (docker compose) falhou -- "
                f"abortando ANTES de qualquer verificacao/execucao (saida: "
                f"{(backend_proc.stdout + backend_proc.stderr).strip()!r})"
            )
        if not self.local_shim_bridge_join:
            self.cpu_mem_samples.append(
                {"label": "depois_do_backend", "profile": profile, "route": route,
                 **self._sample_cpu_mem(self._server_ip(route))})
        # Decisao 55, item 2: entrega por save/load, NUNCA build na
        # instancia -- ANTES de qualquer verificacao/execucao.
        self._deliver_image("gateway", self._server_ip(route))
        verification = self._verify_gateway_binary(profile, route)
        self._launch_gateway(profile, route=route)
        self._verify_running_gateway_binary(verification)
        if self.local_shim_bridge_join:
            cli.run_ssh(self._server_ip(route), f"docker network connect bridge {self.gateway_container}", key_path=self.key_path)
            ip_proc = cli.run_ssh(
                self._server_ip(route),
                f"docker inspect {self.gateway_container} --format '{{{{.NetworkSettings.Networks.bridge.IPAddress}}}}'",
                key_path=self.key_path,
            )
            bridge_ip = ip_proc.stdout.strip()
            if not bridge_ip:
                raise RuntimeError(f"start_block {profile}/{route}: nao consegui descobrir o IP de {self.gateway_container} na rede bridge")
            # Decisao 107 (generalizacao N-servidores): muta a entrada
            # CERTA do inventario (piloto: "server" unico, igual
            # sempre; campanha oficial: so o servidor desta `route`,
            # nunca os outros 2) -- nunca mais hardcoded "server".
            server_key = self._server_key(route)
            server_key["private_ip"] = bridge_ip
            server_key["public_ip"] = bridge_ip
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
        fixos (`tls_kem_proxy_run`/`pqc_signer_service_run`).

        Decisao 83 (pedido do Luciano, item 1: "inclua no stop"):
        tambem para (nunca remove -- `stop`, nunca `down`, pra NUNCA
        derrubar a rede `insurance-server-lambdas_default` que o
        gateway ja esta usando, Decisao 83 em `_launch_gateway`) o
        backend de negocio no SERVIDOR -- o proximo `start_block`
        (de qualquer perfil, inclusive o mesmo) sempre faz
        `--force-recreate` de novo, entao parar aqui so libera CPU/
        memoria entre blocos, nunca perde estado necessario."""
        remote_cmd = (f"docker stop {self.TLS_KEM_PROXY_CONTAINER} {self.PQC_SIGNER_CONTAINER} 2>/dev/null; "
                      f"docker rm -f {self.TLS_KEM_PROXY_CONTAINER} {self.PQC_SIGNER_CONTAINER} 2>/dev/null; true")
        cli.run_ssh(self._client_ip(route), remote_cmd, key_path=self.key_path)
        compose_dir = (
            '"$(pwd)/../../insurance-server-lambdas"' if self.local_shim_bridge_join
            else "~/insurance-server-lambdas"
        )
        cli.run_ssh(self._server_ip(route),
                    f"cd {compose_dir} && docker compose --profile main stop auth mongo_seed mockapi "
                    f"2>/dev/null; true",
                    key_path=self.key_path)
        # Achado 10 (implementado, modo campanha so): para os samplers
        # iniciados em `start_block` (servidor E cliente, paridade com
        # a v8 real -- ver comentario la), traz o JSONL de CADA lado,
        # calcula o steal% real (delta 1a->ultima amostra, cobre a
        # janela INTEIRA do bloco) -- nunca so um instantaneo antes/
        # depois, nunca so 1 dos 2 lados.
        if self.route_server is not None and (profile, route) in self._cpu_steal_sampler_paths:
            sides = self._cpu_steal_sampler_paths.pop((profile, route))
            local_dir = self.images_staging_dir.parent / "cpu_steal_samples"
            for host_role, (host, out_path, pid_path) in sides.items():
                steal_pct = self._cpu_steal_sampler_stop_and_collect(host, out_path, pid_path, local_dir)
                self.cpu_steal_samples.append({
                    "profile": profile, "route": route, "host_role": host_role, "host": host,
                    "steal_pct": steal_pct, "sampled_at_utc": datetime.now(timezone.utc).isoformat(),
                })
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
        log_text = self._gateway_logs(t0.isoformat(), t1.isoformat(), route)
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

        log_text = self._gateway_logs(t0.isoformat(), t1.isoformat(), route)
        raw_lines, parsed = self._connection_ok_lines(log_text)
        client_facing = [p for p in parsed if p["sni"] != _INTERNAL_CALLER_SNI]
        curve_id = client_facing[0]["curve"] if client_facing and client_facing[0]["curve"] else ec.EXPECTED_CURVE.get(profile)
        dual_auth = (client_facing[0]["dual"] == "true") if client_facing and client_facing[0]["dual"] else (profile == "hibrido-and")

        return {
            "insurance": result.get("calls", []), "person": [],
            "gateway_log_lines": raw_lines,
            "curveID": curve_id, "dualAuthenticated": dual_auth,
            # Pedido do Luciano (Etapa 1, item 4): carimbo por EXECUCAO
            # (nao so por chamada individual, que ja vem de
            # opin_flow.py dentro de result["calls"]) -- t0/t1 ja
            # calculados acima (delimitam a chamada SSH inteira), so
            # nunca devolvidos antes desta correcao.
            "start_utc": t0.isoformat(), "end_utc": t1.isoformat(),
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

    def _all_server_ips(self) -> list[str]:
        """Piloto (`route_server is None`): `[self._server_ip()]`,
        exatamente como sempre -- 1 elemento, caminho intocado.
        Campanha oficial: um IP por servidor distinto (ordem estavel,
        nunca duplicado, mesmo que varias rotas apontem pro mesmo
        servidor)."""
        if self.route_server is None:
            return [self._server_ip()]
        seen = []
        for server_id in dict.fromkeys(self.route_server.values()):  # ordem estavel, sem duplicata
            ip = self.inventory["servers"][server_id]["public_ip"]
            if ip not in seen:
                seen.append(ip)
        return seen

    def capture_ready_check(self):
        """Decisao 53, item 4c: fail-closed, chamado pelo smoke gate
        ANTES de qualquer execucao -- hoje, so o(s) servidor(es) rodam
        tcpdump/docker exec/tshark de verdade (ver `dedicated_capture`).
        Piloto: 1 servidor so, `_all_server_ips()` devolve exatamente
        `[self._server_ip()]` como sempre. Campanha oficial (pedido do
        Luciano, generalizacao pra N servidores): um host por servidor
        distinto -- os N precisam estar prontos, nunca so o primeiro.

        Decisao 81 (achado real, ao vivo, numa fleet nova): o probe
        (`preflight.run_capture_preflight`) so LE se `mockopin-v9-
        measure` ja existe no servidor -- nunca entrega. Numa fleet
        recem-provisionada, nada jamais entregou essa imagem antes
        deste ponto (`dedicated_capture` so a entrega lazily, e so
        roda DEPOIS da porta de fumaca passar) -- o preflight
        reprovava sempre, por falta de uma imagem que ele mesmo nunca
        tenta entregar. Corrigido: entrega aqui primeiro (mesmo
        `_deliver_image` idempotente que `dedicated_capture` ja usa --
        sha256 conferido nos dois saltos, nunca um `docker build`),
        so entao roda o probe -- agora pra CADA servidor."""
        hosts = self._all_server_ips()
        for host in hosts:
            self._deliver_image("measure", host)
        return preflight.run_capture_preflight(hosts, key_path=self.key_path)

    def _preserve_capture_attempt(self, server_ip, remote_pcap_path, remote_keylog_path, profile, route, attempt, capturas_dir: Path):
        """Pedido do Luciano (item 0, regra fail-closed nova + item 3,
        robustez de captura): traz o pcap+keylog BRUTOS desta
        tentativa (sucesso OU falha -- nunca so a que deu certo) pro
        `capturas_dir` LOCAL (no CONTROLE) -- sem isso, os dois ficam
        SO em `/tmp` no servidor, destruidos pelo teardown, nunca
        fazendo parte do que `collect_artifacts.py` verifica por
        sha256. A tentativa VENCEDORA (que `dedicated_capture` aceita
        como final) ganha o nome SEM sufixo de tentativa
        (`{profile}_{route}.pcap`/`.keylog`) alem da copia numerada --
        mesma convencao que `{profile}_{route}.log` (o bloco de texto
        extraido) ja usa."""
        retries_dir = capturas_dir / "capturas_brutas"
        retries_dir.mkdir(parents=True, exist_ok=True)
        local_pcap = retries_dir / f"{profile}_{route}_tentativa{attempt}.pcap"
        local_keylog = retries_dir / f"{profile}_{route}_tentativa{attempt}.keylog"
        pcap_proc = cli.run_scp(f"ec2-user@{server_ip}:{remote_pcap_path}", str(local_pcap), key_path=self.key_path)
        if pcap_proc.returncode != 0:
            raise RuntimeError(f"_preserve_capture_attempt {profile}/{route} tentativa {attempt}: scp do pcap falhou: {cli.redact(pcap_proc.stderr)}")
        keylog_proc = cli.run_scp(f"ec2-user@{server_ip}:{remote_keylog_path}", str(local_keylog), key_path=self.key_path)
        if keylog_proc.returncode != 0:
            raise RuntimeError(f"_preserve_capture_attempt {profile}/{route} tentativa {attempt}: scp do keylog falhou: {cli.redact(keylog_proc.stderr)}")

    MAX_CAPTURE_ATTEMPTS = 3

    def dedicated_capture(self, profile, route, capturas_dir=None):
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
        self._launch_gateway(profile, keylog=True, route=route)
        # `start_block` ja verificou o transporte e o container
        # anterior -- esta e so a MESMA imagem reiniciada (keylog=True
        # nunca muda o binario), mas confere de novo porque e um
        # container NOVO (reconfere o running_container_sha256, nunca
        # reconfere o transporte -- o binario local nao mudou).
        self._verify_running_gateway_binary(self.gateway_binary_verifications[-1])

        server_ip = self._server_ip(route)
        # Decisao 55, item 2: mockopin-v9-measure (tshark) tambem por
        # save/load -- nunca `docker build` na instancia.
        self._deliver_image("measure", server_ip)
        iface = self._primary_iface(server_ip)

        # Emenda robustez-de-captura (pedido do Luciano, item 3 da
        # rodada de correcao dos criterios 1/2/7, apos a Decisao 95
        # achar que L0 so decifra ClientHello/ServerHello nos 4
        # perfis, hipotese de timing nunca confirmada): nunca adivinha
        # a causa -- em vez disso, torna a captura ROBUSTA. Cada
        # tentativa usa pcap/keylog/log PROPRIOS (numerados), confere
        # decifragem IMEDIATA e COMPLETA (`ec.capture_decryption_
        # complete`, as 6 conexoes mTLS precisam ter o Certificate do
        # servidor decifrado) antes de aceitar -- SO retenta quando o
        # MODO DE FALHA e decifragem incompleta (nunca por divergencia
        # de tamanho, que e reportada como esta, nunca mascarada por
        # retry), ate `MAX_CAPTURE_ATTEMPTS` vezes. TODA tentativa
        # (sucesso ou falha) tem seu pcap/keylog preservados -- pedido
        # explicito do Luciano, nunca descartados silenciosamente.
        attempts_log = []
        lines = None
        t0 = t1 = None
        for attempt in range(1, self.MAX_CAPTURE_ATTEMPTS + 1):
            pcap_path = f"/tmp/criterio1_{profile}_{route}_tentativa{attempt}.pcap"
            keylog_path = f"/tmp/criterio1_keylog_{profile}_{route}_tentativa{attempt}.txt"
            tcpdump_log = f"/tmp/criterio1_tcpdump_{profile}_{route}_tentativa{attempt}.log"

            start_proc = cli.run_ssh(
                server_ip,
                f"sudo sh -c 'nohup tcpdump -i {iface} -s 0 -w {pcap_path} \"tcp port 443\" "
                f"> {tcpdump_log} 2>&1 & echo $!'",
                key_path=self.key_path,
            )
            tcpdump_pid = start_proc.stdout.strip().splitlines()[-1] if start_proc.stdout.strip() else ""
            if not tcpdump_pid.isdigit():
                raise RuntimeError(
                    f"dedicated_capture {profile}/{route} tentativa {attempt}: tcpdump nao iniciou "
                    f"(stdout={start_proc.stdout!r} stderr={start_proc.stderr!r})"
                )

            attempt_t0 = datetime.now(timezone.utc)
            try:
                gw_ip = self._server_gateway_ip(route)
                env = self._client_env(profile, gw_ip)
                remote_argv = f"campaign_client_runner.py --label criterio1_capture_{profile}_{route}_t{attempt}"
                remote_cmd = f"cd ~/thesis/scripts && {self._env_prefix(env)} python3 {remote_argv}"
                trigger = cli.run_ssh(self._client_ip(route), remote_cmd, key_path=self.key_path)
                if trigger.returncode != 0:
                    raise RuntimeError(f"dedicated_capture {profile}/{route} tentativa {attempt}: conexao de disparo falhou: {trigger.stderr}")
            finally:
                # sleep 1 antes do kill: da tempo da conexao de disparo
                # terminar de verdade antes de cortar a captura no
                # meio. sleep 2 (em vez de 1) DEPOIS do kill: tempo
                # extra pro keylog ser flushado em disco pelo processo
                # do gateway antes do `docker exec cat` seguinte --
                # hipotese registrada na Decisao 95 (L0, RTT quase
                # zero, pode nao dar tempo de sobra) -- nunca confirmada
                # sozinha, por isso tambem o RETRY (acima) se mesmo
                # assim a decifragem sair incompleta.
                cli.run_ssh(server_ip, f"sleep 1; sudo kill {tcpdump_pid} 2>/dev/null; sleep 2; true", key_path=self.key_path)
            attempt_t1 = datetime.now(timezone.utc)

            cli.run_ssh(server_ip, f"docker exec {self.gateway_container} cat /tmp/v9_keylog.txt > {keylog_path}", key_path=self.key_path)

            # Decisao 91 (Emenda -- bug de parsing do criterio 1, item b):
            # tres colunas extras (tcp.stream, tcp.srcport, tcp.len) em
            # relacao ao que esta funcao emitia antes -- `_message_sizes_
            # for_profile` (evaluate_criteria.py) agora classifica cada
            # mensagem por QUEM MANDOU (srcport), nunca mais por "esta na
            # mesma linha que ServerHello" (suposicao que a rede real
            # quebrou: o flight do servidor pode chegar fragmentado em mais
            # de uma linha/frame sob latencia real, nunca visto em
            # loopback). Desegmentacao de TCP/TLS ligada EXPLICITAMENTE
            # (ja e o default do tshark, mas o item b do Luciano pede
            # explicito) -- reagrupa fragmentos de UM registro TLS antes de
            # reportar o tipo/tamanho da mensagem, pra qualquer fragmentacao
            # no NIVEL DE REGISTRO (nao so a de reordenar linhas) tambem
            # ficar coberta. Filtro `tcp.len>0` (nao so `tls.handshake`):
            # precisa de TODO segmento TCP real, nao so os que carregam uma
            # mensagem de handshake completa, pra fechar a soma bruta de
            # bytes por direcao (item d) -- linhas sem tipo/tamanho de
            # handshake saem com essas duas colunas vazias, nunca omitidas.
            tshark_proc = cli.run_ssh(
                server_ip,
                f"docker run --rm -v {pcap_path}:{pcap_path}:ro -v {keylog_path}:{keylog_path}:ro "
                f"--entrypoint tshark mockopin-v9-measure "
                f'-r {pcap_path} -o "tls.keylog_file: {keylog_path}" '
                f'-o "tcp.desegment_tcp_streams: TRUE" -o "tls.desegment_ssl_records: TRUE" '
                f'-o "tls.desegment_ssl_application_data: TRUE" -Y "tcp.len>0" '
                f"-T fields -e frame.number -e tcp.stream -e tcp.srcport -e tcp.len "
                f"-e tls.handshake.type -e tls.handshake.length "
                f"-e tls.handshake.extensions_server_name -E aggregator=,",
                key_path=self.key_path,
            )
            # Decisao 91 (achado ao validar localmente contra o stack real,
            # item 4 do pedido do Luciano -- confirmar 4/4 perfis ANTES de
            # qualquer nova tentativa real): o carve-out interno de auth
            # (SNI "matls-api.local", Decisao 17/18/36 -- ja excluido da
            # contagem do criterio 4) atravessa a MESMA porta 443/interface
            # capturada aqui quando a execucao real de negocio o dispara --
            # confirmado ao vivo, localmente, contra o stack real (6 streams
            # sni="mtls" + 7 streams sni="matls-api.local" na MESMA
            # captura). SNI do ClientHello extraido pra `_message_sizes_
            # for_profile` poder excluir esses streams da analise das 6
            # conexoes client-facing, nunca conta-los como erro nem como
            # divergencia.
            attempt_lines = ["tamanho POR MENSAGEM (frame, stream, srcport, tcp.len, tipos, tamanhos, sni)"]
            n_handshake_rows = 0
            for raw_line in tshark_proc.stdout.strip().splitlines():
                # tshark `-T fields` omite os TABS finais quando os ultimos
                # campos estao vazios -- um pacote sem mensagem de
                # handshake (ACK puro ja excluido por `tcp.len>0`, mas
                # tambem um fragmento PARCIAL de um registro TLS reagrupado
                # num frame POSTERIOR, parte do mesmo achado da Decisao 90,
                # corrigido aqui pela Decisao 91) chega aqui com menos de 7
                # colunas -- preenche ate 7 em vez de descartar (descartar
                # subcontaria os bytes brutos do item d pra QUALQUER
                # captura real que fragmente no nivel de registro,
                # exatamente o cenario que esta Emenda existe pra cobrir).
                cols = raw_line.split("\t")
                if len(cols) < 7:
                    cols = cols + [""] * (7 - len(cols))
                if not cols[0] or not cols[1] or not cols[2] or not cols[3]:
                    continue
                attempt_lines.append("\t".join(cols[:7]))
                if cols[4] and cols[5]:
                    n_handshake_rows += 1

            # Pedido do Luciano (item 0, regra fail-closed nova):
            # preserva pcap+keylog DESTA tentativa, sucesso ou falha,
            # pro `capturas_dir` (local, no CONTROLE) -- nunca so no
            # servidor, onde seriam destruidos pelo teardown.
            if capturas_dir is not None:
                self._preserve_capture_attempt(server_ip, pcap_path, keylog_path, profile, route, attempt, Path(capturas_dir))

            decryption = {"complete": False, "note": "nenhuma linha de handshake extraida (pcap vazio ou keylog nao decifrou nada)"}
            if n_handshake_rows > 0:
                decryption = ec.capture_decryption_complete(attempt_lines)
            attempts_log.append({"attempt": attempt, "n_handshake_rows": n_handshake_rows, "decryption": decryption})

            if n_handshake_rows > 0 and decryption["complete"]:
                lines, t0, t1 = attempt_lines, attempt_t0, attempt_t1
                # `run_criterio7` (dedicated_criteria.py) procura o
                # pcap dedicado pelo nome SEM sufixo de tentativa
                # (`/tmp/criterio1_{profile}_{route}.pcap`) -- copia a
                # tentativa VENCEDORA pra esse nome no SERVIDOR, nunca
                # muda a busca do lado de quem consome.
                winner_pcap = f"/tmp/criterio1_{profile}_{route}.pcap"
                winner_keylog = f"/tmp/criterio1_keylog_{profile}_{route}.txt"
                cli.run_ssh(server_ip, f"cp {pcap_path} {winner_pcap} && cp {keylog_path} {winner_keylog}", key_path=self.key_path)
                if capturas_dir is not None:
                    cli.run_scp(f"ec2-user@{server_ip}:{winner_pcap}", str(Path(capturas_dir) / f"{profile}_{route}.pcap"), key_path=self.key_path)
                    cli.run_scp(f"ec2-user@{server_ip}:{winner_keylog}", str(Path(capturas_dir) / f"{profile}_{route}.keylog"), key_path=self.key_path)
                break
        else:
            raise RuntimeError(
                f"dedicated_capture {profile}/{route}: decifragem incompleta em "
                f"{self.MAX_CAPTURE_ATTEMPTS} tentativas (nunca uma divergencia de tamanho -- "
                f"essa e reportada, nunca re-tentada) -- {attempts_log}"
            )

        # Decisao 91, item (d): handshakeBytesIn/Out REAIS (log do
        # gateway, `countingConn`) pras 6 conexoes client-facing desta
        # execucao, na mesma ordem cronologica que o pcap -- unica fonte
        # independente capaz de confirmar que a soma bruta de bytes por
        # direcao (acima) fechou de verdade, nunca so reconferida contra
        # ela mesma.
        log_text = self._gateway_logs(t0.isoformat(), t1.isoformat(), route)
        gw_pairs = _handshake_bytes_all(log_text, profile)
        gw_lines = ["handshakeBytesIn/Out do gateway, por conexao client-facing (ordem cronologica)"]
        gw_lines.extend(f"{hs_in}\t{hs_out}" for hs_in, hs_out in gw_pairs)

        self.stop_block(profile, route)
        # Decisao 91: divisor "==..." explicito entre as duas secoes --
        # `_message_sizes_for_profile`/`_parse_gateway_handshake_bytes`
        # (evaluate_criteria.py) delimitam cada secao achando a PROXIMA
        # linha que comeca com "==" (ou o fim do texto); sem esse
        # divisor, a secao "tamanho POR MENSAGEM" engoliria as linhas
        # de handshakeBytesIn/Out tambem.
        return (f"== Perfil: {profile} ==\n" + "\n".join(lines) + "\n== secao seguinte ==\n"
                + "\n".join(gw_lines) + "\n== fim ==")


def _assert_profile_negotiated(profile, route, run, result):
    """Pedido do Luciano (Etapa 1, item 5): rede de seguranca ATIVA
    contra contaminacao de perfil entre blocos -- achado real da
    rodada de robustez local (backend ficou com `CRYPTO_PROFILE` de
    uma rodada anterior enquanto o gateway ja tinha sido recriado pro
    perfil novo; nunca reproduzido no caminho real `start_block`, que
    recria os dois juntos, mas o Luciano quer a verificacao ativa
    mesmo assim, nunca so confiar que o mecanismo de recriacao
    funcionou).

    Compara o que foi REALMENTE negociado (`curveID`/`dualAuthenticated`,
    extraidos do log real do gateway em `SSHExecutor`, ou do mock
    determinístico equivalente em `LocalExecutor`) contra o ESPERADO
    desta celula -- `evaluate_criteria.EXPECTED_CURVE` e o MESMO
    baseline que o avaliador real usa pra notar os criterios, nunca
    um numero reinventado aqui. Levanta com erro claro e contexto
    completo (perfil/rota/run/observado/esperado) no primeiro desvio.

    Limitacao honesta: cobre as duas dimensoes que ja chegam como
    dado estruturado neste ponto (grupo de troca de chaves do
    handshake, dual=true/false) -- NAO verifica algoritmo de
    assinatura nem a cadeia de certificados byte a byte (isso exigiria
    parsear o pcap/keylog de cada execucao, que so o criterio 1
    dedicado captura hoje, numa amostra, nao em toda execucao)."""
    expected_curve = ec.EXPECTED_CURVE.get(profile)
    expected_dual = (profile == "hibrido-and")
    observed_curve = result.get("curveID")
    observed_dual = result.get("dualAuthenticated")
    if observed_curve != expected_curve or observed_dual != expected_dual:
        raise RuntimeError(
            f"_assert_profile_negotiated: desvio de perfil detectado em profile={profile!r} "
            f"route={route!r} run={run!r} -- esperado curveID={expected_curve!r} "
            f"dualAuthenticated={expected_dual!r}, observado curveID={observed_curve!r} "
            f"dualAuthenticated={observed_dual!r}. Abortando ANTES de aceitar esta execucao -- "
            f"provavel contaminacao de estado entre blocos (backend/gateway nao recriados juntos). "
            f"Nunca segue coletando dado sob um perfil diferente do anunciado."
        )


def run_pilot(executor, seed: int, out_dir: Path, n_per_profile: int = N_PER_PROFILE, smoke: bool = False,
              routes: list[str] | None = None, profiles: list[str] | None = None,
              skip_dedicated_captures: bool = False, n_warmup_per_profile: int = 0,
              resume: bool = False, cost_tracker: "ct.CostTracker | None" = None) -> dict:
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

    `routes`/`profiles` (Decisao 49): reduzem/expandem a grade --
    usado historicamente so pra REDUZIR (validacao manual de UM
    bloco especifico, sempre com `skip_dedicated_captures=True`); o
    ensaio multi-regiao/campanha oficial (Decisao 107) e o primeiro
    caso que EXPANDE (8 rotas da campanha) com capturas dedicadas
    ligadas -- o laco de capturas abaixo honra `profiles`/`routes`
    de verdade, nunca os globais PROFILES/ROUTES do piloto.

    `skip_dedicated_captures`: as 12 capturas do criterio 1 sao uma
    responsabilidade SEPARADA (Decisao 41, produtores dedicados) --
    a porta de fumaca (Decisao 48) e a validacao manual de bloco
    (Decisao 49) pulam essa parte de proposito, pra nao confundir
    "12 execucoes de fumaca" com "12 capturas do criterio 1", dois
    "12" sem nenhuma relacao entre si.

    `n_warmup_per_profile` (Decisao do Luciano, protocolo de
    aquecimento full-flow, apos a revisao final item A): K execucoes
    REAIS e COMPLETAS (mesmo `run_execution`, nunca um handshake so --
    isso ja e o `readiness_probe` acima) por bloco, ANTES do laco
    contado, com marcador PROPRIO (`aquecimento_marker_inicio/fim`,
    NUNCA `execucao_marker_inicio/fim`) -- `evaluate_criteria.py` so
    reconhece o segundo marcador (`_execucao_window`), entao um
    aquecimento nunca e contado como execucao oficial so por existir
    no log. Gravado em arquivos SEPARADOS (`piloto_aquecimento.log`/
    `aquecimento_execucoes.json`, nunca misturado com `piloto_combined.
    log`/`piloto_calls.json`/`criterio6_execucoes.json`) -- preservado
    dentro do MESMO `out_dir` que `collect_artifacts.py` ja hasheia por
    completo (evidencia intacta, sha256 coberto por construcao, nunca
    um segundo sistema de verificacao paralelo). Default 0 -- piloto
    e qualquer chamador que nunca passe isto continuam byte a byte
    identicos a antes (nenhum arquivo novo escrito, loop nunca entra).

    `resume` (pedido do Luciano, Etapa 1 do piloto v9 -- retomada entre
    janelas completas): cada invocacao deste script cobre UMA janela
    inteira -- nada e escrito em `out_dir` ate o fim de todos os lacos
    (achado da rodada de robustez local). Sem checkpoint intra-janela
    por desenho (interromper no meio de uma janela sempre perde aquela
    janela -- aceito explicitamente pelo Luciano). `resume=True` so
    cobre a granularidade que ele PEDIU proteger: se `out_dir/
    manifest.json` ja existe e `total_execucoes == expected_total`
    (janela completa, persistida de verdade, nunca so parcial -- um
    manifesto so e escrito no fim), devolve ele de novo SEM reexecutar
    nada (nunca duplica, nunca mistura estado). Se o manifesto existir
    mas DIVERGIR (outra config, `n_per_profile` diferente, etc.),
    fail-closed -- nunca sobrescreve silenciosamente uma janela
    anterior que pode nao ser a mesma. Default False -- qualquer
    chamador que nunca passe isto continua byte a byte identico a
    antes (sempre reexecuta, como sempre fez)."""
    routes = routes if routes is not None else ROUTES
    profiles = profiles if profiles is not None else PROFILES
    expected_total = len(profiles) * len(routes) * n_per_profile
    manifest_path = out_dir / "manifest.json"
    if resume and manifest_path.is_file():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("smoke"):
            raise RuntimeError(
                f"run_pilot(resume=True): {manifest_path} e de uma porta de fumaca (smoke=true), "
                f"nunca uma janela oficial -- nao pode ser usado como retomada."
            )
        if existing.get("total_execucoes") == expected_total and existing.get("expected_total") == expected_total:
            return existing
        raise RuntimeError(
            f"run_pilot(resume=True): {manifest_path} ja existe mas nao bate com esta chamada "
            f"(total_execucoes={existing.get('total_execucoes')!r}, esperado={expected_total!r}) -- "
            f"provavelmente uma janela parcial de uma config diferente ou interrompida antes do fim. "
            f"Nunca sobrescrito automaticamente: mova/renomeie {out_dir} antes de repetir, ou confirme "
            f"que a config (n_per_profile/profiles/routes) e a mesma pretendida."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    capturas_dir = out_dir / "criterio1_capturas"
    capturas_dir.mkdir(parents=True, exist_ok=True)

    # Pedido do Luciano (Etapa 1, item 4): carimbo da JANELA inteira
    # (esta invocacao de run_pilot), distinto do carimbo por execucao
    # (abaixo) e por chamada (ja dentro de cada "insurance"/"person").
    window_start_utc = datetime.now(timezone.utc).isoformat()
    rng = random.Random(seed)
    combined_log_lines = []
    execucoes_calls = []
    criterio6_rows = []
    route_orders = {}
    aquecimento_log_lines = []
    aquecimento_calls = []
    # Pedido do Luciano (Etapa 1, item 2 -- trava local de custo):
    # `cost_stop_info` vira nao-None no primeiro `status()=="stop"`,
    # e e checado no topo de cada nivel de laco pra abortar JANELA
    # inteira (nunca so a celula atual) de forma limpa -- a execucao
    # EM ANDAMENTO sempre termina antes do cheque (o cheque roda
    # DEPOIS de `executor.run_execution` ja ter retornado), os dados
    # ja coletados seguem pro mesmo `execucoes_calls`/arquivos de
    # sempre (escritos mais abaixo, sem mudanca), e `stop_block` do
    # bloco atual e chamado antes de sair (libera CPU/memoria local).
    # NUNCA desmonta a frota real (EC2/Terraform) -- isso e
    # responsabilidade de quem chama (`cleanup.py`), mesmo padrao
    # ja estabelecido pela porta de fumaca ("nunca destroi por conta
    # propria, so reporta e sai com erro").
    cost_stop_info = None
    _cost_alert_logged = False

    for route in routes:
        if cost_stop_info is not None:
            break
        order = profile_block_order(route, rng, profiles=profiles)
        route_orders[route] = order
        for profile in order:
            if cost_stop_info is not None:
                break
            combined_log_lines.append(f"== Perfil: {profile} ==")
            executor.start_block(profile, route)
            combined_log_lines.append(executor.readiness_probe(profile, route))
            for warmup in range(1, n_warmup_per_profile + 1):
                aquecimento_log_lines.append(aquecimento_marker_inicio(profile, route, warmup))
                warmup_result = executor.run_execution(profile, route, run=f"aquecimento{warmup}")
                _assert_profile_negotiated(profile, route, f"aquecimento{warmup}", warmup_result)
                aquecimento_log_lines.extend(warmup_result["gateway_log_lines"])
                aquecimento_log_lines.append(aquecimento_marker_fim(profile, route, warmup))
                aquecimento_calls.append({
                    "profile": profile, "route": route, "warmup": warmup,
                    "insurance": warmup_result["insurance"], "person": warmup_result["person"],
                    "start_utc": warmup_result.get("start_utc"), "end_utc": warmup_result.get("end_utc"),
                })
            for run in range(1, n_per_profile + 1):
                combined_log_lines.append(execucao_marker_inicio(profile, route, run))
                result = executor.run_execution(profile, route, run)
                # Pedido do Luciano (Etapa 1, item 5 -- achado critico da
                # rodada de robustez: contaminacao de perfil entre blocos,
                # backend com CRYPTO_PROFILE antigo enquanto o gateway ja
                # tinha trocado). Verifica o perfil REALMENTE negociado
                # (grupo de troca de chaves do handshake + dual=true/false)
                # contra o ESPERADO desta celula -- antes de aceitar a
                # execucao como valida. Aborta e reporta no primeiro
                # desvio, nunca segue coletando dado contaminado.
                _assert_profile_negotiated(profile, route, run, result)
                combined_log_lines.extend(result["gateway_log_lines"])
                combined_log_lines.append(execucao_marker_fim(profile, route, run))
                execucoes_calls.append({
                    "profile": profile, "route": route, "run": run,
                    "insurance": result["insurance"], "person": result["person"],
                    "start_utc": result.get("start_utc"), "end_utc": result.get("end_utc"),
                })
                criterio6_rows.append({
                    "profile": profile, "route": route, "run": run,
                    "curveID": result["curveID"], "dualAuthenticated": result["dualAuthenticated"],
                    "keylog_evidence": True,
                })
                if cost_tracker is not None:
                    breakdown = cost_tracker.breakdown_usd()
                    ct.write_cost_log_entry(out_dir, "check", breakdown)
                    cost_status = cost_tracker.status()
                    if cost_status == "alert" and not _cost_alert_logged:
                        _cost_alert_logged = True
                        msg = (f"*** ALERTA DE CUSTO: estimativa US${breakdown['total_usd']:.2f} "
                               f">= alerta US${cost_tracker.alert_usd:.2f} ***")
                        combined_log_lines.append(msg)
                        print(msg, file=sys.stderr)
                    elif cost_status == "stop":
                        msg = (f"*** PARADA POR CUSTO: estimativa US${breakdown['total_usd']:.2f} "
                               f">= limite US${cost_tracker.stop_usd:.2f} -- interrompendo apos esta "
                               f"execucao (profile={profile} route={route} run={run}) ***")
                        combined_log_lines.append(msg)
                        print(msg, file=sys.stderr)
                        cost_stop_info = {
                            "triggered_at_utc": datetime.now(timezone.utc).isoformat(),
                            "profile": profile, "route": route, "run": run, **breakdown,
                        }
                        ct.write_cost_log_entry(out_dir, "stop_triggered", breakdown)
                        break
            executor.stop_block(profile, route)

    # Achado real (encontrado agora, pedido do Luciano: desenho do
    # ensaio multi-regiao reduzido): este laco usava PROFILES/ROUTES
    # (os globais do piloto, 4x3) HARDCODED, nunca `profiles`/`routes`
    # (os parametros da propria funcao, 1 linha acima) -- inofensivo
    # ate agora porque `routes`/`profiles` so eram usados (Decisao 49)
    # pra REDUZIR a grade de validacao manual, sempre JUNTO com
    # `skip_dedicated_captures=True` (nunca exercitava este laco). A
    # campanha/ensaio oficial e o PRIMEIRO caso que passa uma grade
    # customizada (8 rotas) E quer capturas dedicadas ao mesmo tempo
    # -- sem este fix, as capturas do criterio 1 ficariam presas as 3
    # rotas do piloto, nunca cobrindo as 5 rotas novas da campanha.
    if not skip_dedicated_captures:
        for profile in profiles:
            for route in routes:
                block = executor.dedicated_capture(profile, route, capturas_dir=capturas_dir)
                (capturas_dir / f"{profile}_{route}.log").write_text(block, encoding="utf-8")

    combined_log_path = out_dir / "piloto_combined.log"
    combined_log_path.write_text("\n".join(combined_log_lines) + "\n", encoding="utf-8")

    calls_path = out_dir / "piloto_calls.json"
    calls_path.write_text(json.dumps(execucoes_calls, indent=2, ensure_ascii=False), encoding="utf-8")

    criterio6_path = out_dir / "criterio6_execucoes.json"
    criterio6_path.write_text(json.dumps(criterio6_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    # Protocolo de aquecimento (ver docstring acima): arquivos SEMPRE
    # criados quando n_warmup_per_profile>0, nunca quando e 0 (sem
    # arquivo novo no caso default -- out_dir fica identico a antes).
    aquecimento_log_path = aquecimento_calls_path = None
    if n_warmup_per_profile > 0:
        aquecimento_log_path = out_dir / "piloto_aquecimento.log"
        aquecimento_log_path.write_text("\n".join(aquecimento_log_lines) + "\n", encoding="utf-8")
        aquecimento_calls_path = out_dir / "aquecimento_execucoes.json"
        aquecimento_calls_path.write_text(json.dumps(aquecimento_calls, indent=2, ensure_ascii=False), encoding="utf-8")

    expected_total = len(profiles) * len(routes) * n_per_profile
    manifest = {
        "seed": seed, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        # Pedido do Luciano (Etapa 1, item 4): carimbo da JANELA
        # inteira -- `window_start_utc` capturado antes do primeiro
        # bloco, `window_end_utc` aqui, depois do ultimo (e das
        # capturas dedicadas, se houver).
        "window_start_utc": window_start_utc, "window_end_utc": datetime.now(timezone.utc).isoformat(),
        "smoke": smoke, "n_per_profile": n_per_profile,
        "route_orders": route_orders,
        "total_execucoes": len(execucoes_calls), "expected_total": expected_total,
        "total_capturas": len(profiles) * len(routes),
        "combined_log": str(combined_log_path), "calls_json": str(calls_path),
        "criterio6_json": str(criterio6_path), "capturas_dir": str(capturas_dir),
        # Informativo SO -- nunca somado a total_execucoes/expected_total
        # acima (Decisao do Luciano: aquecimento nunca conta pro total
        # oficial, so preservado como evidencia).
        "n_warmup_per_profile": n_warmup_per_profile,
        "total_aquecimentos": len(aquecimento_calls),
        "aquecimento_log": str(aquecimento_log_path) if aquecimento_log_path else None,
        "aquecimento_calls_json": str(aquecimento_calls_path) if aquecimento_calls_path else None,
        # Decisao 54, item 1: verificacao scp+sha256sum -c do binario
        # do gateway, uma entrada por bloco (start_block) -- lista
        # vazia pro LocalExecutor (nunca tem binario real pra
        # verificar).
        "gateway_binary_verifications": getattr(executor, "gateway_binary_verifications", []),
        # Decisao 83, item 1: amostras de CPU/memoria do servidor
        # (antes/depois de cada subida do backend) -- comparar com o
        # que a v8 ja mediu. Lista vazia pro LocalExecutor.
        "cpu_mem_samples": getattr(executor, "cpu_mem_samples", []),
        # Pedido do Luciano (Etapa 1, item 2): None se a trava de custo
        # nunca disparou (ou nunca esteve ligada) -- dict com o
        # detalhamento completo (profile/route/run + breakdown_usd) no
        # momento exato da parada, caso contrario. A janela pode ter
        # terminado com MENOS execucoes que `expected_total` por causa
        # disso -- confira este campo antes de assumir falha.
        "cost_stop": cost_stop_info,
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


def _handshake_bytes_all(log_text: str, profile: str) -> list[tuple[int, int]]:
    """Decisao 91, item (d): TODAS as linhas 'connection OK' CLIENT-
    FACING (sni="mtls", mesmo filtro que `_bytes_diagnostic_for_profile`
    ja usa pra excluir o carve-out interno matls-api.local/Decisao 18/
    19) deste perfil, na ordem cronologica em que o gateway logou --
    `dedicated_capture` usa a MESMA ordem em que o pcap viu as conexoes
    (ambos crescem no tempo), entao o N-esimo par aqui corresponde ao
    N-esimo tcp.stream do pcap. Reusa o padrao de `_bytes_diagnostic_
    for_profile` (nunca reinventado), so com `finditer` em vez de
    `search` -- aquela funcao so pegava a PRIMEIRA conexao (suficiente
    pro diagnostico da Decisao 55); esta precisa de todas (6, pelo
    N_mTLS documentado em opin_flow.py)."""
    pattern = _BYTES_DIAGNOSTIC_LOG_RE_TEMPLATE.format(profile=_re.escape(profile))
    return [(int(m.group(1)), int(m.group(2))) for m in _re.finditer(pattern, log_text)]


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
    bytes_diagnostic_rows = []
    for profile in PROFILES:
        try:
            row = _bytes_diagnostic_for_profile(combined_log_text, profile, certs_dir)
        except Exception as e:  # noqa: BLE001 -- Decisao 75, item 2: diagnostico e so isso, um
            # DIAGNOSTICO -- qualquer excecao (ex: certs_dir ausente no
            # controle) nunca pode derrubar o smoke gate inteiro; so
            # marca esta linha como needs_decision, igual a um desvio
            # != 0 detectado normalmente (Decisao 55/48).
            row = {"profile": profile, "ok": False, "note": f"{type(e).__name__}: {e}"}
        bytes_diagnostic_rows.append(row)
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
    # Pedido do Luciano (achado real ao preparar o ensaio/campanha de
    # verdade: a CLI nunca tinha sido wireada pra campanha -- so
    # chamada em processo, nunca via `--mode ssh` do controle real,
    # que e como o PILOT_RUNBOOK.md de fato invoca este script).
    # Sem a flag, comportamento INALTERADO (route_server=None,
    # routes/profiles=None -- os defaults do piloto, 3 rotas).
    ap.add_argument("--campaign", action="store_true",
                     help="usa a topologia de 3 servidores/8 rotas de campaign_topology.py "
                          "(route_server/routes) em vez do piloto de 1 servidor/3 rotas")
    ap.add_argument("--n-per-profile", type=int, default=None,
                     help="N execucoes por celula perfil x rota -- com --campaign, obrigatorio "
                          "(depende da escala real: ensaio N=1/janela, oficial N=30); sem --campaign, "
                          f"default do piloto ({N_PER_PROFILE})")
    ap.add_argument("--n-warmup-per-profile", type=int, default=0,
                     help="Decisao 108 item 1: N aquecimentos full-flow por celula ANTES das "
                          "execucoes contadas (default 0 -- nenhum aquecimento, comportamento de sempre)")
    ap.add_argument("--resume", action="store_true",
                     help="Pedido do Luciano (Etapa 1 do piloto v9): se --out ja tem um manifest.json "
                          "de uma janela COMPLETA e identica (mesmo total esperado), devolve ele de novo "
                          "sem reexecutar -- nunca duplica, nunca mistura estado. Fail-closed se o "
                          "manifesto existir mas nao bater com esta chamada. Default False (reexecuta "
                          "sempre, comportamento de sempre).")
    # Pedido do Luciano (Etapa 1, item 2): trava local de custo -- so
    # tem sentido no modo ssh (custo real de AWS); --mode simulate
    # nunca liga nada disso (sem --no-cost-tracking nem nada, o modo
    # simulate so ignora -- ver construcao do CostTracker abaixo).
    ap.add_argument("--cost-alert-usd", type=float, default=ct.DEFAULT_PILOT_ALERT_USD,
                     help=f"Limiar de ALERTA em USD (default do piloto: {ct.DEFAULT_PILOT_ALERT_USD}). "
                          "A campanha oficial deve passar o seu proprio limite.")
    ap.add_argument("--cost-stop-usd", type=float, default=ct.DEFAULT_PILOT_STOP_USD,
                     help=f"Limiar de PARADA em USD (default do piloto: {ct.DEFAULT_PILOT_STOP_USD}). "
                          "A campanha oficial deve passar o seu proprio limite.")
    ap.add_argument("--cost-control-instance-type", default="t4g.micro",
                     help="Tipo real da instancia de controle (mesmo default do Terraform, t4g.micro)")
    ap.add_argument("--cost-server-client-instance-type", default=None,
                     help="Tipo real das instancias de servidor/cliente -- OBRIGATORIO no modo ssh "
                          "(sem default de proposito, mesma politica do Terraform: falha alto se "
                          "ninguem passar o valor explicito, nunca assume).")
    ap.add_argument("--no-cost-tracking", action="store_true",
                     help="Desliga a trava de custo mesmo no modo ssh (ex.: ensaio curto ja sob "
                          "supervisao manual constante). Default False -- a trava fica ligada por "
                          "padrao em qualquer execucao real contra a AWS.")
    args = ap.parse_args()

    campaign_routes = campaign_profiles = route_server = None
    if args.campaign:
        _scripts_dir = str(Path(__file__).resolve().parent)
        if _scripts_dir not in sys.path:
            sys.path.insert(0, _scripts_dir)
        import campaign_topology
        campaign_routes = list(campaign_topology.CAMPAIGN_ROUTES)
        campaign_profiles = list(PROFILES)
        route_server = dict(campaign_topology.CAMPAIGN_ROUTE_SERVER)
        if args.n_per_profile is None:
            ap.error("--campaign exige --n-per-profile (depende da escala real, nunca assumido)")

    cost_tracker_instance = None
    if args.mode == "simulate":
        executor = LocalExecutor()
    else:
        if not args.inventory_json:
            ap.error("--mode ssh exige --inventory-json")
        inventory = json.load(open(args.inventory_json, encoding="utf-8"))
        executor = SSHExecutor(inventory, key_path=args.ssh_key, images_staging_dir=args.images_staging_dir,
                                route_server=route_server)
        if not args.no_cost_tracking:
            if not args.cost_server_client_instance_type:
                ap.error("--mode ssh exige --cost-server-client-instance-type (sem default de "
                         "proposito, mesma politica do Terraform) -- ou passe --no-cost-tracking "
                         "explicitamente pra desligar a trava de custo.")
            instance_types = {"control": args.cost_control_instance_type}
            if "servers" in inventory:
                for server_id in inventory["servers"]:
                    instance_types[f"server:{server_id}"] = args.cost_server_client_instance_type
            elif "server" in inventory:
                instance_types["server"] = args.cost_server_client_instance_type
            for client_id in inventory.get("clients", {}):
                instance_types[f"client:{client_id}"] = args.cost_server_client_instance_type
            cost_tracker_instance = ct.CostTracker(
                instance_types=instance_types, n_public_ips=len(instance_types),
                alert_usd=args.cost_alert_usd, stop_usd=args.cost_stop_usd,
            )

    if args.exercise_start_stop:
        report = exercise_start_stop(executor, args.exercise_profile, args.exercise_route)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    if not args.out:
        ap.error("--out e obrigatorio fora do modo --exercise-start-stop")

    n_per_profile = args.n_per_profile if args.n_per_profile is not None else N_PER_PROFILE
    if args.smoke:
        manifest = run_smoke_gate(executor, args.seed, Path(args.out))
    else:
        manifest = run_pilot(executor, args.seed, Path(args.out), n_per_profile=n_per_profile,
                              routes=campaign_routes, profiles=campaign_profiles,
                              n_warmup_per_profile=args.n_warmup_per_profile, resume=args.resume,
                              cost_tracker=cost_tracker_instance)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if manifest.get("cost_stop"):
        # Mesmo padrao da porta de fumaca: NUNCA destroi por conta
        # propria -- a execucao em andamento ja terminou, os dados ja
        # coletados ja estao salvos (ver run_pilot), o bloco atual ja
        # foi parado (stop_block) -- falta so a decisao do Luciano
        # sobre desmontar a frota real (cleanup.py) ou ajustar o
        # limite e continuar numa nova janela.
        print("\n*** PARADA POR CUSTO -- PAUSADO. ***", file=sys.stderr)
        print(f"Estimativa no momento da parada: US${manifest['cost_stop']['total_usd']:.2f} "
              f"(limite: US${args.cost_stop_usd:.2f}).", file=sys.stderr)
        print("Dados ja coletados estao salvos nesta janela. Nenhum destroy automatico. Decisao do Luciano:", file=sys.stderr)
        print("  (a) confirmar o custo real (console/Cost Explorer) e mandar desmontar a frota (cleanup.py), ou", file=sys.stderr)
        print("  (b) ajustar o limite e continuar numa nova janela, se o custo real ainda permitir.", file=sys.stderr)
        sys.exit(1)
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

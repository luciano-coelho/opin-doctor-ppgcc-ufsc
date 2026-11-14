"""Negative/positive tests for the AS's hybrid AND-gate client auth
(mock-service-os/mock_as/utils/opin/clientHybridAuth.js) -- Decisao 115
(thesis/results/v9/DECISIONS.md): the AS's /token endpoint must reject a
client_assertion whose payload-extension pqc claim is either
present-but-invalid OR absent entirely, and must accept one whose pqc
claim verifies. Runs against the REAL local stack, CRYPTO_PROFILE=hybrid
-- the same backend config serves both Hibrido dual=false (control) and
Hibrido dual=true (AND); clientHybridAuth.js has no signal to tell them
apart and Decisao 115 deliberately didn't add one, so this one test run
covers both profiles' application-layer behavior identically. The
distinct TLS-layer behavior between the two profiles is covered
elsewhere (toolchain/patches/and.patch's own tests), never by this file.

Invoke as:
  CRYPTO_PROFILE=hybrid python -m pytest tests/test_hybrid_and_gate.py
"""
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import conftest
import opin_flow as of
import pytest
import requests

PROFILE = os.environ.get("CRYPTO_PROFILE", "classic")

# Decisao 164 (item 1b, pedido do Luciano apos a reauditoria da tag v6):
# o ramo legado de opin_flow.start_tls_kem_proxy() (usado quando
# V9_HARNESS nao esta setado) nao sustenta handshake sob CRYPTO_PROFILE=
# hybrid contra mock_mtls (confirmado ao vivo: "remote error: tls:
# handshake failure", 30s de timeout) -- mock_mtls nao fala o grupo TLS
# que o perfil hybrid negocia. V9_HARNESS=1 TAMBEM falhava como estava,
# mas por um motivo DIFERENTE e corrigivel: relay.go fixa ServerName=
# "mtls" (correto -- os certificados REAIS do gateway v9 tem "mtls" no
# SAN), mas quem respondia por "mtls" na rede do compose ainda era o
# mock_mtls, cujo certificado e valido pra auth.local/api.local/
# directory/etc, nunca "mtls" -- um erro puro de identidade na rede, nao
# do proxy. Corrigido NAO alterando o proxy, mas subindo o gateway v9
# REAL (business mode) nos MESMOS aliases que `thesis/results/v9/
# campaign/local_validation_criterio1_v2/capture_one_profile.sh` ja usa
# pra este exato proposito -- confirmado ao vivo (POST /token real,
# assertion valida, 200 com access_token) antes de escrever este codigo.
# `business.go`'s businessMux encaminha pra AUTH_URI=http://auth:3000
# (o servico REAL `auth` do compose, onde clientHybridAuth.js de fato
# mora) -- nunca por "mtls", entao o resto do roteamento funciona sem
# mudanca nenhuma.
_V9_GATEWAY_CONTAINER = "v9-mtls-hybrid-and-gate-test"
_V9_GATEWAY_ALIASES = ("mtls", "matls-auth.local", "auth.local", "matls-api.local", "api.local", "directory")
_COMPOSE_NETWORK = "insurance-server-lambdas_default"
_REAL_CERTS_DIR = str(Path(__file__).resolve().parents[3] / "mock-service-os" / "certs")


def _mock_mtls_was_running() -> bool:
    import subprocess
    r = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True)
    return "insurance-server-lambdas-mtls-1" in r.stdout


def _docker_compose_mtls(action: str) -> None:
    import subprocess
    env = dict(os.environ, COMPOSE_PROFILES="main,dev,cs,build-only")
    compose_dir = Path(__file__).resolve().parents[3] / "insurance-server-lambdas"
    subprocess.run(["docker", "compose", action, "mtls"], cwd=str(compose_dir), env=env, capture_output=True)


def _auth_container_crypto_profile() -> str:
    """Decisao 164: o CRYPTO_PROFILE do `auth` real (mock_as) e um env
    var PROPRIO do container, INDEPENDENTE do CRYPTO_PROFILE que o
    gateway v9 usa -- confirmado ao vivo (achado real desta rodada): o
    AND-gate de clientHybridAuth.js so ativa se o PROPRIO `auth` estiver
    rodando sob hybrid/hibrido-and; sem isso, `isHybridProfile` nunca
    verdadeiro e QUALQUER assertion e aceita, mascarando os 2 testes
    negativos como falsos-PASS (achado ao vivo: 200 onde devia dar 400).
    O proprio docker-compose.yml ja documenta a recriacao exigida
    (linha do CRYPTO_PROFILE do servico auth): "CRYPTO_PROFILE=pqc
    docker-compose --profile main up -d --force-recreate auth mtls
    mongo_seed mockapi" -- reaproveitado aqui, so sem o `mtls` (que este
    fixture ja superseding com o gateway v9 real)."""
    import subprocess
    r = subprocess.run(["docker", "exec", "insurance-server-lambdas-auth-1", "printenv", "CRYPTO_PROFILE"],
                        capture_output=True, text=True)
    return r.stdout.strip() or "classic"


def _recreate_auth_backend(crypto_profile: str) -> None:
    import subprocess
    env = dict(os.environ, COMPOSE_PROFILES="main,dev,cs,build-only", CRYPTO_PROFILE=crypto_profile)
    compose_dir = Path(__file__).resolve().parents[3] / "insurance-server-lambdas"
    r = subprocess.run(
        ["docker", "compose", "up", "-d", "--force-recreate", "auth", "mongo_seed", "mockapi"],
        cwd=str(compose_dir), env=env, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"falha ao recriar auth/mongo_seed/mockapi sob CRYPTO_PROFILE={crypto_profile}: {r.stderr}")
    import time
    time.sleep(3)  # tempo pro oidc-provider/express subirem antes da primeira chamada real


def _start_real_v9_gateway():
    """Sobe o gateway v9 REAL (business mode, perfil hibrido-v8 --
    V9_PROFILE_NAME["hybrid"] em opin_flow.py), superseding os aliases
    de rede "mtls"/"matls-auth.local"/etc que mock_mtls normalmente
    ocupa. Espera "listening on" no log antes de devolver -- mesma
    convencao de polling que opin_flow.py's proprio _wait_for_tls_kem_
    proxy_ready usa pra outros containers."""
    import subprocess
    import time
    subprocess.run(["docker", "rm", "-f", _V9_GATEWAY_CONTAINER], capture_output=True)
    argv = ["docker", "run", "-d", "--name", _V9_GATEWAY_CONTAINER, "--network", _COMPOSE_NETWORK]
    for alias in _V9_GATEWAY_ALIASES:
        argv += ["--network-alias", alias]
    argv += [
        "-e", "HTTP_MODE=business", "-e", "TICKETS_DISABLED=true", "-e", "CRYPTO_PROFILE=hibrido-v8",
        "-v", f"{_REAL_CERTS_DIR}:/real-certs:ro", "mockopin-v9-gateway",
    ]
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"falha ao subir o gateway v9 real: {r.stderr}")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        logs = subprocess.run(["docker", "logs", _V9_GATEWAY_CONTAINER], capture_output=True, text=True)
        if "listening on" in (logs.stdout + logs.stderr):
            return
        time.sleep(0.5)
    raise RuntimeError("gateway v9 real nao respondeu 'listening on' em 30s")


def _stop_real_v9_gateway():
    import subprocess
    subprocess.run(["docker", "rm", "-f", _V9_GATEWAY_CONTAINER], capture_output=True)


@pytest.fixture(scope="module")
def stack():
    if PROFILE not in ("hybrid", "hibrido-and"):
        pytest.skip("the payload-extension AND-gate only exists in the two hybrid profiles -- "
                     "classic/pqc never load clientHybridAuth.js (express.js's isHybridProfile gate)")
    conftest.skip_if_stack_not_up()

    mock_mtls_running = _mock_mtls_was_running()
    original_auth_profile = _auth_container_crypto_profile()
    if mock_mtls_running:
        _docker_compose_mtls("stop")
    import importlib
    os.environ["V9_HARNESS"] = "1"
    importlib.reload(of)
    try:
        # Decisao 164: o PROPRIO `auth` real precisa estar sob hybrid/
        # hibrido-and pro AND-gate (clientHybridAuth.js) de fato ativar
        # -- e um env var independente do que o gateway v9 usa (achado
        # ao vivo, ver _auth_container_crypto_profile() acima).
        _recreate_auth_backend(PROFILE)
        _start_real_v9_gateway()
        proc = of.start_tls_kem_proxy(PROFILE)
        signer_started = of.start_pqc_signer_service(PROFILE)
        try:
            session = requests.Session()
            cert = of.get_local_leg_cert_paths(PROFILE)
            signing_key, kid, alg = of.load_client_signing_key(PROFILE)
            yield session, cert, signing_key, kid, alg
        finally:
            of.stop_pqc_signer_service(signer_started)
            of.stop_tls_kem_proxy(proc)
    finally:
        _stop_real_v9_gateway()
        os.environ.pop("V9_HARNESS", None)
        importlib.reload(of)
        if mock_mtls_running:
            _docker_compose_mtls("start")
        _recreate_auth_backend(original_auth_profile)


@pytest.fixture(scope="module")
def any_profile_stack():
    """Same as `stack`, minus the hybrid-only skip -- used only by
    test_classic_and_pqc_unaffected, which needs to run precisely for the
    two profiles `stack` skips.

    Decisao 164 (item 3) -- TENTADO E REVERTIDO: ver
    self_generated_client_one_material acima, que gera client_one.crt/
    .key/.jwks funcionais num diretorio temporario e funciona por si
    so (confirmado: client_one.jwks aparece, o certmaker roda limpo).
    Mas aponta-lo aqui (of.CERTS_DIR -> o temp dir) faz
    start_tls_kem_proxy("classic") QUEBRAR -- o proxy legado completa o
    handshake upstream contra mock_mtls repetidamente (confirmado no
    log do container), mas a checagem de pronto (`_wait_for_tls_kem_
    proxy_ready`, um GET HTTPS local) nunca recebe resposta, 30s de
    timeout. Causa raiz NAO isolada no tempo disponivel -- hipotese mais
    provavel: o `ca.crt`/`ca.key` FRESCOS que o certmaker gera no mesmo
    diretorio (par de CA novo, nao o mesmo de mock-service-os/certs/)
    quebra algo na cadeia de confianca entre o proxy e mock_mtls/mockapi
    de um jeito que nao impede o HANDSHAKE TLS em si mas impede alguma
    chamada HTTP subsequente de responder -- nunca confirmado com
    certeza. Revertido pra nao quebrar um teste que ja passava; o gap
    do material gitignorado pra ESTE teste especifico fica SEM
    correcao, registrado para investigacao futura."""
    conftest.skip_if_stack_not_up()
    proc = of.start_tls_kem_proxy(PROFILE)
    signer_started = of.start_pqc_signer_service(PROFILE)
    try:
        session = requests.Session()
        cert = of.get_local_leg_cert_paths(PROFILE)
        signing_key, kid, alg = of.load_client_signing_key(PROFILE)
        yield session, cert, signing_key, kid, alg
    finally:
        of.stop_pqc_signer_service(signer_started)
        of.stop_tls_kem_proxy(proc)


def _token_request(session, cert, assertion: str):
    body = {
        "grant_type": "client_credentials",
        "scope": "consents",
        "client_assertion": assertion,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
    }
    _, resp = of.do_call(
        session, "POST", f"{of.GATEWAY_SCHEME}://{of.AUTH_CONNECT_HOST}/token", cert=cert,
        host_header=of.AUTH_MTLS_HOST_HEADER, headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=body, src="test_hybrid_and_gate",
    )
    return resp


def test_pqc_absent_rejected(stack):
    """A classical-only PS256 assertion with no `pqc` claim at all must now
    be rejected. This is the exact case Decisao 13's own original text
    already named as a downgrade risk ("invalido ou ausente"), but the
    code only ever implemented the "invalido" half until Decisao 115."""
    session, cert, signing_key, kid, _alg = stack
    classic_key, _pqc_jwk = signing_key
    assertion = of.make_client_assertion(
        classic_key, kid, "PS256", audience=f"https://{of.AUTH_MTLS_HOST_HEADER}/token",
        artifact="test:pqc_absent",
    )
    payload = json.loads(of._b64url_decode(assertion.split(".")[1]))
    assert "pqc" not in payload, "sanity check: this assertion must genuinely have no pqc claim"

    resp = _token_request(session, cert, assertion)
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}: {resp.text}"
    assert "hybrid AND-gate failed" in resp.json().get("error_description", "")


def test_pqc_invalid_rejected(stack):
    """A present-but-corrupted pqc signature must still be rejected -- the
    behavior Decisao 13's original implementation already covered;
    confirmed unchanged by Decisao 115's fix to the absent case."""
    session, cert, signing_key, kid, alg = stack
    classic_key, pqc_jwk = signing_key
    assertion = of.make_client_assertion(signing_key, kid, alg, audience=f"https://{of.AUTH_MTLS_HOST_HEADER}/token",
                                          artifact="test:pqc_invalid")
    header_b64, payload_b64, _old_sig_b64 = assertion.split(".")
    payload = json.loads(of._b64url_decode(payload_b64))
    pqc_sig = bytearray(of._b64url_decode(payload["pqc"]["signature"]))
    pqc_sig[-1] ^= 0xFF
    payload["pqc"]["signature"] = of._b64url_encode(bytes(pqc_sig))

    # Re-sign the classical half over the tampered payload so PS256 itself
    # still verifies -- otherwise oidc-provider's own native check would
    # reject it first, for the wrong reason, before clientHybridAuth.js
    # ever inspects the pqc claim at all.
    retampered = of.pyjwt.encode(payload, classic_key, algorithm="PS256", headers={"kid": kid, "alg": "PS256"})

    resp = _token_request(session, cert, retampered)
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}: {resp.text}"
    assert "hybrid AND-gate failed" in resp.json().get("error_description", "")


def test_pqc_valid_accepted(stack):
    """A genuine hybrid assertion (valid PS256 + valid pqc/ML-DSA-65) must
    still be accepted -- confirms this round didn't turn the AND-gate into
    an always-reject gate."""
    session, cert, signing_key, kid, alg = stack
    assertion = of.make_client_assertion(signing_key, kid, alg, audience=f"https://{of.AUTH_MTLS_HOST_HEADER}/token",
                                          artifact="test:pqc_valid")
    resp = _token_request(session, cert, assertion)
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    assert "access_token" in resp.json()


def test_classic_and_pqc_unaffected(any_profile_stack):
    """Decisao 115 touches only clientHybridAuth.js, which classic/pqc
    never load -- confirms LIVE, not just by reading express.js's
    isHybridProfile gate, that an ordinary client_credentials token
    request still succeeds unchanged in both profiles."""
    if PROFILE == "hybrid":
        pytest.skip("covered by test_pqc_valid_accepted above")
    session, cert, signing_key, kid, alg = any_profile_stack
    assertion = of.make_client_assertion(signing_key, kid, alg, audience=f"https://{of.AUTH_MTLS_HOST_HEADER}/token",
                                          artifact="test:classic_pqc_unaffected")
    resp = _token_request(session, cert, assertion)
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    assert "access_token" in resp.json()

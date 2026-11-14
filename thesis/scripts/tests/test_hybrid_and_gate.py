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


def _with_v9_harness_forced(generator_func):
    """Decisao 165 (pedido do Luciano): TODO perfil (classic/pqc/hybrid/
    hibrido-and) passa pelo MESMO caminho agora -- V9_HARNESS=1 forcado
    incondicionalmente, nunca so pra hybrid/hibrido-and. Elimina de vez
    o ramo legado de opin_flow.start_tls_kem_proxy() (o unico que tinha
    o KeyError 'hibrido-and' -- TLS_KEM_PROXY_CURVE_BY_PROFILE nunca
    teve entrada pra esse perfil, por ser uma ferramenta de 3 perfis
    so). V9_HARNESS e lido no IMPORT do modulo opin_flow (variavel de
    modulo) -- por isso o reload apos setar a env var, revertido no
    finally (mesmo padrao de thesis/scripts/tests/test_profile_cert_
    dispatch.py's _reload_with_v9_harness)."""
    import importlib
    os.environ["V9_HARNESS"] = "1"
    importlib.reload(of)
    try:
        yield from generator_func()
    finally:
        os.environ.pop("V9_HARNESS", None)
        importlib.reload(of)


@pytest.fixture(scope="module")
def stack():
    """Decisao 165: NAO recria mais nenhum container, NAO troca mais
    nenhum alias de rede -- assume que o stack JA esta de pe, no
    perfil certo, subido pelo lancador padrao do repositorio
    (thesis/results/v9/campaign/scripts/run_gate.py, que usa
    orchestrator.SSHExecutor.start_block -- o MESMO caminho que a
    campanha e o piloto usam). A tentativa anterior (Decisao 164) de
    recriar auth/mongo_seed/mockapi AD-HOC de dentro desta fixture nao
    se sustentava de forma confiavel (achado ao vivo, reproduzido 2x:
    auth continuava relatando CRYPTO_PROFILE=classic depois do
    --force-recreate sob hybrid) -- a correcao nao e tentar de novo
    aqui, e nunca mais tentar: `run_gate.py` sobe tudo UMA vez, antes
    de qualquer teste, pelo caminho ja comprovado.

    conftest.assert_stack_profile_matches() FALHA (nunca pula) se o
    perfil vivo nao bater com PROFILE -- essa e a UNICA verificacao
    que esta fixture ainda faz sobre o estado do stack."""
    if PROFILE not in ("hybrid", "hibrido-and"):
        pytest.skip("the payload-extension AND-gate only exists in the two hybrid profiles -- "
                     "classic/pqc never load clientHybridAuth.js (express.js's isHybridProfile gate)")
    conftest.skip_if_stack_not_up()
    conftest.assert_stack_profile_matches(PROFILE)

    def _inner():
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

    yield from _with_v9_harness_forced(_inner)


_MOCK_SERVICE_OS_CERTS_DIR = Path(__file__).resolve().parents[3] / "mock-service-os" / "certs"
_CERTMAKER_ORG_ID = "12345678000195"


def _ensure_client_one_material_exists() -> bool:
    """Decisao 164 (item 3, correcao real -- a tentativa anterior foi
    revertida por ter corrigido o sintoma errado). client_one.key/
    .jwks sao material PRIVADO gitignorado (mock-service-os/certs/
    .gitignore) -- ausente numa worktree genuinamente limpa. A
    tentativa anterior gerava uma CA NOVA do zero num diretorio
    isolado -- isso E a causa real do sintoma "handshake upstream
    completa mas a leitura nunca responde" (confirmado ao vivo nesta
    correcao): o `ca.crt`/`ca.key` novo nao e o mesmo que mock_mtls ja
    confia.

    Correcao real: o proprio `mock-service-os/certs/main.go` ja tem um
    modo pra isso -- flag `-client-one-rsa2048`, que reemite SO
    client_one (crt/key/jwks/hybrid/pqc-enc), assinado pela ca.crt/
    ca.key JA EXISTENTE em disco, nunca uma CA nova. O unico obstaculo
    real: o binario tem seu `sourceDir` (onde ele espera achar ca.crt)
    gravado em tempo de BUILD via runtime.Caller(0) -- `/app` no stage
    builder do Dockerfile -- enquanto o servico `certmaker` do
    docker-compose do mock-service-os monta os certs reais em
    `/app/certs` (um nivel abaixo), nunca em `/app` -- por isso
    `docker-compose run certmaker ./main -client-one-rsa2048` sempre
    daria "no such file or directory" pra ca.crt. Contornado rodando o
    stage BUILDER do Dockerfile direto, com o diretorio REAL de certs
    montado em `/app` (nao `/app/certs`) -- confirmado ao vivo, rodada
    real: client_one.crt/.key/.jwks reemitidos, assinados pela ca.crt
    existente, sem tocar em mais nada.

    So gera se client_one.crt AINDA NAO EXISTE -- nunca sobrescreve
    material real ja presente (confirmado ao vivo que sobrescrever
    client_one ja em uso deixa auth/mockapi com a chave PUBLICA antiga
    em cache -- 401 "client authentication failed" -- ate um
    --force-recreate; numa worktree de verdade recem-clonada isso
    nunca se aplica, porque nao ha nada "ja existente" pra entrar em
    conflito). Devolve True se gerou (quem chamar precisa recriar
    auth/mongo_seed/mockapi antes de usar -- `_recreate_auth_backend`),
    False se o material ja existia (caminho comum, sem restart).

    PRE-CONDICAO que esta funcao NAO tenta resolver por conta propria:
    `ca.crt`/`ca.key` ja existirem em disco -- `-client-one-rsa2048` e
    uma ferramenta de ROTACAO (reemite um cliente usando uma CA JA
    EXISTENTE), nunca de bootstrap de uma PKI inteira do zero;
    confirmado ao vivo que faltando `client_one_pub.jwks` (ou qualquer
    outro arquivo que o fluxo de reemissao espera encontrar) o
    processo falha no meio. `ca.crt` e publico (rastreado no git,
    sempre presente); `ca.key` e privado (gitignorado) -- numa
    worktree git limpa, FALTA, porque um `git worktree add` nunca traz
    arquivos nao-rastreados do checkout original. Isso e
    responsabilidade de QUEM prepara o ambiente da worktree (o mesmo
    processo que ja precisa prover REAL_CERTS_DIR pros testes Go/v9),
    nao desta fixture -- copiar `mock-service-os/certs/ca.key` (e
    `issuer_ca*.key` se outros testes vierem a precisar) do checkout
    principal pra dentro da worktree, UMA vez, antes do gate rodar.
    Falha aqui com uma mensagem explicita, nunca tenta gerar uma CA
    nova (que quebraria a confianca com o mock_mtls/auth/mockapi JA
    rodando, que so confiam na CA que ja tinham)."""
    import subprocess
    if (_MOCK_SERVICE_OS_CERTS_DIR / "client_one.crt").exists():
        return False
    if not (_MOCK_SERVICE_OS_CERTS_DIR / "ca.crt").exists() or not (_MOCK_SERVICE_OS_CERTS_DIR / "ca.key").exists():
        pytest.fail(
            f"{_MOCK_SERVICE_OS_CERTS_DIR}/ca.crt e/ou ca.key ausentes -- esta fixture so sabe REEMITIR "
            "client_one usando uma CA ja existente, nunca criar uma CA nova (isso quebraria a confianca "
            "com o mock_mtls/auth/mockapi ja rodando). Provisione ca.key (gitignorado, copie do checkout "
            "principal) antes de rodar este teste nesta worktree."
        )
    builder_tag = "mock-certmaker-builder-item3-fixture"
    build = subprocess.run(
        ["docker", "build", "--target", "builder", "-t", builder_tag,
         "-f", str(_MOCK_SERVICE_OS_CERTS_DIR / "Dockerfile"), str(_MOCK_SERVICE_OS_CERTS_DIR)],
        capture_output=True, text=True,
    )
    if build.returncode != 0:
        pytest.fail(f"build do certmaker (stage builder) falhou: {build.stderr[-2000:]}")
    run = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{_MOCK_SERVICE_OS_CERTS_DIR}:/app", builder_tag,
         "sh", "-c", f"cd /app && go build -o main . && ./main --org_id={_CERTMAKER_ORG_ID} "
                     "-client-one-rsa2048 && rm -f main"],
        capture_output=True, text=True,
    )
    if run.returncode != 0 or not (_MOCK_SERVICE_OS_CERTS_DIR / "client_one.crt").exists():
        pytest.fail(f"certmaker -client-one-rsa2048 falhou: stdout={run.stdout[-1500:]!r} stderr={run.stderr[-1500:]!r}")
    return True


@pytest.fixture(scope="module")
def any_profile_stack():
    """Same as `stack`, minus the hybrid-only skip -- used only by
    test_classic_and_pqc_unaffected, which needs to run precisely for the
    two profiles `stack` skips. Decisao 165 (item 3): repontado pro
    mesmo caminho do harness que `stack` usa -- trivial, porque
    `run_gate.py` (item 2) ja garante o backend certo de pe antes de
    qualquer teste rodar; nao ha mais motivo pra quarentena. A chamada a
    `_recreate_auth_backend` (removida do arquivo -- item 1) que antes
    seguia um `generated=True` foi descartada, nao substituida: o
    proprio docstring de _ensure_client_one_material_exists() ja
    documentava que ela so gera material NOVO (nunca sobrescreve o que
    existe), e so nesse caso (nada "ja existente" pra entrar em
    conflito) -- ou seja, o restart nunca era necessario no cenario que
    esta funcao de fato trata (worktree limpa); so seria necessario pra
    sobrescrever material em uso, o que a funcao explicitamente nunca
    faz."""
    conftest.skip_if_stack_not_up()
    conftest.assert_stack_profile_matches(PROFILE)
    _ensure_client_one_material_exists()

    def _inner():
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

    yield from _with_v9_harness_forced(_inner)


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

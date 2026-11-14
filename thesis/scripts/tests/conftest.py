"""Decisao 161 (item 5, pedido do Luciano apos a reauditoria da tag
v6): marcador de infraestrutura compartilhado -- distingue "o stack
docker-compose local nao esta de pe" (skip, com motivo explicito) de
"o stack esta de pe e algo quebrou de verdade" (falha real, nunca
mascarada). Usado pelos fixtures de thesis/scripts/tests/
test_signature_verification.py e test_hybrid_and_gate.py, que
dependem de `opin_flow.start_tls_kem_proxy()`/`start_pqc_signer_
service()` alcancando a rede `insurance-server-lambdas_default`
(docker-compose up) -- sem essa rede, o docker run interno falha
quase imediatamente; a checagem aqui e feita ANTES de tentar nada
disso, nunca por um try/except generico em volta do fixture inteiro
(que esconderia uma falha real do stack ja de pe)."""
import subprocess

import pytest

_STACK_NETWORK = "insurance-server-lambdas_default"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "legacy_unsupported(reason): Decisao 163 -- quarentena nominal. Teste que "
        "depende EXCLUSIVAMENTE de opin_flow.start_tls_kem_proxy()'s branch legado "
        "(nunca V9_HARNESS=1/relay.go) atingindo um backend real "
        "(mock_mtls/mock_as), e cuja asserção não tem equivalente coberto pelo "
        "caminho do harness real nem pelos testes de campanha -- verificado caso a "
        "caso, listado nominalmente na Decisao 163 (thesis/results/v9/DECISIONS.md). "
        "Sempre pulado, com o motivo exato do marker, nunca escondido/deselecionado "
        "silenciosamente.",
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        marker = item.get_closest_marker("legacy_unsupported")
        if marker is not None:
            reason = marker.kwargs.get("reason", "sem motivo informado")
            item.add_marker(pytest.mark.skip(reason=f"legacy_unsupported: {reason}"))


_BACKEND_CRYPTO_PROFILE_ENV = {"classico": "classic", "pqc": "pqc", "hibrido-v8": "hybrid", "hibrido-and": "hybrid"}
_GATEWAY_CONTAINER = "v9-mtls"


def _container_crypto_profile(container: str) -> str | None:
    result = subprocess.run(["docker", "exec", container, "printenv", "CRYPTO_PROFILE"],
                             capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def assert_stack_profile_matches(expected_opin_profile: str) -> None:
    """Decisao 165 (pedido do Luciano -- as fixtures de teste NAO
    recriam mais container nenhum; assumem que o stack ja esta de pe
    no perfil certo, subido pelo lancador padrao do repositorio --
    `run_gate.py`/`orchestrator.SSHExecutor.start_block`, o MESMO
    caminho que a campanha e o piloto usam). Esta checagem e a unica
    coisa que um teste ainda faz sobre o perfil do stack: confere, e
    FALHA (nunca pula) se nao bater -- um skip aqui escondia exatamente
    o tipo de falso-PASS que a Decisao 164 achou (auth ainda em
    "classic" enquanto o teste pensava estar testando "hybrid").

    `expected_opin_profile` esta na nomenclatura de `opin_flow.py`
    (classic/pqc/hybrid/hibrido-and) -- convertida aqui pra nomenclatura
    do gateway (classico/pqc/hibrido-v8/hibrido-and, via
    `opin_flow.V9_PROFILE_NAME`) e pra nomenclatura do backend
    (`_BACKEND_CRYPTO_PROFILE_ENV`, a MESMA tabela que
    `orchestrator.BACKEND_CRYPTO_PROFILE_ENV` ja usa -- duplicada aqui
    de proposito, nunca importando `orchestrator.py` deste modulo de
    teste, pra nao criar uma dependencia circular entre
    `campaign/scripts` e `thesis/scripts/tests`; os dois dicts tem que
    ficar idênticos -- conferido por teste dedicado)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import opin_flow as of

    gateway_profile = of.V9_PROFILE_NAME[expected_opin_profile]
    backend_profile = _BACKEND_CRYPTO_PROFILE_ENV[gateway_profile]

    checks = {
        _GATEWAY_CONTAINER: gateway_profile,
        "insurance-server-lambdas-auth-1": backend_profile,
        "insurance-server-lambdas-mockapi-1": backend_profile,
    }
    mismatches = {}
    for container, expected in checks.items():
        actual = _container_crypto_profile(container)
        if actual != expected:
            mismatches[container] = {"expected": expected, "actual": actual}
    if mismatches:
        raise AssertionError(
            f"stack vivo NAO esta no perfil esperado pra CRYPTO_PROFILE={expected_opin_profile!r} "
            f"(pytest) -- {mismatches}. Suba o stack pelo lancador padrao "
            f"(thesis/results/v9/campaign/scripts/run_gate.py) com este perfil ANTES de rodar este "
            f"teste -- esta checagem nunca recria nem conserta nada, so confirma."
        )


def skip_if_stack_not_up():
    """Checagem estreita e especifica: so confirma que a rede docker
    do stack local existe. Nao confirma mais nada sobre o stack (os
    containers podem ainda estar subindo, por exemplo) -- qualquer
    outra falha, com a rede presente, propaga normalmente como uma
    falha real do teste."""
    result = subprocess.run(
        ["docker", "network", "inspect", _STACK_NETWORK],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip(
            f"docker-compose stack nao esta de pe -- rede {_STACK_NETWORK!r} nao encontrada "
            f"(docker network inspect: {result.stderr.strip()}). Suba o stack local "
            "(COMPOSE_PROFILES=main,dev,cs,build-only docker compose up -d, em "
            "insurance-server-lambdas/) antes de rodar este teste."
        )

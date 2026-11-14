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

"""Regressao OBRIGATORIA (pedido explicito do Luciano, item 3, na
generalizacao do orquestrador pra N servidores): o caminho do piloto
(1 servidor, inventario `inventory["server"]` singular, `route_server`
nunca passado) tem que produzir resultado IDENTICO antes e depois da
generalizacao -- comparacao de verdade por DIFF, nunca so "parece
igual".

Como provar isso sem reverter o codigo: `_orchestrator_pre_
generalization_baseline.py` e uma copia CONGELADA e commitada de
`orchestrator.py` exatamente como estava em HEAD antes desta rodada
(extraida com `git show HEAD:.../orchestrator.py`, nunca editada
depois) -- carregada aqui sob um nome de modulo proprio, lado a lado
com o `orchestrator.py` ATUAL (ja generalizado), os dois contra o
MESMO inventario de piloto (`SSHExecutor`, sem `route_server`) e o
MESMO par perfil/rota -- toda resolucao de endereco que importa pro
piloto (`_server_ip`, `_server_gateway_ip`, `_client_ip`,
`_gateway_logs` -- so o HOST que ela resolve, nunca a chamada SSH
cheia, que depende de mocks pesados nao relacionados a esta mudanca)
tem que bater byte a byte."""
import importlib.util
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_baseline_module():
    """Carrega a copia congelada de orchestrator.py (pre-generalizacao)
    sob o nome `orchestrator_baseline` -- nunca colide com o modulo
    `orchestrator` atual, que o resto da suite ja importa normalmente.
    `cli`/`preflight`/`deliver_images`/`evaluate_criteria` sao
    compartilhados (mesmo arquivo em disco, mesmo sys.modules) --
    intencional: queremos as DUAS versoes de orchestrator.py rodando
    contra o MESMO `cli._run` fake, pra comparar so o que o proprio
    orchestrator.py decide, nunca uma diferenca incidental de dublê."""
    baseline_path = Path(__file__).resolve().parent / "_orchestrator_pre_generalization_baseline.py"
    spec = importlib.util.spec_from_file_location("orchestrator_baseline", baseline_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["orchestrator_baseline"] = module
    spec.loader.exec_module(module)
    return module


_BASELINE = _load_baseline_module()
import orchestrator as _CURRENT  # noqa: E402  -- o modulo atual, ja generalizado


def _pilot_inventory():
    """Mesmo formato que o piloto real produz -- `terraform output -json
    inventory` do piloto (thesis/results/v9/terraform/outputs.tf),
    nunca o formato novo (`servers` plural) da campanha oficial."""
    return {
        "control": {"public_ip": "203.0.113.10", "private_ip": "10.0.0.10"},
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.0.50"},
        "clients": {
            "L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.0.60", "colocated": True},
            "L219": {"public_ip": "203.0.113.70", "private_ip": "10.0.2.70", "colocated": False},
            "L325": {"public_ip": "203.0.113.80", "private_ip": "10.0.3.80", "colocated": False},
        },
    }


def test_server_ip_identico_nos_dois_modulos():
    old = _BASELINE.SSHExecutor(_pilot_inventory(), key_path="/fake/key")
    new = _CURRENT.SSHExecutor(_pilot_inventory(), key_path="/fake/key")
    assert old._server_ip() == new._server_ip() == "203.0.113.50"
    # a assinatura nova aceita `route` opcional -- com route_server=None
    # (piloto), o resultado tem que ser o MESMO, `route` nunca importa.
    assert new._server_ip("L219") == new._server_ip() == new._server_ip(None)


def test_server_gateway_ip_identico_para_as_3_rotas_do_piloto():
    old = _BASELINE.SSHExecutor(_pilot_inventory(), key_path="/fake/key")
    new = _CURRENT.SSHExecutor(_pilot_inventory(), key_path="/fake/key")
    for route in ("L0", "L219", "L325"):
        old_val = old._server_gateway_ip(route)
        new_val = new._server_gateway_ip(route)
        assert old_val == new_val, f"rota {route}: antigo={old_val!r} novo={new_val!r}"
    # L0 e co-localizado -- tem que resolver pro IP PRIVADO nos dois.
    assert new._server_gateway_ip("L0") == "10.0.0.50"
    # L219/L325 nao sao co-localizados -- IP PUBLICO nos dois.
    assert new._server_gateway_ip("L219") == "203.0.113.50"


def test_client_ip_identico_para_as_3_rotas():
    old = _BASELINE.SSHExecutor(_pilot_inventory(), key_path="/fake/key")
    new = _CURRENT.SSHExecutor(_pilot_inventory(), key_path="/fake/key")
    for route in ("L0", "L219", "L325"):
        assert old._client_ip(route) == new._client_ip(route)


class _FakeProc:
    returncode, stdout, stderr = 0, "", ""


def test_gateway_logs_resolve_o_mesmo_host_nos_dois_modulos(monkeypatch):
    calls_old, calls_new = [], []
    import cli

    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: (calls_old.append(argv), _FakeProc())[1])
    old = _BASELINE.SSHExecutor(_pilot_inventory(), key_path="/fake/key")
    old._gateway_logs("2026-01-01T00:00:00", "2026-01-01T00:01:00")

    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: (calls_new.append(argv), _FakeProc())[1])
    new = _CURRENT.SSHExecutor(_pilot_inventory(), key_path="/fake/key")
    new._gateway_logs("2026-01-01T00:00:00", "2026-01-01T00:01:00", route=None)

    assert calls_old == calls_new, (
        f"comandos SSH diferentes entre as duas versoes:\nANTIGO: {calls_old}\nNOVO: {calls_new}"
    )
    assert any("203.0.113.50" in " ".join(c) for c in calls_old), calls_old


def test_mutante_route_server_setado_no_modo_campanha_exige_route_nunca_opcional():
    """Mutante/prova de robustez: no modo campanha (`route_server`
    setado), chamar `_server_ip()` SEM `route` tem que falhar alto
    (fail-closed -- nunca silenciosamente resolver o servidor errado)
    -- bem diferente do piloto antigo, onde `route` nunca era sequer
    um parametro. Confirma que os dois modos sao genuinamente
    distintos, nunca uma coincidencia que esconderia um bug."""
    import pytest
    new_campaign_mode = _CURRENT.SSHExecutor(
        {"servers": {"sa-east-1": {"public_ip": "203.0.113.50", "private_ip": "10.0.0.50"}},
         "clients": {"L219": {"public_ip": "203.0.113.70", "colocated": False}}},
        key_path="/fake/key", route_server={"L219": "sa-east-1"},
    )
    with pytest.raises(KeyError):
        new_campaign_mode._server_ip()  # route=None por default -- route_server[None] nao existe

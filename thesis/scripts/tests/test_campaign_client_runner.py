"""Decisao 159, item 3 (pedido do autor): campaign_client_runner.py
recusa (fail-closed) qualquer execucao sem V9_HARNESS=1 -- o caminho
legado pre-v9 de opin_flow.py (sem essa flag) ainda completa um
handshake sem erro visivel, e ja produziu um achado falso-positivo
nesta mesma linha de pesquisa. Testado via subprocess real (mesma
forma que a campanha de verdade invoca este script) -- nunca importa
main() direto, pra nao herdar nenhum estado de ambiente desta sessao
de teste."""
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "campaign_client_runner.py"


def _run(env_overrides: dict):
    env = {k: v for k, v in os.environ.items() if k not in ("V9_HARNESS", "REMOTE_GATEWAY_HOST", "CRYPTO_PROFILE")}
    env.update(env_overrides)
    # Sem -I: o proprio projeto invoca este script sem isolamento
    # (`python3 campaign_client_runner.py`, orchestrator.py's
    # remote_cmd) -- -I remove o diretorio do script do sys.path,
    # quebrando `import latency_automation`/`opin_flow` (modulos
    # irmaos, mesmo diretorio).
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--label", "run01"],
        capture_output=True, text=True, env=env,
    )


def test_refuses_when_v9_harness_unset():
    result = _run({})
    assert result.returncode != 0
    assert "V9_HARNESS" in result.stderr


def test_refuses_when_v9_harness_not_one():
    result = _run({"V9_HARNESS": "0"})
    assert result.returncode != 0
    assert "V9_HARNESS" in result.stderr


def test_refuses_when_v9_harness_empty_string():
    result = _run({"V9_HARNESS": ""})
    assert result.returncode != 0
    assert "V9_HARNESS" in result.stderr


def test_v9_harness_set_but_remote_gateway_host_missing_still_refuses_with_its_own_message():
    """Confirma que a checagem nova (V9_HARNESS) nao substitui nem
    esconde a checagem antiga (REMOTE_GATEWAY_HOST) -- cada uma com
    sua propria mensagem, na ordem certa."""
    result = _run({"V9_HARNESS": "1"})
    assert result.returncode != 0
    assert "REMOTE_GATEWAY_HOST" in result.stderr
    assert "V9_HARNESS" not in result.stderr

"""Testes de check_operator_ip.py (Decisao 75, item 5) -- curl/
terraform stubados via cli._run/cli.run_terraform monkeypatchados,
nenhuma chamada real, nenhuma credencial."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import check_operator_ip as coi  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _fake_state_json(cidr):
    return json.dumps({
        "values": {
            "root_module": {
                "resources": [],
                "child_modules": [
                    {
                        "address": "module.control",
                        "resources": [
                            {
                                "address": coi.SSH_RULE_ADDRESS,
                                "values": {"cidr_ipv4": cidr},
                            }
                        ],
                    }
                ],
            }
        }
    })


def test_current_operator_ip_le_saida_do_curl(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: FakeProc(stdout="203.0.113.9\n"))
    assert coi.current_operator_ip() == "203.0.113.9"


def test_current_operator_ip_falha_alto_se_curl_falha(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: FakeProc(returncode=1, stderr="timeout"))
    with pytest.raises(RuntimeError, match="curl falhou"):
        coi.current_operator_ip()


def test_last_applied_operator_cidr_le_do_state(monkeypatch):
    monkeypatch.setattr(cli, "run_terraform", lambda args, cwd, timeout=120: (0, _fake_state_json("203.0.113.9/32"), ""))
    assert coi.last_applied_operator_cidr("/fake/tf") == "203.0.113.9/32"


def test_last_applied_operator_cidr_falha_alto_se_show_falha(monkeypatch):
    monkeypatch.setattr(cli, "run_terraform", lambda args, cwd, timeout=120: (1, "", "state locked"))
    with pytest.raises(RuntimeError, match="terraform show falhou"):
        coi.last_applied_operator_cidr("/fake/tf")


def test_last_applied_operator_cidr_falha_alto_se_recurso_ausente(monkeypatch):
    empty_state = json.dumps({"values": {"root_module": {"resources": [], "child_modules": []}}})
    monkeypatch.setattr(cli, "run_terraform", lambda args, cwd, timeout=120: (0, empty_state, ""))
    with pytest.raises(RuntimeError, match="nao encontrado"):
        coi.last_applied_operator_cidr("/fake/tf")


def test_ensure_operator_ip_current_nao_reaplica_se_ip_igual(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: FakeProc(stdout="203.0.113.9\n"))
    calls = []

    def fake_terraform(args, cwd, timeout=120):
        calls.append(args)
        return 0, _fake_state_json("203.0.113.9/32"), ""

    monkeypatch.setattr(cli, "run_terraform", fake_terraform)
    result = coi.ensure_operator_ip_current("/fake/tf")
    assert result == {"changed": False, "cidr": "203.0.113.9/32"}
    assert not any(a[0] == "apply" for a in calls), "IP igual -- nunca deveria reaplicar"


def test_ensure_operator_ip_current_reaplica_se_ip_diferente(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: FakeProc(stdout="198.51.100.7\n"))
    calls = []

    def fake_terraform(args, cwd, timeout=120):
        calls.append(args)
        if args[0] == "show":
            return 0, _fake_state_json("203.0.113.9/32"), ""
        return 0, "Apply complete!", ""

    monkeypatch.setattr(cli, "run_terraform", fake_terraform)
    result = coi.ensure_operator_ip_current("/fake/tf")
    assert result == {"changed": True, "old_cidr": "203.0.113.9/32", "new_cidr": "198.51.100.7/32"}
    apply_call = next(a for a in calls if a[0] == "apply")
    assert f"-target={coi.SSH_RULE_ADDRESS}" in apply_call
    assert "-var=operator_ip_cidr=198.51.100.7/32" in apply_call


def test_ensure_operator_ip_current_falha_alto_se_reaplicar_falha(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: FakeProc(stdout="198.51.100.7\n"))

    def fake_terraform(args, cwd, timeout=120):
        if args[0] == "show":
            return 0, _fake_state_json("203.0.113.9/32"), ""
        return 1, "", "Error: SG rule update conflict"

    monkeypatch.setattr(cli, "run_terraform", fake_terraform)
    with pytest.raises(RuntimeError, match="reaplicar a regra falhou"):
        coi.ensure_operator_ip_current("/fake/tf")

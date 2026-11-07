"""Testes do pre-voo -- `aws` stubado (cli.run_aws_json/cli.run_aws
monkeypatchados), nenhuma chamada real, nenhuma credencial. Confirma
em especial que o Account ID NUNCA aparece em nenhum resultado."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import preflight  # noqa: E402

FAKE_ACCOUNT_ID = "123456789012"


def test_identity_ok_nunca_inclui_account_id(monkeypatch):
    monkeypatch.setattr(cli, "run_aws_json", lambda args, **kw: {"Arn": f"arn:aws:iam::{FAKE_ACCOUNT_ID}:user/fake"})
    result = preflight.check_identity("fake-profile")
    assert result["ok"] is True
    assert FAKE_ACCOUNT_ID not in str(result)


def test_vcpu_quota_abaixo_do_minimo_reprova(monkeypatch):
    monkeypatch.setattr(cli, "run_aws_json", lambda args, **kw: {"Quota": {"Value": 5.0}})
    result = preflight.check_vcpu_quota("sa-east-1", "fake-profile", min_required=10)
    assert result["ok"] is False
    assert result["value"] == 5.0


def test_vcpu_quota_suficiente_passa(monkeypatch):
    monkeypatch.setattr(cli, "run_aws_json", lambda args, **kw: {"Quota": {"Value": 32.0}})
    result = preflight.check_vcpu_quota("sa-east-1", "fake-profile", min_required=10)
    assert result["ok"] is True


def test_tipo_de_instancia_ausente_e_detectado(monkeypatch):
    monkeypatch.setattr(cli, "run_aws_json", lambda args, **kw: {"InstanceTypeOfferings": [{"InstanceType": "t4g.micro"}]})
    result = preflight.check_instance_type_availability("sa-east-1", "fake-profile", ["m7i-flex.large", "t4g.micro"])
    assert result["ok"] is False
    assert result["missing"] == ["m7i-flex.large"]


def test_tipo_de_instancia_todos_presentes_passa(monkeypatch):
    monkeypatch.setattr(cli, "run_aws_json",
                         lambda args, **kw: {"InstanceTypeOfferings": [{"InstanceType": "m7i-flex.large"}, {"InstanceType": "t4g.micro"}]})
    result = preflight.check_instance_type_availability("sa-east-1", "fake-profile", ["m7i-flex.large", "t4g.micro"])
    assert result["ok"] is True


def test_ami_nao_resolve_reprova(monkeypatch):
    monkeypatch.setattr(cli, "run_aws_json", lambda args, **kw: {"Images": []})
    result = preflight.check_ami_resolves("sa-east-1", "fake-profile", "al2023-ami-*")
    assert result["ok"] is False


def test_budget_alert_usa_account_id_na_chamada_mas_nunca_no_retorno(monkeypatch):
    json_calls = []

    def fake_run_aws(args, profile=None, region=None, timeout=30):
        return FAKE_ACCOUNT_ID + "\n"

    def fake_run_aws_json(args, profile=None, region=None, timeout=30):
        json_calls.append(args)
        return {"Budgets": [{"BudgetName": "piloto-v9"}]}

    monkeypatch.setattr(cli, "run_aws", fake_run_aws)
    monkeypatch.setattr(cli, "run_aws_json", fake_run_aws_json)
    result = preflight.check_budget_alert_exists("fake-profile")

    assert result["ok"] is True
    assert FAKE_ACCOUNT_ID not in str(result), "o Account ID nunca pode aparecer no resultado devolvido"
    assert any(FAKE_ACCOUNT_ID in a for call in json_calls for a in call), (
        "a chamada real --account-id (describe-budgets) tem que ter sido feita (so nao pode VAZAR no retorno)"
    )


def test_rede_de_seguranca_detecta_arn_vazado(monkeypatch):
    """Mutacao direta: simula um check que, por bug, devolveria um
    ARN de verdade -- a rede de seguranca (assert dentro de
    run_preflight) tem que disparar."""
    monkeypatch.setattr(preflight, "check_identity", lambda profile: {
        "check": "identidade da credencial", "ok": True,
        "note": "arn:aws:iam::123456789012:user/vazou-de-verdade",  # bug simulado
    })
    monkeypatch.setattr(preflight, "check_vcpu_quota", lambda region, profile, min_required=10: {"check": "x", "ok": True})
    monkeypatch.setattr(preflight, "check_instance_type_availability", lambda region, profile, types: {"check": "y", "ok": True})
    monkeypatch.setattr(preflight, "check_ami_resolves", lambda region, profile, pattern: {"check": "z", "ok": True})
    monkeypatch.setattr(preflight, "check_budget_alert_exists", lambda profile: {"check": "w", "ok": True})

    with pytest.raises(AssertionError, match="VAZAMENTO"):
        preflight.run_preflight("fake-profile", ["sa-east-1"], {"sa-east-1": ["m7i-flex.large"]}, {"sa-east-1": "al2023*"})


def test_go_e_false_se_qualquer_check_falhar(monkeypatch):
    monkeypatch.setattr(preflight, "check_identity", lambda profile: {"check": "a", "ok": True})
    monkeypatch.setattr(preflight, "check_vcpu_quota", lambda region, profile, min_required=10: {"check": "b", "ok": False})
    monkeypatch.setattr(preflight, "check_instance_type_availability", lambda region, profile, types: {"check": "c", "ok": True})
    monkeypatch.setattr(preflight, "check_ami_resolves", lambda region, profile, pattern: {"check": "d", "ok": True})
    monkeypatch.setattr(preflight, "check_budget_alert_exists", lambda profile: {"check": "e", "ok": True})

    result = preflight.run_preflight("fake-profile", ["sa-east-1"], {"sa-east-1": ["m7i-flex.large"]}, {"sa-east-1": "al2023*"})
    assert result["go"] is False


def test_mutante_go_sempre_true_e_pego(monkeypatch):
    """Mutacao: run_preflight() usando any() em vez de all() pra
    agregar -- o teste acima (go False com 1 check falho) reprovaria
    com essa mutacao, confirmando que ele depende de verdade do all()."""
    monkeypatch.setattr(preflight, "check_identity", lambda profile: {"check": "a", "ok": True})
    monkeypatch.setattr(preflight, "check_vcpu_quota", lambda region, profile, min_required=10: {"check": "b", "ok": False})
    monkeypatch.setattr(preflight, "check_instance_type_availability", lambda region, profile, types: {"check": "c", "ok": True})
    monkeypatch.setattr(preflight, "check_ami_resolves", lambda region, profile, pattern: {"check": "d", "ok": True})
    monkeypatch.setattr(preflight, "check_budget_alert_exists", lambda profile: {"check": "e", "ok": True})

    checks = [preflight.check_identity("fake-profile"), preflight.check_vcpu_quota("sa-east-1", "fake-profile"),
              preflight.check_instance_type_availability("sa-east-1", "fake-profile", []),
              preflight.check_ami_resolves("sa-east-1", "fake-profile", ""), preflight.check_budget_alert_exists("fake-profile")]
    go_mutante = any(c["ok"] for c in checks)  # mutante: deveria ser all()
    assert go_mutante is True
    with pytest.raises(AssertionError):
        assert go_mutante is False

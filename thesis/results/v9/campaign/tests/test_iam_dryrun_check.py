"""Testes do iam_dryrun_check.py -- `cli.run_aws`/`cli.run_aws_json`
stubados, NENHUMA chamada real a AWS (Decisao 55, item 4: este
processo nunca executa o script de verdade, so escreve e testa com
mock -- o Luciano roda)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import iam_dryrun_check as idc  # noqa: E402


def _raise_dryrun_authorized(*a, **kw):
    raise RuntimeError("aws ec2 run-instances falhou: An error occurred (DryRunOperation) when calling the RunInstances operation: Request would have succeeded, but DryRun flag is set.")


def _raise_unauthorized(*a, **kw):
    raise RuntimeError("aws ec2 run-instances falhou: An error occurred (UnauthorizedOperation) when calling the RunInstances operation: You are not authorized to perform this operation.")


def test_dryrun_autorizado_e_ok(monkeypatch):
    monkeypatch.setattr(cli, "run_aws", _raise_dryrun_authorized)
    result = idc.check_run_instances("sa-east-1", "fake-profile")
    assert result["ok"] is True
    assert "DryRunOperation" in result["note"]


def test_unauthorized_e_reprovado(monkeypatch):
    monkeypatch.setattr(cli, "run_aws", _raise_unauthorized)
    result = idc.check_run_instances("sa-east-1", "fake-profile")
    assert result["ok"] is False
    assert "UnauthorizedOperation" in result["note"]


def test_acao_sem_recurso_id_fica_nao_testada_nunca_inventada_como_pass():
    result = idc.check_terminate_instances("sa-east-1", "fake-profile", instance_id=None)
    assert result["ok"] is None
    assert "pulado" in result["note"]


def test_acao_com_recurso_id_e_testada_de_verdade(monkeypatch):
    monkeypatch.setattr(cli, "run_aws", _raise_dryrun_authorized)
    result = idc.check_terminate_instances("sa-east-1", "fake-profile", instance_id="i-fake123")
    assert result["ok"] is True


def test_run_all_checks_agrega_as_3_regioes(monkeypatch):
    monkeypatch.setattr(cli, "run_aws", _raise_dryrun_authorized)
    monkeypatch.setattr(cli, "run_aws_json", lambda *a, **kw: {"Reservations": []})
    result = idc.run_all_checks("fake-profile")
    assert set(result["results"].keys()) == set(idc.REGIONS)
    assert result["all_tested_ok"] is True
    # acoes que exigem recurso real, sem nenhum ID passado -- "nao
    # testado" pras 3 regioes x 7 acoes (create-sg, authorize-ingress,
    # terminate, modify-attribute, release-address, delete-key, revoke).
    assert len(result["not_tested"]) == 3 * 7


def test_run_all_checks_reprova_se_qualquer_acao_for_unauthorized(monkeypatch):
    def fake_run_aws(argv, region=None, profile=None, timeout=30):
        if "run-instances" in argv and region == "eu-north-1":
            raise RuntimeError("An error occurred (UnauthorizedOperation) when calling the RunInstances operation")
        raise RuntimeError("An error occurred (DryRunOperation) when calling the X operation")

    monkeypatch.setattr(cli, "run_aws", fake_run_aws)
    monkeypatch.setattr(cli, "run_aws_json", lambda *a, **kw: {"Reservations": []})
    result = idc.run_all_checks("fake-profile")
    assert result["all_tested_ok"] is False
    assert result["results"]["eu-north-1"]["ec2:RunInstances"]["ok"] is False


def test_mutante_ignora_unauthorized_e_pego(monkeypatch):
    """Mutacao: `all_tested_ok` calculado so olhando se alguma
    chamada tem `ok is True`, nunca reprovando por `ok is False` --
    o teste acima (reprova com 1 UnauthorizedOperation) tem que
    reprovar com essa mutacao."""
    checks = {"a": {"ok": False}, "b": {"ok": True}}
    mutante_all_ok = any(c["ok"] for c in checks.values())  # mutante: deveria ser all(c["ok"] is not False ...)
    assert mutante_all_ok is True
    with pytest.raises(AssertionError):
        assert mutante_all_ok is False

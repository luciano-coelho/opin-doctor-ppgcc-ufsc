"""Testes da limpeza/verificacao final -- `aws` e `terraform`
stubados (cli.run_aws_json/cli.run_terraform monkeypatchados),
nenhuma chamada real, nenhuma credencial."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import cleanup  # noqa: E402


def _empty_region_responses():
    return {
        "ec2 describe-instances": {"Reservations": []},
        "ec2 describe-addresses": {"Addresses": []},
        "ec2 describe-security-groups": {"SecurityGroups": []},
        "ec2 describe-key-pairs": {"KeyPairs": []},
        "ec2 describe-volumes": {"Volumes": []},
    }


def _fake_run_aws_json_factory(responses_by_call):
    def fake(args, profile=None, region=None, timeout=30):
        key = " ".join(args[:2])
        return responses_by_call.get(key, {})
    return fake


def test_force_sem_marcador_falha_alto(tmp_path):
    with pytest.raises(RuntimeError, match="nao encontrado"):
        cleanup.full_cleanup(str(tmp_path), "fake-profile", pull_verified_marker=str(tmp_path / "nao-existe"))


def test_verify_region_limpa_quando_tudo_vazio(monkeypatch):
    monkeypatch.setattr(cli, "run_aws_json", _fake_run_aws_json_factory(_empty_region_responses()))
    report = cleanup.verify_region("sa-east-1", "fake-profile")
    assert report["clean"] is True
    assert report["orphaned_eips"] == []


def test_verify_region_nao_limpa_com_instancia_rodando(monkeypatch):
    responses = _empty_region_responses()
    responses["ec2 describe-instances"] = {"Reservations": [{"Instances": [{"State": {"Name": "running"}}]}]}
    monkeypatch.setattr(cli, "run_aws_json", _fake_run_aws_json_factory(responses))
    report = cleanup.verify_region("sa-east-1", "fake-profile")
    assert report["clean"] is False
    assert report["instances"] == 1


def test_eip_orfao_detectado_mas_nao_liberado_sem_flag(monkeypatch):
    responses = _empty_region_responses()
    responses["ec2 describe-addresses"] = {"Addresses": [{"AllocationId": "eipalloc-fake1"}]}  # sem InstanceId
    monkeypatch.setattr(cli, "run_aws_json", _fake_run_aws_json_factory(responses))
    release_calls = []
    monkeypatch.setattr(cli, "run_aws", lambda args, **kw: release_calls.append(args))

    report = cleanup.verify_region("sa-east-1", "fake-profile")
    assert len(report["orphaned_eips"]) == 1
    released = cleanup.release_orphaned_eips("sa-east-1", "fake-profile", report["orphaned_eips"], actually_release=False)
    assert released == ["eipalloc-fake1"]
    assert release_calls == [], "sem --release-eips, NUNCA deveria chamar release-address de verdade"


def test_eip_orfao_liberado_de_verdade_com_flag(monkeypatch):
    responses = _empty_region_responses()
    responses["ec2 describe-addresses"] = {"Addresses": [{"AllocationId": "eipalloc-fake2"}]}
    monkeypatch.setattr(cli, "run_aws_json", _fake_run_aws_json_factory(responses))
    release_calls = []
    monkeypatch.setattr(cli, "run_aws", lambda args, **kw: release_calls.append(args))

    report = cleanup.verify_region("sa-east-1", "fake-profile")
    cleanup.release_orphaned_eips("sa-east-1", "fake-profile", report["orphaned_eips"], actually_release=True)
    assert release_calls == [["ec2", "release-address", "--allocation-id", "eipalloc-fake2"]]


def test_drift_detectado_quando_menos_de_5_instancias(monkeypatch):
    def fake_instances(region, profile):
        return [1, 2] if region == "sa-east-1" else []  # so 2 de 5 esperadas

    monkeypatch.setattr(cleanup, "_describe_instances", fake_instances)
    drift = cleanup.check_self_terminate_drift("fake-profile")
    assert drift["drift_detected"] is True
    assert drift["total_running"] == 2


def test_sem_drift_quando_5_instancias_presentes(monkeypatch):
    def fake_instances(region, profile):
        return [1] if region == "eu-north-1" or region == "ap-southeast-1" else [1, 1, 1]

    monkeypatch.setattr(cleanup, "_describe_instances", fake_instances)
    drift = cleanup.check_self_terminate_drift("fake-profile")
    assert drift["drift_detected"] is False
    assert drift["total_running"] == 5


def test_destroy_falho_levanta_antes_de_verificar_regioes(monkeypatch, tmp_path):
    marker = tmp_path / ".pull-verified"
    marker.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(cleanup, "check_self_terminate_drift", lambda profile: {"drift_detected": False})
    monkeypatch.setattr(cli, "run_terraform", lambda args, cwd, timeout=120: (1, "", "destroy failed"))
    verify_calls = []
    monkeypatch.setattr(cleanup, "verify_region", lambda region, profile: verify_calls.append(region))

    with pytest.raises(RuntimeError, match="terraform destroy falhou"):
        cleanup.full_cleanup(str(tmp_path), "fake-profile", pull_verified_marker=str(marker))
    assert verify_calls == [], "nunca deveria tentar verificar regioes se o destroy ja falhou"


def test_mutante_clean_sempre_true_e_pego_pelo_teste_de_instancia_rodando(monkeypatch):
    """Mutacao: verify_region() reportaria 'clean=True' mesmo com uma
    instancia rodando -- test_verify_region_nao_limpa_com_instancia_rodando
    acima tem que reprovar com essa mutacao."""
    responses = _empty_region_responses()
    responses["ec2 describe-instances"] = {"Reservations": [{"Instances": [{"State": {"Name": "running"}}]}]}
    monkeypatch.setattr(cli, "run_aws_json", _fake_run_aws_json_factory(responses))

    original_verify_region = cleanup.verify_region

    def mutated_verify_region(region, profile):
        report = original_verify_region(region, profile)
        report["clean"] = True  # mutante: ignora o que foi encontrado
        return report

    report = mutated_verify_region("sa-east-1", "fake-profile")
    with pytest.raises(AssertionError):
        assert report["clean"] is False

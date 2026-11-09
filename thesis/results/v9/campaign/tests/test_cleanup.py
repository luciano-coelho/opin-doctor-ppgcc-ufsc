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


# --- Pedido do Luciano (item 0, regra fail-closed nova): o teardown
# so pode rodar depois dos brutos coletados e VERIFICADOS por sha256
# -- `--force` (bypass do marcador) agora EXIGE uma `reason` explicita
# (excecao de custo/seguranca, regra 7), nunca um jeito de pular a
# verificacao por conveniencia/costume (achado real: o PILOT_RUNBOOK.md
# mandava `--force` como o comando PRINCIPAL, nunca exercitando o gate).

def test_force_sem_reason_falha_alto(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup, "check_self_terminate_drift", lambda profile: {"drift_detected": False})
    with pytest.raises(RuntimeError, match="reason"):
        cleanup.full_cleanup(str(tmp_path), "fake-profile", force=True)


def test_force_com_reason_vazia_falha_alto(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup, "check_self_terminate_drift", lambda profile: {"drift_detected": False})
    with pytest.raises(RuntimeError, match="reason"):
        cleanup.full_cleanup(str(tmp_path), "fake-profile", force=True, reason="   ")


def test_force_com_reason_explicita_prossegue_e_reporta(monkeypatch, tmp_path):
    monkeypatch.setattr(cleanup, "check_self_terminate_drift", lambda profile: {"drift_detected": False})
    monkeypatch.setattr(cli, "run_terraform", lambda args, cwd, timeout=120: (0, "destroyed", ""))
    monkeypatch.setattr(cli, "run_aws_json", _fake_run_aws_json_factory(_empty_region_responses()))

    result = cleanup.full_cleanup(str(tmp_path), "fake-profile", force=True,
                                   reason="limite de custo atingido no meio do piloto")
    assert result["all_clean"] is True
    assert result["forced"] is True
    assert result["reason"] == "limite de custo atingido no meio do piloto"


def test_sem_force_nunca_reporta_forced(monkeypatch, tmp_path):
    marker = tmp_path / ".pull-verified"
    marker.write_text("ok", encoding="utf-8")
    monkeypatch.setattr(cleanup, "check_self_terminate_drift", lambda profile: {"drift_detected": False})
    monkeypatch.setattr(cli, "run_terraform", lambda args, cwd, timeout=120: (0, "destroyed", ""))
    monkeypatch.setattr(cli, "run_aws_json", _fake_run_aws_json_factory(_empty_region_responses()))

    result = cleanup.full_cleanup(str(tmp_path), "fake-profile", pull_verified_marker=str(marker))
    assert result["forced"] is False
    assert result["reason"] is None


def test_mutante_force_sem_exigir_reason_e_pego(tmp_path, monkeypatch):
    """Mutante = o comportamento ANTIGO (antes desta Emenda): `--force`
    sozinho, sem nenhuma `reason`, ja bastava pra pular o marcador --
    exatamente o jeito que o PILOT_RUNBOOK.md usava no Passo 14 (achado
    real desta rodada: o gate nunca era de fato exercitado). O teste
    real acima (`test_force_sem_reason_falha_alto`) reprova com essa
    mutacao."""
    monkeypatch.setattr(cleanup, "check_self_terminate_drift", lambda profile: {"drift_detected": False})

    def mutant_full_cleanup_sem_exigir_reason(tf_dir, profile, force=False, pull_verified_marker=None):
        if not force:
            if pull_verified_marker is None or not Path(pull_verified_marker).is_file():
                raise RuntimeError(f"{pull_verified_marker} nao encontrado")
        return {"forced": force}  # mutante: nunca checa reason, passa direto

    result = mutant_full_cleanup_sem_exigir_reason(str(tmp_path), "fake-profile", force=True)
    assert result["forced"] is True  # mutante aceitou sem reason -- a lacuna real que esta Emenda fecha
    with pytest.raises(RuntimeError, match="reason"):
        cleanup.full_cleanup(str(tmp_path), "fake-profile", force=True)  # codigo REAL reprova a mesma chamada

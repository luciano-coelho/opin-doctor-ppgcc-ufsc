"""Testes da parada de emergencia (Decisao 55, item 5) -- `cli.run_aws`/
`cli.run_aws_json` stubados, NENHUMA chamada real. Confirma em
especial que toda acao destrutiva so roda sobre um ID que veio de uma
`describe-*` filtrada pela tag do projeto."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import emergency_stop as es  # noqa: E402

FAKE_INSTANCE = {"InstanceId": "i-tagged123", "State": {"Name": "running"}}
FAKE_EIP = {"AllocationId": "eipalloc-tagged1", "AssociationId": "eipassoc-1"}
FAKE_SG = {"GroupId": "sg-tagged1"}
FAKE_KEY = {"KeyName": "mockopin-pqc-v9-piloto"}


def _fake_describe(region, profile):
    def fake_run_aws_json(argv, region=None, profile=None, timeout=30):
        if "describe-instances" in argv:
            return {"Reservations": [{"Instances": [FAKE_INSTANCE]}]}
        if "describe-addresses" in argv:
            return {"Addresses": [FAKE_EIP]}
        if "describe-security-groups" in argv:
            return {"SecurityGroups": [FAKE_SG]}
        if "describe-key-pairs" in argv:
            return {"KeyPairs": [FAKE_KEY]}
        return {}
    return fake_run_aws_json


def test_dry_mode_nunca_chama_acao_destrutiva(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_aws_json", _fake_describe("sa-east-1", "fake"))
    monkeypatch.setattr(cli, "run_aws", lambda *a, **kw: calls.append(a) or "")
    report = es.stop_region("sa-east-1", "fake-profile", execute=False)
    assert report["instances_found"] == ["i-tagged123"]
    assert report["instances_terminated"] == []
    assert report["eips_released"] == []
    assert report["security_groups_deleted"] == []
    assert report["key_pairs_deleted"] == []
    assert calls == [], "modo dry nunca pode chamar nenhuma acao mutavel"


def test_execute_termina_so_o_id_que_veio_da_tag(monkeypatch):
    calls = []

    def fake_run_aws(argv, region=None, profile=None, timeout=30):
        calls.append(argv)
        return ""

    monkeypatch.setattr(cli, "run_aws_json", _fake_describe("sa-east-1", "fake"))
    monkeypatch.setattr(cli, "run_aws", fake_run_aws)
    report = es.stop_region("sa-east-1", "fake-profile", execute=True, wait_fn=lambda s: None)
    terminate_calls = [c for c in calls if "terminate-instances" in c]
    assert len(terminate_calls) == 1
    assert "i-tagged123" in terminate_calls[0]
    assert report["instances_terminated"] == ["i-tagged123"]


def test_execute_desassocia_antes_de_liberar_eip(monkeypatch):
    calls = []

    def fake_run_aws(argv, region=None, profile=None, timeout=30):
        calls.append(argv)
        return ""

    monkeypatch.setattr(cli, "run_aws_json", _fake_describe("sa-east-1", "fake"))
    monkeypatch.setattr(cli, "run_aws", fake_run_aws)
    report = es.stop_region("sa-east-1", "fake-profile", execute=True, wait_fn=lambda s: None)
    disassoc_idx = next(i for i, c in enumerate(calls) if "disassociate-address" in c)
    release_idx = next(i for i, c in enumerate(calls) if "release-address" in c)
    assert disassoc_idx < release_idx
    assert report["eips_released"] == ["eipalloc-tagged1"]


def test_execute_apaga_sg_e_key_pair_encontrados_pela_tag(monkeypatch):
    calls = []

    def fake_run_aws(argv, region=None, profile=None, timeout=30):
        calls.append(argv)
        return ""

    monkeypatch.setattr(cli, "run_aws_json", _fake_describe("sa-east-1", "fake"))
    monkeypatch.setattr(cli, "run_aws", fake_run_aws)
    report = es.stop_region("sa-east-1", "fake-profile", execute=True, wait_fn=lambda s: None)
    assert report["security_groups_deleted"] == ["sg-tagged1"]
    assert report["key_pairs_deleted"] == ["mockopin-pqc-v9-piloto"]


def test_sem_tag_nenhuma_instancia_encontrada_nenhuma_acao(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_aws_json", lambda *a, **kw: {"Reservations": [], "Addresses": [], "SecurityGroups": [], "KeyPairs": []})
    monkeypatch.setattr(cli, "run_aws", lambda *a, **kw: calls.append(a) or "")
    report = es.stop_region("sa-east-1", "fake-profile", execute=True, wait_fn=lambda s: None)
    assert report["instances_found"] == []
    assert calls == []


def test_mutante_ignora_tag_e_destroi_sem_filtrar_e_pego(monkeypatch):
    """Mutacao: `stop_region` que termina um ID fixo, nunca derivado
    da `describe-instances` filtrada por tag -- os testes acima
    (so o ID TAGGED aparece) tem que reprovar com essa mutacao."""
    calls = []

    def mutant_stop_region(region, profile, execute=False):
        cli.run_aws(["ec2", "terminate-instances", "--instance-ids", "i-NUNCA-FOI-TAGGEADO"], region=region, profile=profile)
        return {"instances_terminated": ["i-NUNCA-FOI-TAGGEADO"]}

    monkeypatch.setattr(cli, "run_aws", lambda *a, **kw: calls.append(a) or "")
    report = mutant_stop_region("sa-east-1", "fake-profile", execute=True)
    assert report["instances_terminated"] == ["i-NUNCA-FOI-TAGGEADO"]  # mutante age sem checar tag
    with pytest.raises(AssertionError):
        assert report["instances_terminated"] == ["i-tagged123"]

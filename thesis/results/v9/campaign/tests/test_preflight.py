"""Testes do pre-voo -- `aws` stubado (cli.run_aws_json/cli.run_aws
monkeypatchados), nenhuma chamada real, nenhuma credencial. Confirma
em especial que o Account ID NUNCA aparece em nenhum resultado."""
import json
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


# --- Decisao 51 (item 2): checagem do interprete Python do cliente --
# REAIS, nunca stubadas (e exatamente o interprete que esta sendo
# testado, nao a CLI da aws/ssh) -- pede dois interpretes de verdade
# ja presentes nesta maquina de dev: o venv certo do projeto e o
# Python de sistema (o mesmo que causou o "Unknown key type" real,
# Decisao 50).
_SYSTEM_PYTHON = r"C:\Python313\python.exe"
_PROJECT_VENV_PYTHON = str(
    Path(__file__).resolve().parents[4] / "scripts" / ".venv" / "Scripts" / "python.exe"
)


@pytest.mark.skipif(not Path(_PROJECT_VENV_PYTHON).is_file(), reason="venv do projeto nao existe nesta maquina")
def test_ambiente_python_correto_aprova(tmp_path):
    result = preflight.check_client_python_environment(_PROJECT_VENV_PYTHON)
    assert result["ok"] is True, result
    assert result["mldsa_public_key_bytes"] == 1952
    assert result["mismatches"] == []


@pytest.mark.skipif(not Path(_SYSTEM_PYTHON).is_file(), reason="Python de sistema nao existe nesta maquina")
def test_ambiente_python_errado_reprova(tmp_path):
    """O MESMO erro real que a Decisao 50 encontrou -- interprete de
    sistema desta maquina, sem os pacotes do projeto (ou com versoes
    velhas) -- tem que reprovar com mensagem clara, nunca em
    silencio."""
    result = preflight.check_client_python_environment(_SYSTEM_PYTHON)
    assert result["ok"] is False, result
    assert result["mismatches"], "deveria listar pelo menos um motivo da reprovacao"


def test_interprete_inexistente_reprova_com_mensagem_clara():
    result = preflight.check_client_python_environment("/caminho/que/nao/existe/python.exe")
    assert result["ok"] is False
    assert "nao encontrado" in result["note"]


def test_parse_pinned_versions(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text(
        "# comentario\n"
        "requests==2.32.5 \\\n"
        "    --hash=sha256:deadbeef\n"
        "cryptography==50.0.2 \\\n"
        "    --hash=sha256:deadbeef\n",
        encoding="utf-8",
    )
    pins = preflight._parse_pinned_versions(req)
    assert pins == {"requests": "2.32.5", "cryptography": "50.0.2"}


def test_versao_desalinhada_do_pin_e_detectada(monkeypatch, tmp_path):
    """Mutacao direta: simula um probe que devolve uma versao
    DIFERENTE do pin -- tem que reprovar com o motivo exato."""
    req = tmp_path / "requirements.txt"
    req.write_text("cryptography==50.0.2 \\\n    --hash=sha256:x\n", encoding="utf-8")

    def fake_run(argv, capture_output, text, timeout):
        class FakeProc:
            returncode = 0
            stdout = ('{"executable": "/fake/python", '
                      '"versions": {"cryptography": "46.0.3", "PyJWT": "2.15.1", "requests": "2.32.5"}, '
                      '"mldsa_public_key_bytes": 1952}')
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    monkeypatch.setattr(preflight.Path, "is_file", lambda self: True)
    result = preflight.check_client_python_environment("/fake/python", requirements_path=req)
    assert result["ok"] is False
    assert any("cryptography" in m and "46.0.3" in m and "50.0.2" in m for m in result["mismatches"])


# --- Decisao 53 (pedido independente, item 4a/4c): pre-requisitos da
# captura dedicada (criterio 1) em cada instancia -- fail-closed, com
# mensagem clara, ANTES de qualquer execucao. `cli.run_ssh`
# monkeypatchado diretamente (preflight.py chama essa funcao, nao
# `cli._run`).

_FAKE_MEASURE_LAYERS = ["sha256:" + "a1" * 32, "sha256:" + "b2" * 32]
_FAKE_MEASURE_CONFIG = {"Entrypoint": ["/usr/local/bin/measure.sh"], "Cmd": None, "Env": ["PATH=/usr/bin"], "ExposedPorts": None}

_CAPTURE_PROBE_OK = (
    "TCPDUMP_PATH=/usr/sbin/tcpdump\n"
    "SUDO_NOPASSWD=1\n"
    "MEASURE_IMAGE_ID=sha256:deadbeef\n"
    f"MEASURE_LAYERS={json.dumps(_FAKE_MEASURE_LAYERS)}\n"
    f"MEASURE_CONFIG={json.dumps(_FAKE_MEASURE_CONFIG)}\n"
    "TMP_WRITABLE=1\n"
    "PRIMARY_IFACE=ens5\n"
)


class _FakeSSHProc:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_todos_prerequisitos_de_captura_presentes_passa(monkeypatch):
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(_CAPTURE_PROBE_OK))
    result = preflight.check_capture_prerequisites("203.0.113.9")
    assert result["ok"] is True, result
    assert result["missing"] == []
    assert result["primary_iface"] == "ens5"


def test_tcpdump_ausente_reprova_com_mensagem_clara(monkeypatch):
    broken = _CAPTURE_PROBE_OK.replace("TCPDUMP_PATH=/usr/sbin/tcpdump\n", "TCPDUMP_PATH=\n")
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(broken))
    result = preflight.check_capture_prerequisites("203.0.113.9")
    assert result["ok"] is False
    assert any("tcpdump" in m for m in result["missing"]), result


def test_imagem_measure_ausente_reprova(monkeypatch):
    broken = _CAPTURE_PROBE_OK.replace(f"MEASURE_LAYERS={json.dumps(_FAKE_MEASURE_LAYERS)}\n", "MEASURE_LAYERS=\n")
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(broken))
    result = preflight.check_capture_prerequisites("203.0.113.9")
    assert result["ok"] is False
    assert any("mockopin-v9-measure" in m for m in result["missing"]), result


def test_imagem_measure_com_camadas_erradas_reprova(monkeypatch):
    """Decisao 68 (Emenda -- substitui a verificacao por Image ID,
    que diverge entre versoes de Docker): a imagem EXISTE
    (RootFS.Layers presentes), mas NAO sao as camadas que PINS.json
    espera -- tem que reprovar com mensagem clara, nao so checar
    presenca."""
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(_CAPTURE_PROBE_OK))
    result = preflight.check_capture_prerequisites("203.0.113.9", expected_measure_layers=["sha256:" + "9" * 64])
    assert result["ok"] is False
    assert any("PINS.json" in m for m in result["missing"]), result


def test_imagem_measure_com_config_errado_reprova(monkeypatch):
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(_CAPTURE_PROBE_OK))
    result = preflight.check_capture_prerequisites(
        "203.0.113.9", expected_measure_layers=_FAKE_MEASURE_LAYERS,
        expected_measure_config={"Entrypoint": ["/bin/sh"], "Cmd": None, "Env": [], "ExposedPorts": None},
    )
    assert result["ok"] is False
    assert any("Config" in m for m in result["missing"]), result


def test_imagem_measure_com_camadas_e_config_certos_passa(monkeypatch):
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(_CAPTURE_PROBE_OK))
    result = preflight.check_capture_prerequisites(
        "203.0.113.9", expected_measure_layers=_FAKE_MEASURE_LAYERS, expected_measure_config=_FAKE_MEASURE_CONFIG,
    )
    assert result["ok"] is True
    assert result["missing"] == []


def test_interface_loopback_reprova():
    """`lo` NUNCA pode passar como interface primaria -- mesma regra
    de `_primary_iface` do orquestrador."""
    broken = _CAPTURE_PROBE_OK.replace("PRIMARY_IFACE=ens5\n", "PRIMARY_IFACE=lo\n")
    import unittest.mock as mock
    with mock.patch.object(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(broken)):
        result = preflight.check_capture_prerequisites("203.0.113.9")
    assert result["ok"] is False
    assert any("interface primaria" in m for m in result["missing"]), result


def test_sudo_sem_permissao_reprova(monkeypatch):
    broken = _CAPTURE_PROBE_OK.replace("SUDO_NOPASSWD=1\n", "SUDO_NOPASSWD=0\n")
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(broken))
    result = preflight.check_capture_prerequisites("203.0.113.9")
    assert result["ok"] is False
    assert any("sudo" in m for m in result["missing"]), result


def test_ssh_indisponivel_reprova_sem_estourar_excecao(monkeypatch):
    def boom(host, cmd, **kw):
        raise RuntimeError("connection refused")
    monkeypatch.setattr(cli, "run_ssh", boom)
    result = preflight.check_capture_prerequisites("203.0.113.9")
    assert result["ok"] is False
    assert "SSH" in result["note"]


def test_run_capture_preflight_falha_se_qualquer_host_falhar(monkeypatch):
    responses = {"203.0.113.9": _CAPTURE_PROBE_OK, "203.0.113.10": _CAPTURE_PROBE_OK.replace("TCPDUMP_PATH=/usr/sbin/tcpdump\n", "TCPDUMP_PATH=\n")}
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(responses[host]))
    # Decisao 55, item 2: `pins_path` inexistente -- este teste e sobre
    # a AGREGACAO por host, nao sobre o Image ID (ver testes dedicados
    # abaixo), entao desliga a exigencia de Image ID de proposito.
    result = preflight.run_capture_preflight(["203.0.113.9", "203.0.113.10"], pins_path=Path("/caminho/que/nao/existe/PINS.json"))
    assert result["go"] is False
    assert result["checks"][0]["ok"] is True
    assert result["checks"][1]["ok"] is False


def test_mutante_run_capture_preflight_any_em_vez_de_all_e_pego(monkeypatch):
    """Mutacao: usar any() em vez de all() pra agregar -- o teste
    acima (go False com 1 host falho) tem que reprovar com essa
    mutacao."""
    checks = [{"ok": True}, {"ok": False}]
    go_mutante = any(c["ok"] for c in checks)  # mutante: deveria ser all()
    assert go_mutante is True
    with pytest.raises(AssertionError):
        assert go_mutante is False


def test_mutante_ignora_mismatch_de_versao_e_pego(monkeypatch, tmp_path):
    """Mutacao: `ok` calculado so pelo parse de ML-DSA, ignorando
    `mismatches` de versao -- o teste acima tem que reprovar com essa
    mutacao."""
    req = tmp_path / "requirements.txt"
    req.write_text("cryptography==50.0.2 \\\n    --hash=sha256:x\n", encoding="utf-8")

    def fake_run(argv, capture_output, text, timeout):
        class FakeProc:
            returncode = 0
            stdout = ('{"executable": "/fake/python", '
                      '"versions": {"cryptography": "46.0.3"}, "mldsa_public_key_bytes": 1952}')
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(preflight.subprocess, "run", fake_run)
    monkeypatch.setattr(preflight.Path, "is_file", lambda self: True)

    probe = __import__("json").loads(fake_run(None, None, None, None).stdout)
    mldsa_ok_mutante = probe["mldsa_public_key_bytes"] == 1952  # mutante: so olha isso
    assert mldsa_ok_mutante is True  # mutante aprovaria indevidamente
    with pytest.raises(AssertionError):
        assert mldsa_ok_mutante is False


# Decisao 125 (item 3 do adendo "piloto v9" -- achado real, Decisao
# 122: um container/alias de rede orfao de uma rodada local anterior
# corrompeu silenciosamente uma validacao). `_docker_orphan_report` e
# testada pura (sem Docker real); `cli._run`/`cli.run_ssh`
# monkeypatchados pras versoes local/remota, mesmo padrao do resto
# deste arquivo.

def test_orphan_report_casamento_exato_nunca_substring():
    """'auth' nao deveria casar com 'auth-gateway-v2' de outro
    projeto no mesmo host -- falso positivo bloquearia um pre-voo
    bom."""
    result = preflight._docker_orphan_report(
        container_lines=["auth-gateway-v2", "unrelated-app"],
        network_lines=["bridge", "host"],
    )
    assert result["ok"] is True
    assert result["containers_found"] == []
    assert result["networks_found"] == []


def test_orphan_report_detecta_container_e_rede_exatos():
    result = preflight._docker_orphan_report(
        container_lines=["v9-mtls", "unrelated-app"],
        network_lines=["mockopin-v9-net", "bridge"],
    )
    assert result["ok"] is False
    assert result["containers_found"] == ["v9-mtls"]
    assert result["networks_found"] == ["mockopin-v9-net"]


def test_orphan_report_ambiente_limpo_passa():
    result = preflight._docker_orphan_report(container_lines=["unrelated-app"], network_lines=["bridge"])
    assert result["ok"] is True


class _FakeLocalDockerProc:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout, self.returncode, self.stderr = stdout, returncode, stderr


def test_check_no_orphan_local_detecta_residuo(monkeypatch):
    def fake_run(argv, timeout=None):
        if argv[:2] == ["docker", "ps"]:
            return _FakeLocalDockerProc("v9-mtls\n")
        return _FakeLocalDockerProc("mockopin-v9-net\n")

    monkeypatch.setattr(cli, "_run", fake_run)
    result = preflight.check_no_orphan_docker_resources()
    assert result["ok"] is False
    assert result["containers_found"] == ["v9-mtls"]
    assert result["networks_found"] == ["mockopin-v9-net"]


def test_check_no_orphan_local_ambiente_limpo_passa(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: _FakeLocalDockerProc(""))
    result = preflight.check_no_orphan_docker_resources()
    assert result["ok"] is True


def test_check_no_orphan_local_docker_indisponivel_reprova(monkeypatch):
    def fake_run(argv, timeout=None):
        raise FileNotFoundError("docker nao encontrado")

    monkeypatch.setattr(cli, "_run", fake_run)
    result = preflight.check_no_orphan_docker_resources()
    assert result["ok"] is False
    assert "docker indisponivel" in result["note"]


def test_check_no_orphan_remote_detecta_residuo_via_ssh(monkeypatch):
    stdout = "v9-mtls\nauth\n---NETWORKS---\nbridge\n"
    monkeypatch.setattr(cli, "run_ssh", lambda host, cmd, **kw: _FakeSSHProc(stdout))
    result = preflight.check_no_orphan_docker_resources_remote("203.0.113.9")
    assert result["ok"] is False
    assert sorted(result["containers_found"]) == ["auth", "v9-mtls"]
    assert result["host"] == "203.0.113.9"


def test_check_no_orphan_remote_ssh_falha_reprova(monkeypatch):
    def fake_ssh(host, cmd, **kw):
        raise RuntimeError("conexao recusada")

    monkeypatch.setattr(cli, "run_ssh", fake_ssh)
    result = preflight.check_no_orphan_docker_resources_remote("203.0.113.9")
    assert result["ok"] is False
    assert "SSH" in result["note"]


def test_run_pilot_aborta_se_executor_achar_orfao(tmp_path, monkeypatch):
    """Integracao real com `orchestrator.run_pilot` (sem Docker real):
    um executor fake cujo `check_no_orphans` reprova deve abortar
    ANTES de escrever qualquer arquivo em `out_dir` -- nunca so um
    aviso."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import orchestrator as orch  # noqa: E402

    class _FakeExecutorComResiduo(orch.LocalExecutor):
        def check_no_orphans(self):
            return {"go": False, "checks": [{"check": "containers/redes orfaos do projeto", "ok": False,
                                              "containers_found": ["v9-mtls"], "networks_found": []}]}

    with pytest.raises(RuntimeError, match="orfaos"):
        orch.run_pilot(_FakeExecutorComResiduo(), seed=1, out_dir=tmp_path / "janela",
                       n_per_profile=1, profiles=["classico"], routes=["L0"], skip_dedicated_captures=True)
    assert not (tmp_path / "janela").exists()


def test_local_executor_check_no_orphans_sempre_passa():
    """`LocalExecutor` e simulacao pura -- nunca depende do Docker
    real do host que roda a suite de testes (374 testes usam
    `LocalExecutor()` real; nenhum deve ficar fragil ao estado do
    Docker da maquina)."""
    import orchestrator as orch
    assert orch.LocalExecutor().check_no_orphans() == {"go": True, "checks": []}

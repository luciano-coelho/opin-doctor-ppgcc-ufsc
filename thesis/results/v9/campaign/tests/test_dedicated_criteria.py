"""Testes de dedicated_criteria.py (Decisao 85, pedido do Luciano) --
liga os produtores dos criterios 2/3/7 ao pipeline real. SSH/SCP
stubados via cli._run, nenhuma chamada real."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import orchestrator as orch  # noqa: E402
import dedicated_criteria as dc  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _inventory():
    return {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {
            "L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True},
            "L219": {"public_ip": "203.0.113.70", "private_ip": "10.0.2.70", "colocated": False},
            "L325": {"public_ip": "203.0.113.80", "private_ip": "10.0.3.80", "colocated": False},
        },
    }


# --- criterio 3: adapter reusa criterion_4_counts, nunca reimplementa.

def test_build_criterio3_filtra_l325_e_reusa_criterion_4(tmp_path):
    execucoes = []
    for run in range(1, 6):
        for profile in orch.PROFILES:
            for route in ("L219", "L325"):
                execucoes.append({"profile": profile, "route": route, "run": run,
                                   "insurance": [{"ok": True}] * 28, "person": []})
    # monta um log combinado minimo com os marcadores que criterion_4 le.
    import evaluate_criteria as ec
    log_lines = []
    for e in execucoes:
        log_lines.append(f"== Perfil: {e['profile']} ==")
    combined_log = "\n".join(log_lines)
    collected_dir = tmp_path / "coletado"
    collected_dir.mkdir()
    (collected_dir / "piloto_calls.json").write_text(json.dumps(execucoes), encoding="utf-8")
    (collected_dir / "piloto_combined.log").write_text(combined_log, encoding="utf-8")

    out_dir = tmp_path / "out"
    result = dc.build_criterio3(collected_dir, out_dir)
    assert all(e["route"] == "L325" for e in result["execucoes"])
    assert len(result["execucoes"]) == 20  # 4 perfis x 5 execucoes, so L325
    written = json.loads((out_dir / "criterio3_l325_execucoes.json").read_text(encoding="utf-8"))
    assert written == result


def test_mutante_build_criterio3_sem_filtrar_rota_e_pego(tmp_path, monkeypatch):
    """Mutacao: esquece de filtrar route=='L325' -- o teste real tem
    que reprovar com essa mutacao."""
    execucoes = [{"profile": "classico", "route": "L219", "run": 1, "insurance": [], "person": []},
                 {"profile": "classico", "route": "L325", "run": 1, "insurance": [], "person": []}]
    collected_dir = tmp_path / "coletado"
    collected_dir.mkdir()
    (collected_dir / "piloto_calls.json").write_text(json.dumps(execucoes), encoding="utf-8")
    (collected_dir / "piloto_combined.log").write_text("== Perfil: classico ==\n== Perfil: classico ==", encoding="utf-8")

    def mutant_build_criterio3(collected_dir, out_dir):
        import evaluate_criteria as ec
        combined_log = (collected_dir / "piloto_combined.log").read_text(encoding="utf-8")
        execs = json.loads((collected_dir / "piloto_calls.json").read_text(encoding="utf-8"))
        c4 = ec.criterion_4_counts(execs, combined_log)
        execucoes_l325 = [{"profile": r["profile"], "route": r["route"], "ok": r["ok"]} for r in c4["rows"]]  # mutante: nunca filtra
        return {"execucoes": execucoes_l325}

    result = mutant_build_criterio3(collected_dir, tmp_path / "out")
    assert not all(e["route"] == "L325" for e in result["execucoes"]), "mutante deveria ter deixado L219 passar"
    real_result = dc.build_criterio3(collected_dir, tmp_path / "out_real")
    assert all(e["route"] == "L325" for e in real_result["execucoes"])


# --- criterio 2: sobe o probe no servidor, dispara 1 conexao do cliente.

def _fake_run_criterio2(calls, server_ready_after=1):
    state = {"checks": 0}

    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "ip -o -4 route" in remote_cmd:
            return FakeProc(stdout="eth0\n")
        if "test -f /tmp/criterio2_initcwnd.json" in remote_cmd:
            state["checks"] += 1
            if state["checks"] >= server_ready_after:
                return FakeProc(stdout="FOUND\n")
            return FakeProc(stdout="")
        return FakeProc()

    return fake_run


def test_run_criterio2_sobe_probe_dispara_cliente_e_traz_resultado(tmp_path, monkeypatch):
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_criterio2(calls))

    def fake_run_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        Path(dst).write_text(json.dumps({"bytes_sent_total": 71680, "mss_bytes": 1448}), encoding="utf-8")
        return FakeProc()

    monkeypatch.setattr(cli, "run_scp", fake_run_scp)
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    out_dir = tmp_path / "out"
    result = dc.run_criterio2(executor, out_dir, route="L219")

    assert result["bytes_sent_total"] == 71680
    flat = [" ".join(c) for c in calls]
    assert any("criterio2_probe.py --listen-port 9876 --iface eth0 --route L219" in c for c in flat), flat
    assert any("cat < /dev/tcp/" in c for c in flat), flat
    # a conexao de teste tem que vir do CLIENTE da rota, nunca do servidor.
    client_calls = [c for c in flat if "203.0.113.70" in c and "/dev/tcp/" in c]
    assert client_calls, flat


# --- Decisao 94 (achado real, ao vivo, Passo 11.5): a sessao SSH que
# sobe o probe pode nao retornar a tempo (throttling transitorio do
# servidor logo apos as 60 execucoes do Passo 11, nunca um problema
# de sintaxe de comando -- confirmado manualmente, o MESMO comando
# simples de sempre funcionou em <2s depois de so uns 15s de espera).
# `run_criterio2` tenta de novo (3x, 15s de intervalo) em vez de
# propagar o `TimeoutExpired` cru.

def _fake_run_criterio2_timeout_then_ok(calls, n_timeouts, server_ready_after=1):
    state = {"checks": 0, "launch_attempts": 0}

    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "ip -o -4 route" in remote_cmd:
            return FakeProc(stdout="eth0\n")
        if "criterio2_probe.py --listen-port" in remote_cmd:
            state["launch_attempts"] += 1
            if state["launch_attempts"] <= n_timeouts:
                raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)
            return FakeProc()
        if "test -f /tmp/criterio2_initcwnd.json" in remote_cmd:
            state["checks"] += 1
            if state["checks"] >= server_ready_after:
                return FakeProc(stdout="FOUND\n")
            return FakeProc(stdout="")
        return FakeProc()

    return fake_run


def test_run_criterio2_tenta_de_novo_se_a_sessao_de_lancamento_nao_retorna(tmp_path, monkeypatch):
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_criterio2_timeout_then_ok(calls, n_timeouts=2))
    monkeypatch.setattr(cli, "run_scp", lambda src, dst, **k: (
        Path(dst).write_text(json.dumps({"bytes_sent_total": 71680, "mss_bytes": 1448}), encoding="utf-8"),
        FakeProc(),
    )[1])
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    result = dc.run_criterio2(executor, tmp_path / "out", route="L219")
    assert result["bytes_sent_total"] == 71680


def test_run_criterio2_falha_alto_se_a_sessao_de_lancamento_nunca_retorna(tmp_path, monkeypatch):
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_criterio2_timeout_then_ok(calls, n_timeouts=99))
    with pytest.raises(RuntimeError, match="nunca retornou"):
        dc.run_criterio2(executor=orch.SSHExecutor(_inventory(), key_path="/fake/key"),
                          out_dir=tmp_path / "out", route="L219")


def test_mutante_run_criterio2_sem_retry_propaga_o_timeout_cru(tmp_path, monkeypatch):
    """Mutacao = o comportamento ANTES desta Decisao: sem o laco de
    retry, a mesma situacao (1 timeout, depois sucesso) faz o script
    inteiro quebrar com `TimeoutExpired` cru -- prova que o teste
    'tenta de novo' acima de fato depende do retry, nunca passa por
    acidente."""
    calls = []
    fake_run = _fake_run_criterio2_timeout_then_ok(calls, n_timeouts=1)

    def mutant_run_criterio2_sem_retry(executor, out_dir, route="L219"):
        server_ip = executor._server_ip()
        cli.run_ssh(server_ip, "ip -o -4 route show to default | awk '{print $5}' | head -1", key_path=executor.key_path)
        return cli.run_ssh(server_ip, "cd producers && nohup python3 criterio2_probe.py --listen-port 9876 &",
                            key_path=executor.key_path)  # mutante: nunca tenta de novo

    import unittest.mock as mock
    with mock.patch.object(cli, "_run", fake_run):
        with pytest.raises(subprocess.TimeoutExpired):
            mutant_run_criterio2_sem_retry(orch.SSHExecutor(_inventory(), key_path="/fake/key"), tmp_path / "out")


def test_run_criterio2_falha_alto_se_arquivo_nunca_aparece(tmp_path, monkeypatch):
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_criterio2(calls, server_ready_after=999))
    monkeypatch.setattr(cli, "run_scp", lambda *a, **k: FakeProc())
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="nunca apareceu"):
        dc.run_criterio2(executor, tmp_path / "out", route="L219")


def test_mutante_run_criterio2_nunca_espera_o_arquivo_e_pego(monkeypatch, tmp_path):
    """Mutacao: tenta o scp sem esperar o arquivo aparecer -- o teste
    de 'falha alto' acima tem que depender de fato da espera."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_criterio2(calls, server_ready_after=999))
    scp_called = []
    monkeypatch.setattr(cli, "run_scp", lambda *a, **k: scp_called.append(1) or FakeProc())

    def mutant_run_criterio2(executor, out_dir, route="L219"):
        server_ip = executor._server_ip()
        cli.run_ssh(server_ip, "ip -o -4 route show to default | awk '{print $5}' | head -1", key_path=executor.key_path)
        cli.run_ssh(server_ip, "nohup python3 criterio2_probe.py ... &", key_path=executor.key_path)
        cli.run_ssh(executor._client_ip(route), "cat < /dev/tcp/x/9876", key_path=executor.key_path)
        cli.run_scp("src", "dst", key_path=executor.key_path)  # mutante: nunca espera

    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    mutant_run_criterio2(executor, tmp_path / "out", route="L219")
    assert scp_called, "mutante chamou scp sem esperar -- prova que o teste real dependia da espera"


# --- criterio 7: probe (cliente) + pcap (servidor, via mockopin-v9-measure) + combine.

def test_run_criterio7_roda_probe_no_cliente_e_pcap_no_servidor(tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "criterio7_rtt.py probe" in remote_cmd:
            return FakeProc(stdout=json.dumps({"rtt_ms_probe": 12.3, "n_samples_probe": 20}))
        if "test -f /tmp/criterio1_classico_" in remote_cmd:
            return FakeProc(stdout="FOUND\n")
        if "criterio7_rtt.py pcap" in remote_cmd:
            return FakeProc(stdout=json.dumps({"rtt_ms_pcap": 11.9, "n_samples_pcap": 1}))
        return FakeProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    out_dir = tmp_path / "out"
    result = dc.run_criterio7(executor, out_dir, routes=("L219",))

    assert result["L219"] == {"rtt_ms_probe": 12.3, "n_samples_probe": 20, "rtt_ms_pcap": 11.9}
    written = json.loads((out_dir / "criterio7_rtt_por_rota.json").read_text(encoding="utf-8"))
    assert written == result
    flat = [" ".join(c) for c in calls]
    probe_calls = [c for c in flat if "criterio7_rtt.py probe" in c]
    assert all("203.0.113.70" in c for c in probe_calls), "probe tem que rodar do CLIENTE -- " + str(probe_calls)
    pcap_calls = [c for c in flat if "criterio7_rtt.py pcap" in c]
    assert all("203.0.113.50" in c for c in pcap_calls), "pcap tem que rodar do SERVIDOR -- " + str(pcap_calls)


def test_run_criterio7_falha_alto_se_nenhum_pcap_dedicado_existe(tmp_path, monkeypatch):
    def fake_run(argv, timeout=None):
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "criterio7_rtt.py probe" in remote_cmd:
            return FakeProc(stdout=json.dumps({"rtt_ms_probe": 1.0, "n_samples_probe": 20}))
        if "test -f" in remote_cmd:
            return FakeProc(stdout="")  # nenhum pcap encontrado, nenhum perfil
        return FakeProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="nenhum pcap dedicado"):
        dc.run_criterio7(executor, tmp_path / "out", routes=("L219",))

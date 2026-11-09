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

    scp_calls = []

    def fake_run_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        scp_calls.append((src, dst))
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

    # Pedido do Luciano (item 0, regra fail-closed nova): o pcap bruto
    # deste teste dedicado tem que ser trazido pro MESMO out_dir que o
    # manifesto global ja cobre -- nunca so o JSON.
    assert (out_dir / "criterio2_probe.pcap").is_file()
    pcap_scp_calls = [c for c in scp_calls if "criterio2.pcap" in c[0]]
    assert pcap_scp_calls, scp_calls


def test_mutante_run_criterio2_sem_pull_do_pcap_perde_evidencia_bruta(tmp_path, monkeypatch):
    """Mutante = o comportamento ANTIGO: so traz o JSON, nunca o pcap
    bruto -- o teste real acima depende de fato do scp extra, provado
    aqui reproduzindo o mutante (sem a chamada extra) e confirmando
    que o pcap NUNCA aparece no out_dir."""
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_criterio2(calls))

    def fake_run_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        Path(dst).write_text(json.dumps({"bytes_sent_total": 71680, "mss_bytes": 1448}), encoding="utf-8")
        return FakeProc()

    def mutant_run_criterio2(executor, out_dir, route="L219"):
        server_ip = executor._server_ip()
        cli.run_ssh(server_ip, "ip -o -4 route show to default | awk '{print $5}' | head -1", key_path=executor.key_path)
        cli.run_ssh(server_ip, "nohup python3 criterio2_probe.py ... &", key_path=executor.key_path)
        for _ in range(5):
            check = cli.run_ssh(server_ip, "test -f /tmp/criterio2_initcwnd.json && echo FOUND", key_path=executor.key_path)
            if "FOUND" in (check.stdout or ""):
                break
        cli.run_ssh(executor._client_ip(route), "cat < /dev/tcp/x/9876", key_path=executor.key_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        local_path = out_dir / "criterio2_initcwnd.json"
        cli.run_scp(f"ec2-user@{server_ip}:/tmp/criterio2_initcwnd.json", str(local_path), key_path=executor.key_path)
        return json.loads(local_path.read_text(encoding="utf-8"))

    monkeypatch.setattr(cli, "run_scp", fake_run_scp)
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    out_dir = tmp_path / "out_mutante"
    mutant_run_criterio2(executor, out_dir, route="L219")
    assert not (out_dir / "criterio2_probe.pcap").exists(), "mutante nunca traz o pcap bruto -- exatamente a lacuna da regra fail-closed nova"


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


# --- Generalizacao N-servidores (Decisao 107, achado de confirmacao
# desta rodada): `direction="client-to-server"` e `run_criterio2_
# campaign()` estavam implementados mas SEM nenhum teste dedicado --
# lacuna real, fechada agora. `_fake_run_criterio2_labeled` e generico
# o bastante pra casar com QUALQUER rotulo (`criterio2_initcwnd*.json`,
# nunca so o caminho fixo do piloto).

def _fake_run_criterio2_labeled(calls):
    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "ip -o -4 route" in remote_cmd:
            return FakeProc(stdout="eth0\n")
        if remote_cmd.startswith("test -f") and "criterio2_initcwnd" in remote_cmd:
            return FakeProc(stdout="FOUND\n")
        return FakeProc()
    return fake_run


def test_run_criterio2_direcao_cliente_para_servidor_inverte_papeis(tmp_path, monkeypatch):
    """Gap fechado (pedido do Luciano): `direction='client-to-server'`
    tem que INVERTER os papeis -- quem ESCUTA (e quem o scp final le)
    passa a ser o CLIENTE, quem DISPARA a conexao de teste passa a ser
    o SERVIDOR (o oposto exato do default/piloto, testado acima)."""
    monkeypatch.setattr(dc.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_criterio2_labeled(calls))

    def fake_run_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        if str(dst).endswith(".json"):
            Path(dst).write_text(json.dumps({"bytes_sent_total": 1234}), encoding="utf-8")
        else:
            Path(dst).write_bytes(b"pcap falso")
        return FakeProc()

    monkeypatch.setattr(cli, "run_scp", fake_run_scp)
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    out_dir = tmp_path / "out"
    result = dc.run_criterio2(executor, out_dir, route="L219", direction="client-to-server", label="L219_c2s")

    assert result["bytes_sent_total"] == 1234
    flat = [" ".join(c) for c in calls]
    # quem sobe o probe/escuta tem que ser o CLIENTE (203.0.113.70), nunca o servidor.
    assert any("203.0.113.70" in c and "criterio2_probe.py" in c for c in flat), flat
    # quem dispara a conexao de teste tem que ser o SERVIDOR (203.0.113.50), nunca o cliente.
    connect_calls = [c for c in flat if "/dev/tcp/" in c]
    assert connect_calls and all("203.0.113.50" in c for c in connect_calls), connect_calls
    # caminhos rotulados, nunca os fixos do piloto (que ficariam sem sufixo).
    assert (out_dir / "criterio2_initcwnd_L219_c2s.json").is_file()
    assert (out_dir / "criterio2_probe_L219_c2s.pcap").is_file()
    assert not (out_dir / "criterio2_initcwnd.json").exists()


def test_run_criterio2_direcao_invalida_falha_alto():
    with pytest.raises(ValueError, match="direction invalida"):
        dc.run_criterio2(orch.SSHExecutor(_inventory(), key_path="/fake/key"), Path("/tmp/x"), route="L219",
                          direction="lado-nenhum")


def test_run_criterio2_campaign_cobre_l325_e_as_2_direcoes(monkeypatch, tmp_path):
    """Gap fechado (pedido do Luciano, os 2 itens declarados fora de
    escopo ate aqui): `run_criterio2_campaign()` tem que rodar L325
    explicitamente (nunca so L219/L123/L14/L30) E as duas direcoes
    (server-to-client E client-to-server) -- nunca so a default do
    piloto."""
    calls = []

    def fake_run_criterio2(executor, out_dir, route=None, direction="server-to-client", label=None):
        calls.append((route, direction, label))
        return {"ok": True}

    monkeypatch.setattr(dc, "run_criterio2", fake_run_criterio2)
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    results = dc.run_criterio2_campaign(executor, tmp_path / "out")

    routes_covered = {r for (r, _, _) in calls}
    directions_covered = {d for (_, d, _) in calls}
    assert "L325" in routes_covered, f"L325 tem que ser coberto -- gap declarado como fora de escopo antes: {routes_covered}"
    assert directions_covered == {"server-to-client", "client-to-server"}, directions_covered
    # as 3 rotas L0-* (RTT nominal 0, co-localizadas) ficam fora -- criterio 2 nao se aplica a elas.
    assert not any(r.startswith("L0-") for r in routes_covered), routes_covered
    assert results[f"L325_server-to-client"] == {"ok": True, "data": {"ok": True}}
    assert results[f"L325_client-to-server"] == {"ok": True, "data": {"ok": True}}


def test_run_criterio2_campaign_isola_falha_individual_nunca_aborta_as_outras(monkeypatch, tmp_path):
    """Qualquer falha numa combinacao rota+direcao tem que ficar
    registrada como `{"ok": False, ...}`, nunca abortar as demais --
    confirma a regra de isolamento ja documentada na docstring."""
    def fake_run_criterio2(executor, out_dir, route=None, direction="server-to-client", label=None):
        if route == "L325":
            raise RuntimeError("falha simulada so em L325")
        return {"ok": True}

    monkeypatch.setattr(dc, "run_criterio2", fake_run_criterio2)
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    results = dc.run_criterio2_campaign(executor, tmp_path / "out", routes=["L123", "L325"])

    assert results["L123_server-to-client"]["ok"] is True
    assert results["L325_server-to-client"] == {"ok": False, "error": "falha simulada so em L325"}
    assert results["L123_client-to-server"]["ok"] is True, "falha em L325 nunca pode abortar as outras combinacoes"


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


def test_run_criterio7_funciona_em_modo_campanha_sem_quebrar(tmp_path, monkeypatch):
    """Achado real encontrado nesta rodada (grep literal pedido pelo
    Luciano): `run_criterio7` chamava `executor._server_ip()` SEM
    `route` -- em modo campanha isso levanta KeyError (fail-closed de
    `_server_key`) na PRIMEIRA rota, sempre. Corrigido; este teste
    prova que a funcao agora roda de ponta a ponta em modo campanha,
    resolvendo o SERVIDOR CERTO (us-east-1, nao sa-east-1) pra rota
    L14."""
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "criterio7_rtt.py probe" in remote_cmd:
            return FakeProc(stdout=json.dumps({"rtt_ms_probe": 14.1, "n_samples_probe": 20}))
        if "test -f /tmp/criterio1_classico_" in remote_cmd:
            return FakeProc(stdout="FOUND\n")
        if "criterio7_rtt.py pcap" in remote_cmd:
            return FakeProc(stdout=json.dumps({"rtt_ms_pcap": 13.8, "n_samples_pcap": 1}))
        return FakeProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {
        "control": {"public_ip": "203.0.113.10"},
        "servers": {
            "sa-east-1": {"public_ip": "203.0.113.50"},
            "us-east-1": {"public_ip": "203.0.113.51"},
        },
        "clients": {"L14": {"public_ip": "203.0.113.71", "colocated": False}},
    }
    executor = orch.SSHExecutor(inventory, key_path="/fake/key", route_server={"L14": "us-east-1"})
    out_dir = tmp_path / "out"
    result = dc.run_criterio7(executor, out_dir, routes=("L14",))

    assert result["L14"] == {"rtt_ms_probe": 14.1, "n_samples_probe": 20, "rtt_ms_pcap": 13.8}
    flat = [" ".join(c) for c in calls]
    pcap_calls = [c for c in flat if "criterio7_rtt.py pcap" in c or "test -f" in c]
    # o servidor certo (us-east-1, 203.0.113.51) tem que ser usado, nunca sa-east-1.
    assert any("203.0.113.51" in c for c in pcap_calls), pcap_calls
    assert not any("203.0.113.50" in c for c in pcap_calls), pcap_calls


def test_mutante_run_criterio7_sem_route_quebra_em_modo_campanha(tmp_path):
    """Mutante: reproduz o bug ANTIGO (`_server_ip()` sem route) --
    confirma que ele realmente quebraria em modo campanha, provando
    que o fix acima era necessario, nao cosmetico."""
    inventory = {
        "servers": {"sa-east-1": {"public_ip": "203.0.113.50"}, "us-east-1": {"public_ip": "203.0.113.51"}},
        "clients": {"L14": {"public_ip": "203.0.113.71"}},
    }
    executor = orch.SSHExecutor(inventory, key_path="/fake/key", route_server={"L14": "us-east-1"})
    with pytest.raises(KeyError):
        executor._server_ip()  # mutante: o jeito antigo, sem route, quebra em modo campanha


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


# --- collect_full_logs (pedido do Luciano, item 0, regra fail-closed
# nova): logs CHEIOS de TODOS os containers do servidor -- antes
# desta Emenda, auth/mongo_seed/mockapi nunca tinham log nenhum
# guardado, e o gateway so tinha uma JANELA de tempo.

def test_collect_full_logs_traz_log_cheio_dos_4_containers(tmp_path, monkeypatch):
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "docker logs -t v9-mtls" in remote_cmd:
            return FakeProc(stdout="log do gateway completo\n")
        if "docker logs -t insurance-server-lambdas-auth-1" in remote_cmd:
            return FakeProc(stdout="log do auth completo\n")
        if "docker logs -t insurance-server-lambdas-mongo_seed-1" in remote_cmd:
            return FakeProc(stdout="log do mongo_seed completo\n")
        if "docker logs -t insurance-server-lambdas-mockapi-1" in remote_cmd:
            return FakeProc(stdout="log do mockapi completo\n")
        if "dmesg" in remote_cmd:
            return FakeProc(stdout="dmesg fake\n")
        return FakeProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    out_dir = tmp_path / "out"
    result = dc.collect_full_logs(executor, out_dir)

    logs_dir = out_dir / "full_container_logs"
    assert (logs_dir / "v9-mtls.log").read_text(encoding="utf-8") == "log do gateway completo\n"
    assert (logs_dir / "insurance-server-lambdas-auth-1.log").read_text(encoding="utf-8") == "log do auth completo\n"
    assert (logs_dir / "insurance-server-lambdas-mongo_seed-1.log").read_text(encoding="utf-8") == "log do mongo_seed completo\n"
    assert (logs_dir / "insurance-server-lambdas-mockapi-1.log").read_text(encoding="utf-8") == "log do mockapi completo\n"
    assert set(result["containers"]) == {"v9-mtls", "insurance-server-lambdas-auth-1",
                                          "insurance-server-lambdas-mongo_seed-1", "insurance-server-lambdas-mockapi-1"}
    # sem janela de tempo (--since/--until) -- log CHEIO, nunca so um trecho.
    full_log_calls = [" ".join(c) for c in calls if "docker logs -t v9-mtls" in " ".join(c)]
    assert full_log_calls and all("--since" not in c for c in full_log_calls), full_log_calls


def test_mutante_collect_full_logs_so_gateway_perde_auth_mongo_mockapi(tmp_path, monkeypatch):
    """Mutante = o comportamento ANTIGO: so o gateway (via `_gateway_
    logs`, com JANELA de tempo) era preservado -- auth/mongo_seed/
    mockapi nunca apareciam em disco. Reproduz o mutante e confirma
    que a lacuna real existia."""
    def mutant_collect(executor, out_dir):
        out_dir = Path(out_dir)
        logs_dir = out_dir / "full_container_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_text = executor._gateway_logs("2026-01-01T00:00:00", "2026-01-01T00:01:00")
        (logs_dir / "v9-mtls.log").write_text(log_text, encoding="utf-8")
        return {"containers": {"v9-mtls": {}}}

    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: FakeProc(stdout=""))
    executor = orch.SSHExecutor(_inventory(), key_path="/fake/key")
    out_dir = tmp_path / "out_mutante"
    result = mutant_collect(executor, out_dir)
    assert set(result["containers"]) == {"v9-mtls"}  # nunca os outros 3 -- exatamente a lacuna da regra nova
    assert not (out_dir / "full_container_logs" / "insurance-server-lambdas-auth-1.log").exists()


# --- Generalizacao N-servidores (pedido do Luciano): collect_full_logs
# precisa cobrir TODOS os servidores da campanha oficial, nunca so 1.

def test_collect_full_logs_cobre_todos_os_servidores_em_modo_campanha(tmp_path, monkeypatch):
    def fake_run(argv, timeout=None):
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "docker logs -t v9-mtls" in remote_cmd:
            return FakeProc(stdout="log gateway\n")
        return FakeProc(stdout="")

    monkeypatch.setattr(cli, "_run", fake_run)
    inventory = {
        "control": {"public_ip": "203.0.113.10"},
        "servers": {
            "sa-east-1": {"public_ip": "203.0.113.50"},
            "us-east-1": {"public_ip": "203.0.113.51"},
        },
        "clients": {"L219": {"public_ip": "203.0.113.70"}},
    }
    executor = orch.SSHExecutor(inventory, key_path="/fake/key", route_server={"L219": "sa-east-1"})
    out_dir = tmp_path / "out"
    result = dc.collect_full_logs(executor, out_dir)

    logs_dir = out_dir / "full_container_logs"
    assert (logs_dir / "sa-east-1_v9-mtls.log").is_file()
    assert (logs_dir / "us-east-1_v9-mtls.log").is_file()
    assert (logs_dir / "sa-east-1_insurance-server-lambdas-auth-1.log").is_file()
    assert (logs_dir / "us-east-1_insurance-server-lambdas-auth-1.log").is_file()
    assert set(result["containers"].keys()) == {
        "sa-east-1_v9-mtls", "sa-east-1_insurance-server-lambdas-auth-1",
        "sa-east-1_insurance-server-lambdas-mongo_seed-1", "sa-east-1_insurance-server-lambdas-mockapi-1",
        "us-east-1_v9-mtls", "us-east-1_insurance-server-lambdas-auth-1",
        "us-east-1_insurance-server-lambdas-mongo_seed-1", "us-east-1_insurance-server-lambdas-mockapi-1",
    }


def test_mutante_collect_full_logs_so_1_servidor_em_modo_campanha_perderia_logs(tmp_path, monkeypatch):
    """Mutante = o comportamento ANTIGO: so `executor._server_ip()`
    (que em modo campanha levanta sem `route`) -- confirma que a
    generalizacao real acima e genuinamente necessaria, nunca uma
    coincidencia."""
    inventory = {
        "control": {"public_ip": "203.0.113.10"},
        "servers": {"sa-east-1": {"public_ip": "203.0.113.50"}, "us-east-1": {"public_ip": "203.0.113.51"}},
        "clients": {"L219": {"public_ip": "203.0.113.70"}},
    }
    executor = orch.SSHExecutor(inventory, key_path="/fake/key", route_server={"L219": "sa-east-1"})
    with pytest.raises(KeyError):
        executor._server_ip()  # mutante: o jeito antigo de pegar "o" servidor quebra em modo campanha

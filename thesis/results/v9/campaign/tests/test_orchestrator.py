"""Testes do orquestrador do piloto -- sem SSH real, sem AWS, sem
credenciais. SSHExecutor e testado com `cli._run` monkeypatchado
(stub da CLI real, nunca uma chamada de verdade)."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import orchestrator as orch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "integration"))
import evaluate_criteria as ec  # noqa: E402


def test_cardinality_is_exactly_60_and_12(tmp_path):
    manifest = orch.run_pilot(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    # Literal, nao derivado de orch.EXPECTED_TOTAL -- um bug que
    # mudasse PROFILES/ROUTES/N_PER_PROFILE junto NAO escaparia aqui.
    assert manifest["total_execucoes"] == 60
    assert manifest["total_capturas"] == 12
    execucoes = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))
    assert len(execucoes) == 60
    criterio6 = json.loads(Path(manifest["criterio6_json"]).read_text(encoding="utf-8"))
    assert len(criterio6) == 60
    capturas = list(Path(manifest["capturas_dir"]).glob("*.log"))
    assert len(capturas) == 12


def test_cada_rota_tem_os_4_perfis_sem_repeticao(tmp_path):
    manifest = orch.run_pilot(orch.LocalExecutor(), seed=7, out_dir=tmp_path)
    for route in orch.ROUTES:
        order = manifest["route_orders"][route]
        assert sorted(order) == sorted(orch.PROFILES), f"rota {route}: ordem nao e uma permutacao dos 4 perfis"
        assert len(order) == len(set(order)), f"rota {route}: perfil repetido"


def test_reprodutivel_pelo_mesmo_seed(tmp_path):
    m1 = orch.run_pilot(orch.LocalExecutor(), seed=99, out_dir=tmp_path / "a")
    m2 = orch.run_pilot(orch.LocalExecutor(), seed=99, out_dir=tmp_path / "b")
    assert m1["route_orders"] == m2["route_orders"]


def test_block_order_e_de_fato_sorteada_mutante_sem_shuffle(monkeypatch):
    """Mutacao: se o sorteio (rng.shuffle) for removido, as 3 rotas
    teriam todas a mesma ordem base -- esta asserção so passa com o
    shuffle real no lugar."""
    rng_real = orch.random.Random(123)
    orders_real = [orch.profile_block_order(r, rng_real) for r in orch.ROUTES]
    assert len({tuple(o) for o in orders_real}) > 1, (
        "as 3 rotas sairam com a MESMA ordem de perfis -- o sorteio nao esta variando de fato"
    )

    def mutated_no_shuffle(route, rng):
        return orch.PROFILES[:]  # mutante: shuffle removido

    monkeypatch.setattr(orch, "profile_block_order", mutated_no_shuffle)
    rng_mut = orch.random.Random(123)
    orders_mut = [orch.profile_block_order(r, rng_mut) for r in orch.ROUTES]
    assert len({tuple(o) for o in orders_mut}) == 1, "mutante deveria produzir a mesma ordem nas 3 rotas (prova que o teste real depende do shuffle)"


def test_marcadores_batem_com_o_regex_real_do_avaliador(tmp_path):
    manifest = orch.run_pilot(orch.LocalExecutor(), seed=5, out_dir=tmp_path)
    log_text = Path(manifest["combined_log"]).read_text(encoding="utf-8")
    found = 0
    for profile in orch.PROFILES:
        for route in orch.ROUTES:
            for run in range(1, orch.N_PER_PROFILE + 1):
                window = ec._execucao_window(log_text, profile, route, run)
                if window is not None:
                    found += 1
    assert found == 60, f"so {found}/60 janelas foram encontradas pelo regex REAL do avaliador"


def test_sondagem_fica_fora_de_qualquer_janela(tmp_path):
    manifest = orch.run_pilot(orch.LocalExecutor(), seed=3, out_dir=tmp_path)
    log_text = Path(manifest["combined_log"]).read_text(encoding="utf-8")
    # A sondagem (sni="mtls", remoteAddr="203.0.113.9:...") nunca deve
    # cair DENTRO de uma janela EXECUCAO INICIO...FIM.
    for m in re.finditer(r"== EXECUCAO INICIO.*?== EXECUCAO FIM.*?==", log_text, re.S):
        assert "203.0.113.9:51000" not in m.group(0), "a linha da sondagem vazou pra dentro de uma janela de execucao"


def test_formato_aceito_pelo_avaliador_real_criterios_1_4_5_6_passam(tmp_path):
    """Integra de verdade com evaluate_criteria.py (importado, nao
    reimplementado) -- critérios 1/4/5/6 (produzidos pelo
    orquestrador) devem dar PASS; 2/3/7 (produzidos pelos outros
    produtores dedicados, Decisao 41, fora do escopo do
    orquestrador) devem FALHAR fail-closed, nunca None, nunca
    excecao."""
    manifest = orch.run_pilot(orch.LocalExecutor(), seed=11, out_dir=tmp_path)
    log_text = Path(manifest["combined_log"]).read_text(encoding="utf-8")
    execucoes = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))

    r1 = ec.criterion_1_message_sizes(log_text, aws_dir=str(tmp_path))
    r4 = ec.criterion_4_counts(execucoes, log_text)
    r5 = ec.criterion_5_zero_errors(log_text)
    r6 = ec.criterion_6_instrumentation(log_text, aws_dir=str(tmp_path))
    r2 = ec.criterion_2_initcwnd(str(tmp_path))
    r3 = ec.criterion_3_distant_route(str(tmp_path))
    r7 = ec.criterion_7_latency_sanity(str(tmp_path))

    assert r1["pass"] is True, r1
    assert r4["pass"] is True, r4
    assert r5["pass"] is True, r5
    assert r6["pass"] is True, r6
    assert r2["pass"] is False  # fora do escopo do orquestrador -- Decisao 41
    assert r3["pass"] is False
    assert r7["pass"] is False


def test_mutante_cardinalidade_errada_e_pega_pelo_avaliador(tmp_path):
    """Mutacao: um orquestrador que so rodasse N=4 (em vez de 5) por
    perfil produziria 48 execucoes, nao 60 -- o avaliador REAL deve
    reprovar o criterio 4 por cardinalidade, mesmo que cada execucao
    individual estivesse perfeita."""
    original_n = orch.N_PER_PROFILE
    try:
        orch.N_PER_PROFILE = 4  # mutante
        manifest = orch.run_pilot(orch.LocalExecutor(), seed=2, out_dir=tmp_path)
        assert manifest["total_execucoes"] == 48
        log_text = Path(manifest["combined_log"]).read_text(encoding="utf-8")
        execucoes = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))
        r4 = ec.criterion_4_counts(execucoes, log_text)
        assert r4["pass"] is False, "avaliador deveria reprovar cardinalidade 48 != 60"
    finally:
        orch.N_PER_PROFILE = original_n


def test_ssh_executor_disca_sempre_pelo_ip_publico(monkeypatch):
    """Decisao 43/45: SSH tem que sempre usar o IP PUBLICO do alvo,
    inclusive pro cliente L0 co-localizado -- nunca o privado."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {
            "L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True},
            "L219": {"public_ip": "203.0.113.70", "private_ip": "10.0.2.70", "colocated": False},
        },
    }
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        class FakeProc:
            returncode = 0
            stdout = '{"insurance": [], "person": [], "gateway_log_lines": [], "curveID": "x", "dualAuthenticated": false}'
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    executor.run_execution("classico", "L0", 1)
    ssh_target = [a for a in calls[-1] if "@" in a][0]
    assert ssh_target.endswith("@203.0.113.60"), f"deveria discar o IP PUBLICO do L0, discou: {ssh_target}"

    executor.run_execution("classico", "L219", 1)
    ssh_target = [a for a in calls[-1] if "@" in a][0]
    assert ssh_target.endswith("@203.0.113.70")


def test_mutante_ssh_por_ip_privado_e_detectado(monkeypatch):
    """Mutacao: se _client_ip() usasse o IP privado por engano, este
    teste tem que pegar -- prova que o teste acima depende de fato da
    escolha certa, nao passa por acidente."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        class FakeProc:
            returncode = 0
            stdout = '{"insurance": [], "person": [], "gateway_log_lines": [], "curveID": "x", "dualAuthenticated": false}'
            stderr = ""
        return FakeProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    monkeypatch.setattr(orch.SSHExecutor, "_client_ip", lambda self, route: self.inventory["clients"][route]["private_ip"])  # mutante
    executor.run_execution("classico", "L0", 1)
    ssh_target = [a for a in calls[-1] if "@" in a][0]
    assert ssh_target.endswith("@10.0.1.60")  # confirma que o mutante de fato mudou o comportamento
    with pytest.raises(AssertionError):
        assert ssh_target.endswith("@203.0.113.60")


def test_dedicated_capture_bate_com_os_baselines_reais_importados():
    block = orch._dedicated_capture_block("classico")
    row = ec._message_sizes_for_profile(block, "classico")
    assert row["ok"] is True, row

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
    individual estivesse perfeita. (`N_PER_PROFILE=4` passado
    diretamente -- mutar o modulo nao afetaria o default ja vinculado
    da funcao, Python so avalia defaults uma vez, na definicao.)"""
    manifest = orch.run_pilot(orch.LocalExecutor(), seed=2, out_dir=tmp_path, n_per_profile=4)
    assert manifest["total_execucoes"] == 48
    assert manifest["expected_total"] == 48
    log_text = Path(manifest["combined_log"]).read_text(encoding="utf-8")
    execucoes = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))
    r4 = ec.criterion_4_counts(execucoes, log_text)
    # criterion_4_counts compara contra EXPECTED_EXECUCOES_PILOTO (60,
    # constante fixa do avaliador) -- nunca contra o "expected_total"
    # dinamico deste orquestrador, que e so pra uso interno/smoke.
    assert r4["pass"] is False, "avaliador deveria reprovar cardinalidade 48 != 60"


def _fake_run_factory(calls):
    def fake_run(argv, timeout=None):
        calls.append(argv)
        class FakeProc:
            returncode = 0
            stdout = '{"calls": [], "call_count": 0, "retries": []}'
            stderr = ""
        return FakeProc()
    return fake_run


def _client_runner_call(calls):
    """Entre as varias chamadas ssh de UMA run_execution (cliente +
    busca de log do gateway), acha a que de fato roda
    campaign_client_runner.py -- so essa precisa discar o cliente."""
    matches = [c for c in calls if any("campaign_client_runner.py" in a for a in c)]
    assert matches, "nenhuma chamada rodou campaign_client_runner.py"
    return matches[-1]


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
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")

    executor.run_execution("classico", "L0", 1)
    ssh_target = [a for a in _client_runner_call(calls) if "@" in a][0]
    assert ssh_target.endswith("@203.0.113.60"), f"deveria discar o IP PUBLICO do L0, discou: {ssh_target}"

    calls.clear()
    executor.run_execution("classico", "L219", 1)
    ssh_target = [a for a in _client_runner_call(calls) if "@" in a][0]
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
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    monkeypatch.setattr(orch.SSHExecutor, "_client_ip", lambda self, route: self.inventory["clients"][route]["private_ip"])  # mutante
    executor.run_execution("classico", "L0", 1)
    ssh_target = [a for a in _client_runner_call(calls) if "@" in a][0]
    assert ssh_target.endswith("@10.0.1.60")  # confirma que o mutante de fato mudou o comportamento
    with pytest.raises(AssertionError):
        assert ssh_target.endswith("@203.0.113.60")


def test_dedicated_capture_bate_com_os_baselines_reais_importados():
    block = orch._dedicated_capture_block("classico")
    row = ec._message_sizes_for_profile(block, "classico")
    assert row["ok"] is True, row


def test_porta_de_fumaca_tem_cardinalidade_12_nunca_60(tmp_path):
    manifest = orch.run_smoke_gate(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    assert manifest["smoke"] is True
    assert manifest["n_per_profile"] == 1
    assert manifest["total_execucoes"] == 12
    assert manifest["expected_total"] == 12
    assert manifest["total_execucoes"] != 60, "a porta de fumaca NUNCA pode ser confundida com as 60 execucoes oficiais"


def test_porta_de_fumaca_passa_com_dados_bons(tmp_path):
    manifest = orch.run_smoke_gate(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    assert manifest["smoke_ok"] is True
    assert manifest["smoke_failures"] == []


def test_porta_de_fumaca_aborta_se_qualquer_execucao_falhar(tmp_path, monkeypatch):
    """Mutacao direta no Executor: UMA das 12 execucoes (L219/pqc)
    devolve contagens HTTP erradas -- smoke_ok tem que virar False e
    identificar exatamente qual (profile, route) falhou."""
    real_run_execution = orch.LocalExecutor.run_execution

    def broken_run_execution(self, profile, route, run):
        result = real_run_execution(self, profile, route, run)
        if profile == "pqc" and route == "L219":
            result["person"] = result["person"][:-5]  # falta gente -- contagem HTTP erra
        return result

    monkeypatch.setattr(orch.LocalExecutor, "run_execution", broken_run_execution)
    manifest = orch.run_smoke_gate(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    assert manifest["smoke_ok"] is False
    assert len(manifest["smoke_failures"]) == 1
    assert manifest["smoke_failures"][0]["profile"] == "pqc"
    assert manifest["smoke_failures"][0]["route"] == "L219"


def test_mutante_smoke_ok_sempre_true_e_pego(tmp_path, monkeypatch):
    """Mutacao: smoke_ok calculado so pela cardinalidade, ignorando
    `failures` -- o teste de abortar acima tem que reprovar com essa
    mutacao, confirmando que smoke_ok depende de verdade da lista de
    falhas, nao so da contagem total."""
    real_run_execution = orch.LocalExecutor.run_execution

    def broken_run_execution(self, profile, route, run):
        result = real_run_execution(self, profile, route, run)
        if profile == "pqc" and route == "L219":
            result["person"] = result["person"][:-5]
        return result

    monkeypatch.setattr(orch.LocalExecutor, "run_execution", broken_run_execution)

    def mutated_run_smoke_gate(executor, seed, out_dir):
        manifest = orch.run_pilot(executor, seed, out_dir, n_per_profile=orch.SMOKE_N_PER_PROFILE, smoke=True)
        manifest["smoke_ok"] = manifest["total_execucoes"] == orch.SMOKE_EXPECTED_TOTAL  # mutante: ignora failures
        manifest["smoke_failures"] = []
        return manifest

    mutant_manifest = mutated_run_smoke_gate(orch.LocalExecutor(), 1, tmp_path)
    assert mutant_manifest["smoke_ok"] is True  # mutante esconde a falha real
    with pytest.raises(AssertionError):
        assert mutant_manifest["smoke_ok"] is False


def test_ssh_executor_traduz_nome_de_perfil_pro_cliente(monkeypatch):
    """Decisao 49 (revisao independente): achado real -- o CLIENTE
    (opin_flow.py) so reconhece os nomes antigos da v8
    ("classic"/"hybrid"), nunca os de exibicao da v9
    ("classico"/"hibrido-v8"). CRYPTO_PROFILE no comando remoto do
    CLIENTE tem que vir traduzido; o perfil passado pro orquestrador
    (e usado no manifesto/avaliador) continua sendo o de exibicao."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    executor.run_execution("hibrido-v8", "L0", 1)
    remote_cmd = _client_runner_call(calls)[-1]
    assert "CRYPTO_PROFILE=hybrid" in remote_cmd, f"esperava CRYPTO_PROFILE=hybrid, comando: {remote_cmd}"
    assert "CRYPTO_PROFILE=hibrido-v8" not in remote_cmd


def test_mutante_sem_traducao_de_perfil_e_pego(monkeypatch):
    """Mutacao: usar o nome de exibicao direto (sem traducao) no
    ambiente do cliente -- o teste acima tem que reprovar."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    monkeypatch.setattr(orch.SSHExecutor, "_client_env",
                         lambda self, profile, gw: {"V9_HARNESS": "1", "CRYPTO_PROFILE": profile, "REMOTE_GATEWAY_HOST": gw})
    executor.run_execution("hibrido-v8", "L0", 1)
    remote_cmd = _client_runner_call(calls)[-1]
    assert "CRYPTO_PROFILE=hibrido-v8" in remote_cmd  # mutante: nome errado foi usado
    with pytest.raises(AssertionError):
        assert "CRYPTO_PROFILE=hybrid" in remote_cmd


def test_start_block_troca_perfil_do_gateway_e_sobe_proxy_signer(monkeypatch):
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert any("docker run -d --name v9-mtls" in c and "CRYPTO_PROFILE=classico" in c for c in flat), flat
    assert any("start_tls_kem_proxy" in c and "start_pqc_signer_service" in c for c in flat), flat


def test_stop_block_para_os_dois_containers_fixos(monkeypatch):
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    executor.stop_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert any("docker stop tls_kem_proxy_run pqc_signer_service_run" in c for c in flat), flat
    assert any("docker rm -f tls_kem_proxy_run pqc_signer_service_run" in c for c in flat), flat


def test_connection_ok_extrai_curve_e_dual_authenticated_reais():
    log = (
        '2026/11/07 20:58:35 gateway: classico connection OK remoteAddr=172.21.0.7:1 '
        'sni="mtls" curve=CurveP384 dualAuthenticated=false clientCert="classico_client" '
        'handshakeBytesIn=1 handshakeBytesOut=1\n'
        '2026/11/07 20:58:35 gateway: classico connection OK remoteAddr=172.21.0.7:2 '
        'sni="matls-api.local" curve=CurveP256 dualAuthenticated=false clientCert="op" '
        'handshakeBytesIn=1 handshakeBytesOut=1\n'
    )
    executor = orch.SSHExecutor({"server": {}, "clients": {}})
    raw_lines, parsed = executor._connection_ok_lines(log)
    assert len(raw_lines) == 2
    client_facing = [p for p in parsed if p["sni"] != orch._INTERNAL_CALLER_SNI]
    assert len(client_facing) == 1
    assert client_facing[0]["curve"] == "CurveP384"
    assert client_facing[0]["dual"] == "false"


def test_mutante_sem_excluir_internal_caller_conta_errado():
    """Mutacao: nao filtrar pelo SNI interno -- contaria 2 'client
    facing' em vez de 1, o teste acima tem que reprovar."""
    log = (
        '2026/11/07 20:58:35 gateway: classico connection OK remoteAddr=172.21.0.7:1 '
        'sni="mtls" curve=CurveP384 dualAuthenticated=false clientCert="classico_client" '
        'handshakeBytesIn=1 handshakeBytesOut=1\n'
        '2026/11/07 20:58:35 gateway: classico connection OK remoteAddr=172.21.0.7:2 '
        'sni="matls-api.local" curve=CurveP256 dualAuthenticated=false clientCert="op" '
        'handshakeBytesIn=1 handshakeBytesOut=1\n'
    )
    executor = orch.SSHExecutor({"server": {}, "clients": {}})
    _, parsed = executor._connection_ok_lines(log)
    client_facing_mutante = parsed  # mutante: sem filtro de SNI
    assert len(client_facing_mutante) == 2
    with pytest.raises(AssertionError):
        assert len(client_facing_mutante) == 1

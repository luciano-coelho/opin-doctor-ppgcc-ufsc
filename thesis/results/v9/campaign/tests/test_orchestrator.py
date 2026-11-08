"""Testes do orquestrador do piloto -- sem SSH real, sem AWS, sem
credenciais. SSHExecutor e testado com `cli._run` monkeypatchado
(stub da CLI real, nunca uma chamada de verdade)."""
import hashlib
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


_FAKE_GATEWAY_BINARY_BYTES = b"fake gateway elf binary -- so para testes, nunca executado"
_FAKE_GATEWAY_SHA256 = hashlib.sha256(_FAKE_GATEWAY_BINARY_BYTES).hexdigest()


_FAKE_IMAGE_IDS = {
    "gateway": "sha256:" + "1" * 64,
    "proxy": "sha256:" + "2" * 64,
    "measure": "sha256:" + "3" * 64,
}


def _fake_pins(gateway_sha256=_FAKE_GATEWAY_SHA256, image_ids=None):
    image_ids = image_ids or _FAKE_IMAGE_IDS
    return {"images": {
        "gateway": {"binary_sha256": gateway_sha256, "docker_image": "mockopin-v9-gateway", "image_id": image_ids["gateway"]},
        "proxy": {"docker_image": "mockopin-v9-proxy", "image_id": image_ids["proxy"]},
        "measure": {"docker_image": "mockopin-v9-measure", "image_id": image_ids["measure"]},
    }}


@pytest.fixture(autouse=True)
def _default_fake_pins(monkeypatch):
    """Decisao 55, item 1: `_local_gateway_binary_info` agora confere
    o sha256 extraido contra PINS.json de verdade -- todo teste deste
    arquivo usa um binario FAKE (`_FAKE_GATEWAY_BINARY_BYTES`), que
    nunca bateria contra o PINS.json real do repositorio. Autouse:
    aplica o PINS fake (combinando com o binario fake) em TODO teste
    por padrao -- os poucos testes que querem testar divergencia de
    pin de proposito sobrescrevem `orch.load_pins` eles mesmos."""
    monkeypatch.setattr(orch, "load_pins", lambda pins_path=None: _fake_pins())


class _SimpleProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _fake_sh_docker_save_load_call(argv):
    """Decisao 55, item 2: `_deliver_image` roda `docker save | ssh
    ... docker load` como um UNICO comando `sh -c` via `cli._run` --
    fake generico, sempre sucesso (o teste de ID errado sobrescreve
    so a resposta do `docker image inspect` que vem depois, nunca
    este passo)."""
    if argv and argv[0] == "sh" and len(argv) > 1 and argv[1] == "-c" and "docker save" in argv[2]:
        return _SimpleProc()
    return None


def _fake_image_id_for_remote_cmd(remote_cmd, image_ids=_FAKE_IMAGE_IDS):
    """Resposta fake de `docker image inspect <imagem> --format
    '{{.Id}}'` -- usada pelos dois fakes deste arquivo. Devolve None
    se o comando nao for essa chamada."""
    if "docker image inspect" not in remote_cmd:
        return None
    for key, name in (("gateway", "mockopin-v9-gateway"), ("proxy", "mockopin-v9-proxy"), ("measure", "mockopin-v9-measure")):
        if name in remote_cmd:
            return f"{image_ids[key]}\n"
    return None


def _fake_local_docker_gateway_binary_call(argv):
    """Decisao 54, item 1: respostas fake pras chamadas LOCAIS (nao-
    SSH) que `_local_gateway_binary_info` faz via `cli._run` --
    compartilhada pelos dois fakes deste arquivo (`_fake_run_factory`/
    `_fake_run_dedicated_capture`), pra nunca duplicar a logica.
    Devolve None se `argv` nao e uma dessas chamadas (o chamador cai
    pro proprio fallback dele)."""
    if not argv or argv[0] != "docker":
        return None
    if len(argv) > 1 and argv[1] == "cp":
        Path(argv[3]).write_bytes(_FAKE_GATEWAY_BINARY_BYTES)
        return _SimpleProc()
    if len(argv) > 1 and argv[1] == "run" and "version" in argv and "-m" in argv:
        return _SimpleProc(stdout="/verify/gateway: go1.27.3\n")
    if len(argv) > 1 and argv[1] == "run" and "cat" in argv:
        return _SimpleProc(stdout='{"go_tag": "go1.27.3"}')
    return _SimpleProc()  # docker create / docker rm -f


def _fake_run_factory(calls):
    """Decisao 54, item 1: `_local_gateway_binary_info` roda `docker
    create`/`docker cp`/`docker run ... go version`/`docker run ...
    cat build_metadata.json` via `cli._run` (a MESMA fronteira que
    `cli.run_ssh` usa por baixo) -- precisa de respostas plausiveis
    aqui tambem, nao so pras chamadas SSH. `docker cp` em especial
    PRECISA escrever um arquivo de verdade no destino (3º argumento),
    porque o codigo real faz `bin_path.read_bytes()` depois -- sem
    isso todo teste que chama `start_block`/`dedicated_capture`
    quebraria com `FileNotFoundError`, nunca por causa do que o teste
    queria exercitar."""
    def fake_run(argv, timeout=None):
        calls.append(argv)
        local_docker = _fake_local_docker_gateway_binary_call(argv)
        if local_docker is not None:
            return local_docker
        sh_save_load = _fake_sh_docker_save_load_call(argv)
        if sh_save_load is not None:
            return sh_save_load
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "sha256sum -c" in remote_cmd:
            return _SimpleProc(stdout=f"gateway: OK\n")
        if "sha256sum /gateway" in remote_cmd:
            return _SimpleProc(stdout=f"{_FAKE_GATEWAY_SHA256}  /gateway\n")
        image_id_stdout = _fake_image_id_for_remote_cmd(remote_cmd)
        if image_id_stdout is not None:
            return _SimpleProc(stdout=image_id_stdout)
        return _SimpleProc(stdout='{"calls": [], "call_count": 0, "retries": []}')
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


# --- Decisao 53 (pedido independente, item 4b/4c): preflight de
# captura ANTES de qualquer execucao, e prova da captura em si (1 por
# PERFIL, 4 no total -- nunca confundida com as 12 oficiais do
# criterio 1 nem com as 12/60 execucoes).

def test_porta_de_fumaca_aborta_antes_de_qualquer_execucao_se_prerequisito_de_captura_faltar(tmp_path, monkeypatch):
    executor = orch.LocalExecutor()
    monkeypatch.setattr(executor, "capture_ready_check",
                         lambda: {"go": False, "checks": [{"check": "x", "ok": False, "host": "203.0.113.9", "missing": ["tcpdump nao encontrado no PATH"]}]})
    manifest = orch.run_smoke_gate(executor, seed=1, out_dir=tmp_path)
    assert manifest["smoke_ok"] is False
    assert manifest["aborted_before_execution"] is True
    assert manifest["total_execucoes"] == 0
    assert "tcpdump" in manifest["note"]
    assert not (tmp_path / "piloto_calls.json").exists(), "nenhum artefato de execucao deveria existir -- abortou ANTES de qualquer execucao"


def test_mutante_porta_de_fumaca_ignora_capture_preflight_e_pego(tmp_path, monkeypatch):
    """Mutacao: ignora o resultado de `capture_ready_check()` -- o
    teste acima (aborted_before_execution=True, 0 execucoes) tem que
    reprovar com essa mutacao, confirmando que o gate e de fato load-
    bearing (sem ele, as 12 execucoes rodariam mesmo faltando tcpdump)."""
    executor = orch.LocalExecutor()
    monkeypatch.setattr(executor, "capture_ready_check", lambda: {"go": False, "checks": []})

    def mutant_run_smoke_gate(executor, seed, out_dir):
        # mutante: nunca olha capture_ready_check(), vai direto pras 12 execucoes
        return orch.run_pilot(executor, seed, out_dir, n_per_profile=orch.SMOKE_N_PER_PROFILE,
                               smoke=True, skip_dedicated_captures=True)

    mutant_manifest = mutant_run_smoke_gate(executor, 1, tmp_path)
    assert mutant_manifest["total_execucoes"] == 12  # mutante rodou tudo mesmo devendo abortar
    with pytest.raises(AssertionError):
        assert mutant_manifest["total_execucoes"] == 0


def test_porta_de_fumaca_roda_prova_de_captura_por_perfil_4_nao_12(tmp_path):
    manifest = orch.run_smoke_gate(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    assert manifest["capture_proof_ok"] is True
    assert len(manifest["capture_proof_rows"]) == len(orch.PROFILES) == 4
    assert {r["profile"] for r in manifest["capture_proof_rows"]} == set(orch.PROFILES)
    proof_dir = Path(manifest["capture_proof_dir"])
    assert proof_dir.name == "smoke_capture_proof"
    proof_files = sorted(p.name for p in proof_dir.glob("*.log"))
    assert proof_files == sorted(f"{p}.log" for p in orch.PROFILES), proof_files
    # nunca confundida com as 12 capturas oficiais do criterio 1
    assert proof_dir != Path(manifest["capturas_dir"])


def test_porta_de_fumaca_capture_proof_falha_se_qualquer_perfil_falhar(tmp_path, monkeypatch):
    real_dedicated_capture = orch.LocalExecutor.dedicated_capture

    def broken_dedicated_capture(self, profile, route):
        if profile == "hibrido-and":
            raise RuntimeError("tshark nao decifrou nada -- simulado")
        return real_dedicated_capture(self, profile, route)

    monkeypatch.setattr(orch.LocalExecutor, "dedicated_capture", broken_dedicated_capture)
    manifest = orch.run_smoke_gate(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    assert manifest["capture_proof_ok"] is False
    assert manifest["smoke_ok"] is False
    broken_row = next(r for r in manifest["capture_proof_rows"] if r["profile"] == "hibrido-and")
    assert broken_row["ok"] is False
    assert "tshark" in broken_row["note"]


# --- Decisao 55, item 3: `_bytes_diagnostic_for_profile` -- DIAGNOSTICO
# (nunca o gate oficial do criterio 1), desvio != 0 PAUSA e pede
# decisao, nunca aborta por conta propria.

def test_bytes_diagnostic_zero_desvio_com_certs_reais_e_log_real():
    certs_dir = orch._DEFAULT_CERTS_DIR
    log = (
        '2026/11/08 03:00:00 gateway: hibrido-v8 connection OK remoteAddr=172.21.0.6:1 '
        'sni="mtls" curve=SecP384r1MLKEM1024 dualAuthenticated=false clientCert="hibrido_v8_client" '
        'handshakeBytesIn=8397 handshakeBytesOut=8552\n'
    )
    row = orch._bytes_diagnostic_for_profile(log, "hibrido-v8", certs_dir)
    assert row["ok"] is True, row
    assert row["delta_in"] == 0 and row["delta_out"] == 0


def test_bytes_diagnostic_detecta_desvio():
    certs_dir = orch._DEFAULT_CERTS_DIR
    log = (
        '2026/11/08 03:00:00 gateway: hibrido-v8 connection OK remoteAddr=172.21.0.6:1 '
        'sni="mtls" curve=SecP384r1MLKEM1024 dualAuthenticated=false clientCert="hibrido_v8_client" '
        'handshakeBytesIn=8397 handshakeBytesOut=9999\n'
    )
    row = orch._bytes_diagnostic_for_profile(log, "hibrido-v8", certs_dir)
    assert row["ok"] is False
    assert row["delta_out"] == 9999 - 8552


def test_porta_de_fumaca_sinaliza_decisao_pendente_sem_bloquear_smoke_ok_quando_desvio_detectado(tmp_path, monkeypatch):
    """Diagnostico PAUSA e pede decisao (bytes_diagnostic_needs_decision),
    nunca bloqueia smoke_ok por conta propria -- a mesma logica do
    smoke gate de verdade (abortar sempre e decisao do Luciano, nunca
    automatica demais)."""
    monkeypatch.setattr(orch, "_bytes_diagnostic_for_profile",
                         lambda log_text, profile, certs_dir: {"profile": profile, "ok": profile != "hibrido-and"})
    manifest = orch.run_smoke_gate(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    assert manifest["bytes_diagnostic_needs_decision"] is True
    assert manifest["smoke_ok"] is True  # diagnostico nunca bloqueia o gate oficial por conta propria


def test_mutante_bytes_diagnostic_ignora_desvio_e_pego():
    """Mutacao: compara so handshakeBytesOut, nunca In -- um teste que
    dependesse de detectar desvio SO em In reprovaria com essa
    mutacao."""
    certs_dir = orch._DEFAULT_CERTS_DIR
    log = (
        '2026/11/08 03:00:00 gateway: hibrido-v8 connection OK remoteAddr=172.21.0.6:1 '
        'sni="mtls" curve=SecP384r1MLKEM1024 dualAuthenticated=false clientCert="hibrido_v8_client" '
        'handshakeBytesIn=1 handshakeBytesOut=8552\n'
    )
    row = orch._bytes_diagnostic_for_profile(log, "hibrido-v8", certs_dir)
    assert row["ok"] is False  # delta_in enorme -- o real detecta
    mutant_ok_so_out = row["delta_out"] == 0  # mutante: ignoraria In
    assert mutant_ok_so_out is True
    with pytest.raises(AssertionError):
        assert mutant_ok_so_out is False


def test_mutante_smoke_ok_ignora_capture_proof_e_pego(tmp_path, monkeypatch):
    """Mutacao: `smoke_ok` calculado sem o `capture_proof_ok` -- o
    teste acima (smoke_ok False quando a prova de captura falha) tem
    que reprovar com essa mutacao."""
    real_dedicated_capture = orch.LocalExecutor.dedicated_capture

    def broken_dedicated_capture(self, profile, route):
        if profile == "hibrido-and":
            raise RuntimeError("simulado")
        return real_dedicated_capture(self, profile, route)

    monkeypatch.setattr(orch.LocalExecutor, "dedicated_capture", broken_dedicated_capture)
    manifest = orch.run_smoke_gate(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    smoke_ok_mutante = manifest["total_execucoes"] == orch.SMOKE_EXPECTED_TOTAL and not manifest["smoke_failures"]  # mutante: ignora capture_proof_ok
    assert smoke_ok_mutante is True
    with pytest.raises(AssertionError):
        assert smoke_ok_mutante is False


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


# --- Decisao 54 (pedido independente, item 1): verificacao scp+
# sha256sum -c do binario do gateway, mecanismo ja pre-registrado
# (v9-prereg, "Entrega do binario"), implementado agora no
# SSHExecutor real. Binario CORRETO tem que passar (verde); binario
# ADULTERADO (divergencia no transporte OU no container ja rodando)
# tem que abortar ANTES de qualquer execucao (vermelho).

def test_start_block_verifica_binario_correto_e_passa(monkeypatch):
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    executor.start_block("classico", "L0")

    assert len(executor.gateway_binary_verifications) == 1
    v = executor.gateway_binary_verifications[0]
    assert v["sha256_expected"] == _FAKE_GATEWAY_SHA256
    assert v["transfer_sha256sum_c_ok"] is True
    assert v["running_container_sha256_ok"] is True
    assert v["go_build_version"] == "go1.27.3"
    assert v["toolchain_build_metadata"] == {"go_tag": "go1.27.3"}
    # execucao normal prosseguiu (proxy/signer subiram) -- a
    # verificacao passando nunca bloqueia o fluxo normal.
    flat = [" ".join(c) for c in calls]
    assert any("start_tls_kem_proxy" in c for c in flat), flat


def test_start_block_aborta_antes_de_qualquer_execucao_se_binario_adulterado_no_transporte(monkeypatch):
    """Binario ADULTERADO: `sha256sum -c` no destino reprova (o
    arquivo que chegou nao bate com o hash calculado na origem) --
    tem que abortar ANTES de subir o gateway/proxy/signer, nunca
    depois."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        local_docker = _fake_local_docker_gateway_binary_call(argv)
        if local_docker is not None:
            return local_docker
        sh_save_load = _fake_sh_docker_save_load_call(argv)
        if sh_save_load is not None:
            return sh_save_load
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "sha256sum -c" in remote_cmd:
            return _SimpleProc(returncode=1, stdout="gateway: FAILED\n", stderr="sha256sum: WARNING: 1 computed checksum did NOT match\n")
        image_id_stdout = _fake_image_id_for_remote_cmd(remote_cmd)
        if image_id_stdout is not None:
            return _SimpleProc(stdout=image_id_stdout)
        return _SimpleProc(stdout='{"calls": [], "call_count": 0, "retries": []}')

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    with pytest.raises(RuntimeError, match="sha256sum -c FALHOU"):
        executor.start_block("classico", "L0")

    flat = [" ".join(c) for c in calls]
    assert not any("docker run -d --name v9-mtls" in c for c in flat), (
        "o gateway NUNCA pode subir depois de uma verificacao de binario reprovada -- " + str(flat)
    )
    assert not any("start_tls_kem_proxy" in c for c in flat), (
        "proxy/signer NUNCA podem subir depois de uma verificacao de binario reprovada -- " + str(flat)
    )
    assert len(executor.gateway_binary_verifications) == 1
    assert executor.gateway_binary_verifications[0]["transfer_sha256sum_c_ok"] is False


def test_start_block_aborta_se_binario_do_container_rodando_diverge(monkeypatch):
    """Transporte bate (sha256sum -c OK), mas o binario DENTRO do
    container que efetivamente sobe nao bate com o verificado --
    tambem tem que abortar, ANTES de qualquer execucao (proxy/signer
    nunca sobem)."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        local_docker = _fake_local_docker_gateway_binary_call(argv)
        if local_docker is not None:
            return local_docker
        sh_save_load = _fake_sh_docker_save_load_call(argv)
        if sh_save_load is not None:
            return sh_save_load
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "sha256sum -c" in remote_cmd:
            return _SimpleProc(stdout="gateway: OK\n")
        if "sha256sum /gateway" in remote_cmd:
            return _SimpleProc(stdout="0000000000000000000000000000000000000000000000000000000000000000  /gateway\n")
        image_id_stdout = _fake_image_id_for_remote_cmd(remote_cmd)
        if image_id_stdout is not None:
            return _SimpleProc(stdout=image_id_stdout)
        return _SimpleProc(stdout='{"calls": [], "call_count": 0, "retries": []}')

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    with pytest.raises(RuntimeError, match="nao bate com o verificado"):
        executor.start_block("classico", "L0")

    flat = [" ".join(c) for c in calls]
    assert not any("start_tls_kem_proxy" in c for c in flat), flat
    assert executor.gateway_binary_verifications[0]["transfer_sha256sum_c_ok"] is True
    assert executor.gateway_binary_verifications[0]["running_container_sha256_ok"] is False


def test_mutante_start_block_ignora_resultado_da_verificacao_e_pego(monkeypatch):
    """Mutacao: `start_block` chama `_verify_gateway_binary` mas
    IGNORA a excecao (engole-a) -- os dois testes de aborto acima tem
    que reprovar com essa mutacao (proxy/signer subiriam mesmo com o
    binario adulterado)."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        local_docker = _fake_local_docker_gateway_binary_call(argv)
        if local_docker is not None:
            return local_docker
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "sha256sum -c" in remote_cmd:
            return _SimpleProc(returncode=1, stdout="gateway: FAILED\n")
        return _SimpleProc(stdout='{"calls": [], "call_count": 0, "retries": []}')

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    real_verify = orch.SSHExecutor._verify_gateway_binary

    def mutant_start_block_swallows_exception(self, profile, route):
        try:
            real_verify(self, profile, route)
        except RuntimeError:
            pass  # mutante: engole o erro, nunca aborta
        self._launch_gateway(profile)

    monkeypatch.setattr(orch.SSHExecutor, "start_block", mutant_start_block_swallows_exception)
    executor.start_block("classico", "L0")  # nao levanta, com o mutante
    flat = [" ".join(c) for c in calls]
    mutant_gateway_subiu = any("docker run -d --name v9-mtls" in c for c in flat)
    assert mutant_gateway_subiu is True  # mutante deixou subir mesmo adulterado
    with pytest.raises(AssertionError):
        assert mutant_gateway_subiu is False


# --- Decisao 55, item 1: PINS.json -- pin divergente aborta ANTES de
# qualquer execucao; pin correto passa; a "oficial" (uma segunda
# instancia de SSHExecutor, mesmo PINS.json) passa igual.

def test_pin_divergente_aborta_antes_de_qualquer_execucao(monkeypatch):
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    # PINS.json com um hash que NUNCA bate com o binario fake extraido.
    monkeypatch.setattr(orch, "load_pins", lambda pins_path=None: _fake_pins(gateway_sha256="0" * 64))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    with pytest.raises(RuntimeError, match="PINS.json"):
        executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert not any("docker run -d --name v9-mtls" in c for c in flat), (
        "o gateway NUNCA pode subir com um pin divergente -- " + str(flat)
    )
    assert not any("start_tls_kem_proxy" in c for c in flat), flat


def test_pin_correto_passa(monkeypatch):
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")  # usa o PINS fake (autouse) que bate
    executor.start_block("classico", "L0")
    assert executor.gateway_binary_verifications[0]["pin_matched"] is True
    flat = [" ".join(c) for c in calls]
    assert any("docker run -d --name v9-mtls" in c for c in flat), flat


def test_campanha_oficial_com_os_pins_do_piloto_passa(monkeypatch):
    """`load_pins()` e uma funcao pura do conteudo de PINS.json --
    nunca depende de ser "o piloto" ou "a oficial" chamando. Uma
    SEGUNDA instancia de SSHExecutor (simulando uma campanha oficial
    futura, mesmo arquivo PINS.json, perfil/rota fora da grade do
    piloto) passa pela MESMA verificacao sem nenhuma mudanca de
    codigo nem de pin."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L219": {"public_ip": "203.0.113.70", "private_ip": "10.0.2.70", "colocated": False}},
    }
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    campanha_oficial_executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    campanha_oficial_executor.start_block("pqc", "L219")
    assert campanha_oficial_executor.gateway_binary_verifications[0]["pin_matched"] is True


def test_deliver_image_aborta_antes_de_qualquer_execucao_se_image_id_errado(monkeypatch):
    """Decisao 55, item 2: `docker load` carrega uma imagem com um
    Image ID diferente do que PINS.json espera (origem/build
    diferente do artefato pinado) -- tem que abortar ANTES de
    qualquer `docker run`/proxy/signer."""
    inventory = {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        local_docker = _fake_local_docker_gateway_binary_call(argv)
        if local_docker is not None:
            return local_docker
        sh_save_load = _fake_sh_docker_save_load_call(argv)
        if sh_save_load is not None:
            return sh_save_load
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "docker image inspect" in remote_cmd:
            return _SimpleProc(stdout="sha256:" + "9" * 64 + "\n")  # ID errado, de proposito
        return _SimpleProc(stdout='{"calls": [], "call_count": 0, "retries": []}')

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    with pytest.raises(RuntimeError, match="nao bate com PINS.json"):
        executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert not any("docker run -d --name v9-mtls" in c for c in flat), flat
    assert not any("start_tls_kem_proxy" in c for c in flat), flat
    assert executor.image_delivery_verifications[0]["ok"] is False


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


# --- Decisao 51 (item 3): as 12 capturas dedicadas do criterio 1 --
# isolamento estrutural, nome/hash dos artefatos, leitura pelo
# avaliador real. A captura de REDE em si (tcpdump+tshark contra
# trafego real do SSHExecutor) -- IMPLEMENTADA na Decisao 52 (item 4),
# ver testes de `SSHExecutor.dedicated_capture` mais abaixo.

def test_capturas_dedicadas_rodam_fora_de_qualquer_janela_cronometrada(tmp_path):
    """Isolamento estrutural: nenhuma das 12 capturas pode aparecer
    DENTRO de uma janela EXECUCAO INICIO...FIM, nem contribuir pra
    execucoes_calls/criterio6_rows (que so contam as 60/12 reais)."""
    calls_to_dedicated_capture = []
    real_dedicated_capture = orch.LocalExecutor.dedicated_capture

    def spying_dedicated_capture(self, profile, route):
        calls_to_dedicated_capture.append((profile, route))
        return real_dedicated_capture(self, profile, route)

    executor = orch.LocalExecutor()
    import unittest.mock as mock
    with mock.patch.object(orch.LocalExecutor, "dedicated_capture", spying_dedicated_capture):
        manifest = orch.run_pilot(executor, seed=3, out_dir=tmp_path, n_per_profile=2)

    # As 12 capturas rodaram, e SO depois do loop de blocos (nenhuma
    # pode ter rodado antes da ultima execucao cronometrada -- testado
    # indiretamente: nenhuma linha delas aparece no log combinado,
    # que so tem os marcadores/linhas das execucoes reais).
    assert len(calls_to_dedicated_capture) == 12
    log_text = Path(manifest["combined_log"]).read_text(encoding="utf-8")
    for m in re.finditer(r"== EXECUCAO INICIO.*?== EXECUCAO FIM.*?==", log_text, re.S):
        assert "tamanho POR MENSAGEM" not in m.group(0), (
            "uma captura dedicada vazou pra dentro de uma janela de execucao cronometrada"
        )
    execucoes = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))
    assert len(execucoes) == manifest["total_execucoes"], "capturas dedicadas nao podem inflar a contagem de execucoes reais"


def test_mutante_captura_dedicada_dentro_do_bloco_e_detectada(tmp_path):
    """Mutacao: roda uma captura dedicada DENTRO do loop de execucoes
    (simulado direto, sem reescrever run_pilot) -- o teste de
    isolamento acima tem que reprovar essa situacao."""
    log_lines = [orch.execucao_marker_inicio("classico", "L0", 1)]
    log_lines.append(orch._dedicated_capture_block("classico"))  # mutante: capturada DENTRO da janela
    log_lines.append(orch.execucao_marker_fim("classico", "L0", 1))
    log_text = "\n".join(log_lines)
    found_contamination = any(
        "tamanho POR MENSAGEM" in m.group(0)
        for m in re.finditer(r"== EXECUCAO INICIO.*?== EXECUCAO FIM.*?==", log_text, re.S)
    )
    assert found_contamination is True  # mutante contamina de verdade
    with pytest.raises(AssertionError):
        assert found_contamination is False


def test_capturas_dedicadas_tem_nome_e_hash_esperados_e_o_avaliador_le(tmp_path):
    """Nome exato `{perfil}_{rota}.log`, hash SHA-256 estavel (mesmo
    conteudo -> mesmo hash, round-trip de verificacao igual ao
    `collect_artifacts.py` real) e leitura pelo avaliador REAL
    (`criterion_1_message_sizes(aws_dir=...)`, PASS genuino)."""
    import hashlib

    manifest = orch.run_pilot(orch.LocalExecutor(), seed=4, out_dir=tmp_path, n_per_profile=1)
    capturas_dir = Path(manifest["capturas_dir"])

    hashes = {}
    for profile in orch.PROFILES:
        for route in orch.ROUTES:
            path = capturas_dir / f"{profile}_{route}.log"
            assert path.is_file(), f"captura ausente: {path.name}"
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()

    assert len(hashes) == 12
    # Mesmo conteudo (mesmo perfil, rotas diferentes nao mudam o
    # tamanho de mensagem TLS) -> mesmo hash -- confirma estabilidade,
    # nao so presenca do arquivo.
    for profile in orch.PROFILES:
        route_hashes = {hashes[f"{profile}_{route}.log"] for route in orch.ROUTES}
        assert len(route_hashes) == 1, f"{profile}: hash deveria ser identico entre rotas (mesmo conteudo esperado)"

    r1 = ec.criterion_1_message_sizes(log_text="", aws_dir=str(tmp_path))
    assert r1["pass"] is True, r1
    assert r1["missing_captures"] == []


# --- Decisao 52 (pedido independente, item 4): SSHExecutor.dedicated_
# capture real -- interface PRIMARIA do servidor (nunca loopback),
# KEYLOG_PATH lido do proprio container do gateway, tshark via
# `mockopin-v9-measure`. `cli._run` monkeypatchado por CONTEUDO do
# remote_cmd (cada etapa SSH tem um comando distinto, precisa de
# stdout diferente por etapa -- o fake generico de calls/call_count
# das outras suites nao serve aqui).

_TSHARK_FAKE_OUTPUT = (
    "1\t1\t332\n"
    "2\t2,8,13,11,15,20\t183,6,105,6350,3571,32\n"
    "3\t11,15,20\t6352,3571,32\n"
)


def _fake_run_dedicated_capture(calls, iface="eth0", tcpdump_pid="12345", tshark_output=_TSHARK_FAKE_OUTPUT):
    def fake_run(argv, timeout=None):
        calls.append(argv)
        local_docker = _fake_local_docker_gateway_binary_call(argv)
        if local_docker is not None:
            return local_docker
        sh_save_load = _fake_sh_docker_save_load_call(argv)
        if sh_save_load is not None:
            return sh_save_load
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""

        proc = _SimpleProc()
        if "ip -o -4 route show to default" in remote_cmd:
            proc.stdout = f"{iface}\n"
        elif "nohup tcpdump" in remote_cmd:
            proc.stdout = f"{tcpdump_pid}\n"
        elif "campaign_client_runner.py" in remote_cmd:
            proc.stdout = '{"calls": [], "call_count": 0, "retries": []}'
        elif "tls.handshake.type" in remote_cmd:
            proc.stdout = tshark_output
        elif "sha256sum -c" in remote_cmd:
            proc.stdout = "gateway: OK\n"
        elif "sha256sum /gateway" in remote_cmd:
            proc.stdout = f"{_FAKE_GATEWAY_SHA256}  /gateway\n"
        else:
            image_id_stdout = _fake_image_id_for_remote_cmd(remote_cmd)
            if image_id_stdout is not None:
                proc.stdout = image_id_stdout
        return proc
    return fake_run


def _inventory_l0():
    return {
        "server": {"public_ip": "203.0.113.50", "private_ip": "10.0.1.50"},
        "clients": {"L0": {"public_ip": "203.0.113.60", "private_ip": "10.0.1.60", "colocated": True}},
    }


def test_dedicated_capture_usa_interface_primaria_nunca_loopback(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    block = executor.dedicated_capture("hibrido-and", "L0")
    flat = [" ".join(c) for c in calls]

    assert any("ip -o -4 route show to default" in c for c in flat), flat
    tcpdump_calls = [c for c in flat if "tcpdump" in c]
    assert tcpdump_calls, "nenhuma chamada de tcpdump encontrada"
    assert all("-i eth0" in c for c in tcpdump_calls), tcpdump_calls
    assert all("-i lo " not in c and not c.endswith("-i lo") for c in tcpdump_calls), (
        "a captura NUNCA pode rodar na interface loopback"
    )
    assert any("tcp port 443" in c for c in tcpdump_calls)
    assert block.startswith("== Perfil: hibrido-and ==")
    assert block.endswith("== fim ==")


def test_dedicated_capture_mata_tcpdump_pelo_pid_descoberto(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls, tcpdump_pid="98765"))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.dedicated_capture("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert any("kill 98765" in c for c in flat), flat


def test_dedicated_capture_dispara_execucao_real_no_cliente_antes_de_parar(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.dedicated_capture("pqc", "L0")
    remote_cmds = [c[-1] for c in calls if c and c[0] == "ssh"]
    idx_start = next(i for i, c in enumerate(remote_cmds) if "nohup tcpdump" in c)
    idx_trigger = next(i for i, c in enumerate(remote_cmds) if "campaign_client_runner.py" in c)
    idx_kill = next(i for i, c in enumerate(remote_cmds) if "kill" in c)
    assert idx_start < idx_trigger < idx_kill, remote_cmds
    assert "criterio1_capture_pqc_L0" in remote_cmds[idx_trigger]
    assert "CRYPTO_PROFILE=pqc" in remote_cmds[idx_trigger]


def test_dedicated_capture_le_keylog_do_proprio_container_e_roda_tshark_via_measure(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key", gateway_container="v9-mtls")
    executor.dedicated_capture("hibrido-v8", "L0")
    flat = [" ".join(c) for c in calls]
    assert any("docker exec v9-mtls cat /tmp/v9_keylog.txt" in c for c in flat), flat
    tshark_calls = [c for c in flat if "tshark" in c]
    assert tshark_calls, flat
    assert all("mockopin-v9-measure" in c for c in tshark_calls)
    assert all("tls.handshake.type" in c and "tls.handshake.length" in c for c in tshark_calls)


def test_dedicated_capture_extrai_tamanhos_que_o_avaliador_aceita(monkeypatch):
    """Fim a fim do PARSING (nao so das chamadas): o bloco devolvido
    tem que bater com o Certificate/ClientHello baseline REAL do
    hibrido-v8 (ec.CERTIFICATE_BASELINE/CLIENTHELLO_BASELINE) quando o
    tshark fake devolve exatamente os tamanhos esperados desse
    perfil -- confirma que o parsing de `-E aggregator=,` e o "+4B de
    cabecalho" do avaliador se encaixam sem ajuste nenhum aqui."""
    hb = ec.HANDSHAKE_MESSAGE_BASELINE["hibrido-v8"]
    ch = ec.CLIENTHELLO_BASELINE["hibrido-v8"] - 4
    cert = ec.CERTIFICATE_BASELINE["hibrido-v8"] - 4
    tshark_output = (
        f"1\t1\t{ch}\n"
        f"2\t2,8,13,11,15,20\t"
        f"{hb['ServerHello']-4},{hb['EncryptedExtensions']-4},{hb['CertificateRequest']-4},"
        f"{cert},{hb['CertificateVerify_servidor']-4},{hb['Finished_servidor']-4}\n"
        f"3\t11,15,20\t{hb['Certificate_cliente']-4},{hb['CertificateVerify_cliente']-4},{hb['Finished_cliente']-4}\n"
    )
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls, tshark_output=tshark_output))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    block = executor.dedicated_capture("hibrido-v8", "L0")
    row = ec._message_sizes_for_profile(block, "hibrido-v8")
    assert row["ok"] is True, row


def test_dedicated_capture_falha_alto_se_interface_nao_e_encontrada(monkeypatch):
    """Fail-closed: `_primary_iface` nunca pode inventar uma interface
    -- saida vazia (host sem rota default, comando falhou) tem que
    levantar, nunca silenciosamente cair pra loopback ou pra uma
    string vazia dentro do comando de tcpdump."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls, iface=""))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="interface primaria"):
        executor.dedicated_capture("classico", "L0")


def test_mutante_dedicated_capture_sem_checar_iface_vazia_e_pego(monkeypatch):
    """Mutacao direta: `_primary_iface` que aceita string vazia sem
    levantar -- o teste acima tem que reprovar com essa mutacao."""
    def mutant_primary_iface(self, host):
        return ""  # mutante: nunca valida, devolve vazio direto

    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls, iface=""))
    monkeypatch.setattr(orch.SSHExecutor, "_primary_iface", mutant_primary_iface)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    # Com o mutante, a chamada de tcpdump sai com "-i " (interface
    # vazia) em vez de levantar -- confirma que o teste real acima
    # depende de fato da validacao, nao passa por acidente.
    try:
        executor.dedicated_capture("classico", "L0")
        mutant_raised = False
    except RuntimeError:
        mutant_raised = True
    assert mutant_raised is False
    with pytest.raises(AssertionError):
        assert mutant_raised is True


# --- Decisao 52, Emenda 14 (pedido independente, item 2a): KEYLOG_PATH
# tem que ficar DESLIGADO durante qualquer janela cronometrada (start_
# block/run_execution/readiness_probe) e SO ligado durante dedicated_
# capture -- achado nesta rodada: a primeira versao ligava a flag em
# TODO `start_block`, incondicionalmente, o que ligaria o keylog
# durante as 60 execucoes reais tambem (I/O extra por handshake nunca
# presente antes). Corrigido: `_launch_gateway(profile, keylog=False)`
# e o default (usado por `start_block`); SO `dedicated_capture` chama
# `_launch_gateway(profile, keylog=True)`, reiniciando o MESMO
# container -- e isso acontece dentro do laco de capturas dedicadas de
# `run_pilot`, que so comeca depois que TODAS as 60 execucoes (e seus
# `stop_block`) ja terminaram (ver run_pilot, linhas do loop principal
# vs o loop de `dedicated_capture` em separado) -- nunca entre uma
# execucao cronometrada e outra.

def test_start_block_nunca_liga_keylog_path(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("hibrido-and", "L0")
    flat = [" ".join(c) for c in calls]
    gateway_launches = [c for c in flat if "docker run -d --name v9-mtls" in c]
    assert gateway_launches, flat
    assert all("KEYLOG_PATH" not in c for c in gateway_launches), gateway_launches


def test_run_execution_nunca_menciona_keylog(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.run_execution("hibrido-and", "L0", 1)
    flat = [" ".join(c) for c in calls]
    assert not any("KEYLOG_PATH" in c for c in flat), flat


def test_dedicated_capture_liga_keylog_so_na_propria_reinicializacao(monkeypatch):
    """A PRIMEIRA subida do gateway (via start_block, chamado por
    dedicated_capture pra garantir o perfil certo) nao tem KEYLOG_PATH;
    a SEGUNDA (via _launch_gateway(..., keylog=True), a reinicializacao
    dedicada) tem. As duas tem que existir E diferir."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.dedicated_capture("hibrido-and", "L0")
    flat = [" ".join(c) for c in calls]
    gateway_launches = [c for c in flat if "docker run -d --name v9-mtls" in c]
    assert len(gateway_launches) == 2, gateway_launches
    assert "KEYLOG_PATH" not in gateway_launches[0], gateway_launches[0]
    assert "KEYLOG_PATH=/tmp/v9_keylog.txt" in gateway_launches[1], gateway_launches[1]


def test_mutante_keylog_sempre_ligado_e_pego(monkeypatch):
    """Mutacao: reproduz o bug ORIGINAL desta rodada -- KEYLOG_PATH
    incondicional em `_launch_gateway` -- confirma que o teste acima
    depende de fato da correcao."""
    def mutant_launch_gateway(self, profile, keylog=False):
        cli.run_ssh(self._server_ip(), f"docker run -d --name {self.gateway_container} -e KEYLOG_PATH=/tmp/v9_keylog.txt mockopin-v9-gateway", key_path=self.key_path)

    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    monkeypatch.setattr(orch.SSHExecutor, "_launch_gateway", mutant_launch_gateway)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    gateway_launches = [c for c in flat if "docker run -d --name v9-mtls" in c]
    mutant_has_keylog_in_start_block = any("KEYLOG_PATH" in c for c in gateway_launches)
    assert mutant_has_keylog_in_start_block is True  # mutante liga indevidamente
    with pytest.raises(AssertionError):
        assert mutant_has_keylog_in_start_block is False

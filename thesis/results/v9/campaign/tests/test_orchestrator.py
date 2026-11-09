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


def test_run_pilot_grade_customizada_com_capturas_cobre_so_a_grade_pedida(tmp_path):
    """Achado real (encontrado e corrigido nesta rodada): o laco de
    capturas dedicadas usava PROFILES/ROUTES (globais do piloto,
    4x3=12) hardcoded, nunca os parametros `profiles`/`routes` da
    propria funcao -- uma grade customizada (ex.: a do ensaio
    multi-regiao/campanha oficial) com `skip_dedicated_captures=False`
    teria SEMPRE as 12 capturas do piloto, nunca a grade real pedida.
    Prova com uma grade de 2 perfis x 2 rotas (nunca igual a 4x3)."""
    manifest = orch.run_pilot(
        orch.LocalExecutor(), seed=1, out_dir=tmp_path,
        n_per_profile=1, routes=["L123", "L14"], profiles=["classico", "pqc"],
    )
    assert manifest["total_capturas"] == 4, "2 perfis x 2 rotas = 4, nunca os 12 do piloto"
    capturas = list(Path(manifest["capturas_dir"]).glob("*.log"))
    assert len(capturas) == 4
    capture_names = {p.stem for p in capturas}
    assert capture_names == {"classico_L123", "classico_L14", "pqc_L123", "pqc_L14"}
    # nenhuma rota/perfil do piloto (L0/L219/L325, hibrido-v8/hibrido-and) deveria aparecer.
    assert not any("L0" in n or "L219" in n or "L325" in n or "hibrido" in n for n in capture_names), capture_names


def test_mutante_run_pilot_capturas_fixas_no_piloto_e_pego(tmp_path):
    """Mutante: reproduz o comportamento ANTIGO (capturas sempre sobre
    PROFILES/ROUTES do piloto) -- confirma que o teste real acima
    reprovaria essa regressao."""
    capturas_dir = tmp_path / "mutante_capturas"
    capturas_dir.mkdir()
    executor = orch.LocalExecutor()
    for profile in orch.PROFILES:  # mutante: ignora os parametros da chamada, usa sempre os globais
        for route in orch.ROUTES:
            block = executor.dedicated_capture(profile, route, capturas_dir=capturas_dir)
            (capturas_dir / f"{profile}_{route}.log").write_text(block, encoding="utf-8")
    mutant_capturas = list(capturas_dir.glob("*.log"))
    assert len(mutant_capturas) == 12, "mutante reproduz os 12 do piloto, nunca os 4 da grade customizada"
    assert len(mutant_capturas) != 4


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
    "pqc-signer": "sha256:" + "4" * 64,
    # Decisao 83: backend de negocio da v8, portado pro piloto v9.
    "psql": "sha256:" + "5" * 64,
    "localstack": "sha256:" + "6" * 64,
    "mongodb": "sha256:" + "7" * 64,
    "auth": "sha256:" + "8" * 64,
    "mongo_seed": "sha256:" + "9" * 64,
    "mockapi": "sha256:" + "0" * 64,
}
_FAKE_DOCKER_IMAGE_NAMES = {
    "gateway": "mockopin-v9-gateway", "proxy": "mockopin-v9-proxy",
    "measure": "mockopin-v9-measure", "pqc-signer": "mockopin-pqc-signer",
    "psql": "postgres", "localstack": "localstack/localstack",
    "mongodb": "mongo", "auth": "insurance-server-lambdas-auth",
    "mongo_seed": "insurance-server-lambdas-mongo_seed", "mockapi": "raidiam-insurance-lambdas",
}
# Decisao 68 (Emenda -- substitui a verificacao por Image ID):
# conteudo FALSO, deterministico, por imagem -- o sha256 de cada um
# e o `tar_sha256` que `_fake_pins()` usa, pra `_deliver_image` (que
# agora confere o .tar local ANTES de qualquer scp) nunca abortar
# por acidente nos testes que nao estao testando essa conferencia.
_FAKE_TAR_BYTES = {key: f"tar falso de {key}, so para teste\n".encode() for key in _FAKE_DOCKER_IMAGE_NAMES}
_FAKE_TAR_SHA256 = {key: hashlib.sha256(b).hexdigest() for key, b in _FAKE_TAR_BYTES.items()}
_FAKE_LAYERS = {
    "gateway": ["sha256:" + "a1" * 32, "sha256:" + "a2" * 32],
    "proxy": ["sha256:" + "a1" * 32, "sha256:" + "b2" * 32],
    "measure": ["sha256:" + "a1" * 32, "sha256:" + "c2" * 32],
    "pqc-signer": ["sha256:" + "d1" * 32, "sha256:" + "d2" * 32],
    "psql": ["sha256:" + "e1" * 32], "localstack": ["sha256:" + "e2" * 32],
    "mongodb": ["sha256:" + "e3" * 32], "auth": ["sha256:" + "e4" * 32],
    "mongo_seed": ["sha256:" + "e5" * 32], "mockapi": ["sha256:" + "e6" * 32],
}
_FAKE_CONFIG = {
    "gateway": {"Entrypoint": ["/gateway"], "Cmd": None, "Env": ["PATH=/usr/bin"], "ExposedPorts": {"443/tcp": {}}},
    "proxy": {"Entrypoint": ["/proxy"], "Cmd": None, "Env": ["PATH=/usr/bin"], "ExposedPorts": None},
    "measure": {"Entrypoint": ["/usr/local/bin/measure.sh"], "Cmd": None, "Env": ["PATH=/usr/bin"], "ExposedPorts": None},
    "pqc-signer": {"Entrypoint": ["docker-entrypoint.sh"], "Cmd": ["node", "sign.mjs"], "Env": ["PATH=/usr/bin"], "ExposedPorts": None},
    "psql": {"Entrypoint": ["docker-entrypoint.sh"], "Cmd": ["postgres"], "Env": ["PATH=/usr/bin"], "ExposedPorts": {"5432/tcp": {}}},
    "localstack": {"Entrypoint": ["docker-entrypoint.sh"], "Cmd": None, "Env": ["PATH=/usr/bin"], "ExposedPorts": {"4566/tcp": {}}},
    "mongodb": {"Entrypoint": ["docker-entrypoint.sh"], "Cmd": ["mongod"], "Env": ["PATH=/usr/bin"], "ExposedPorts": {"27017/tcp": {}}},
    "auth": {"Entrypoint": ["docker-entrypoint.sh"], "Cmd": ["npm", "run", "dev"], "Env": ["PATH=/usr/bin"], "ExposedPorts": {"3000/tcp": {}}},
    "mongo_seed": {"Entrypoint": ["docker-entrypoint.sh"], "Cmd": ["/start.sh"], "Env": ["PATH=/usr/bin"], "ExposedPorts": None},
    "mockapi": {"Entrypoint": ["java", "-jar", "/home/app/application.jar"], "Cmd": None, "Env": ["PATH=/usr/bin"], "ExposedPorts": {"8080/tcp": {}}},
}
_FAKE_BINARY_PATH = {"gateway": "/gateway", "proxy": "/proxy", "measure": None, "pqc-signer": None,
                      "psql": None, "localstack": None, "mongodb": None, "auth": None,
                      "mongo_seed": None, "mockapi": None}
_FAKE_PROXY_BINARY_SHA256 = "b" * 64


def _fake_pins(gateway_sha256=_FAKE_GATEWAY_SHA256, image_ids=None, layers=None, config=None, tar_sha256=None):
    image_ids = image_ids or _FAKE_IMAGE_IDS
    layers = layers or _FAKE_LAYERS
    config = config or _FAKE_CONFIG
    tar_sha256 = tar_sha256 or _FAKE_TAR_SHA256
    binary_sha256_by_key = {"gateway": gateway_sha256, "proxy": _FAKE_PROXY_BINARY_SHA256, "measure": None, "pqc-signer": None,
                             "psql": None, "localstack": None, "mongodb": None, "auth": None,
                             "mongo_seed": None, "mockapi": None}
    return {"images": {
        key: {
            "docker_image": name, "image_id": image_ids[key],
            "tar_sha256": tar_sha256[key], "rootfs_layers": layers[key], "config_subset": config[key],
            "binary_path_in_image": _FAKE_BINARY_PATH[key], "binary_sha256": binary_sha256_by_key[key],
        }
        for key, name in _FAKE_DOCKER_IMAGE_NAMES.items()
    }}


@pytest.fixture(autouse=True)
def _staged_images_dir(tmp_path, monkeypatch):
    """Decisao 59: `_deliver_image`/`_verify_gateway_binary` agora
    leem arquivos LOCAIS de `self.images_staging_dir` (default
    `Path.home() / "images"`, onde `deliver_images.py` estagiaria de
    verdade no controle) em vez de rodar docker -- monkeypatcha
    `Path.home()` pra um diretorio de teste com os 4 `.tar` (conteudo
    falso -- so a PRESENCA do arquivo importa, o conteudo nunca e lido
    por `_deliver_image`) + `gateway_binary_info.json`/binario
    `gateway` fake (mesmo sha256 que `_fake_pins()` ja usa). Autouse --
    todo teste deste arquivo ja comeca com isso presente."""
    fake_home = tmp_path / "fake_home"
    images_dir = fake_home / "images"
    images_dir.mkdir(parents=True)
    for key, tar_bytes in _FAKE_TAR_BYTES.items():
        # Decisao 68: o conteudo tem que ser EXATAMENTE o que
        # `_FAKE_TAR_SHA256`/`_fake_pins()` esperam -- `_deliver_image`
        # agora confere o sha256 do .tar local ANTES de qualquer scp.
        (images_dir / f"{key}.tar").write_bytes(tar_bytes)
    (images_dir / "gateway").write_bytes(_FAKE_GATEWAY_BINARY_BYTES)
    (images_dir / "gateway_binary_info.json").write_text(json.dumps({
        "sha256": _FAKE_GATEWAY_SHA256,
        "go_version_m": "/verify/gateway: go1.27.3\n",
        "go_build_version": "go1.27.3",
        "toolchain_build_metadata": {"go_tag": "go1.27.3"},
    }), encoding="utf-8")
    monkeypatch.setattr(orch.Path, "home", lambda: fake_home)
    return images_dir


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


def _fake_image_id_for_remote_cmd(remote_cmd, image_ids=None, layers=None, config=None, binary_shas=None):
    """Decisao 68 (Emenda): respostas fake pras 4 chamadas de
    identidade que `_deliver_image` faz no HOST, pos `docker load`
    -- `docker image inspect --format '{{.Id}}'` (informativo,
    Decisao 68), `'{{json .RootFS.Layers}}'`, `'{{json .Config}}'`, e
    `docker run --rm --entrypoint sha256sum <imagem> <binario>`.
    Devolve None se o comando nao for nenhuma dessas."""
    image_ids = image_ids or _FAKE_IMAGE_IDS
    layers = layers or _FAKE_LAYERS
    config = config or _FAKE_CONFIG
    binary_shas = binary_shas or {"gateway": _FAKE_GATEWAY_SHA256, "proxy": _FAKE_PROXY_BINARY_SHA256}
    # Decisao 83: "mongo" (mongodb) e substring de "insurance-server-
    # lambdas-mongo_seed" (mongo_seed) -- escolhe o nome MAIS LONGO que
    # bate, nunca o primeiro por ordem de dict (ordem-dependente e
    # frágil exatamente nesse caso).
    matches = [k for k, name in _FAKE_DOCKER_IMAGE_NAMES.items() if name in remote_cmd]
    key = max(matches, key=lambda k: len(_FAKE_DOCKER_IMAGE_NAMES[k])) if matches else None
    if key is None:
        return None
    if "RootFS.Layers" in remote_cmd:
        return json.dumps(layers[key]) + "\n"
    if "{{json .Config}}" in remote_cmd or "json .Config}}" in remote_cmd:
        return json.dumps(config[key]) + "\n"
    if "entrypoint sha256sum" in remote_cmd and "docker run" in remote_cmd:
        bp = _FAKE_BINARY_PATH[key]
        sha = binary_shas.get(key)
        if bp and sha:
            return f"{sha}  {bp}\n"
        return None
    if "docker image inspect" in remote_cmd:
        return f"{image_ids[key]}\n"
    return None


def _fake_tcp_preflight_call(remote_cmd):
    """Decisao 58, achado 18: `_tcp_preflight` roda via SSH antes de
    qualquer outra coisa em `start_block` -- resposta fake generica
    (sempre OK) pra nao quebrar nenhum teste existente que nao esta
    testando a sondagem TCP em si. Devolve None se o comando nao for
    essa chamada."""
    if "/dev/tcp/" in remote_cmd:
        return _SimpleProc(stdout="OK\n")
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
        tcp_preflight = _fake_tcp_preflight_call(remote_cmd)
        if tcp_preflight is not None:
            return tcp_preflight
        if "sha256sum -c" in remote_cmd:
            return _SimpleProc(stdout=f"gateway: OK\n")
        if "sha256sum /gateway" in remote_cmd:
            return _SimpleProc(stdout=f"{_FAKE_GATEWAY_SHA256}  /gateway\n")
        if "listening on" in remote_cmd:
            # Decisao 69: `_launch_gateway` agora falha rapido se o laco
            # de espera nunca ver "FOUND" no stdout -- fake sempre acha
            # de primeira (comportamento feliz default; testes que
            # precisam simular o container nunca subindo sobrescrevem
            # este fake especificamente).
            return _SimpleProc(stdout="FOUND\n")
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


# --- Decisao 75, item 2 (pedido do Luciano): qualquer excecao DENTRO
# do diagnostico (ex: certs_dir ausente, cryptography/arquivo faltando)
# nunca pode derrubar o smoke gate inteiro -- so marca a linha daquele
# perfil como needs_decision, igual a um desvio != 0 normal, e
# smoke_ok continua decidido SO pelos criterios oficiais.

def test_bytes_diagnostic_excecao_pausa_mas_nunca_quebra_o_smoke_gate(tmp_path, monkeypatch):
    def broken_diagnostic(log_text, profile, certs_dir):
        if profile == "pqc":
            raise FileNotFoundError(f"certs_dir ausente: {certs_dir}")
        return {"profile": profile, "ok": True}

    monkeypatch.setattr(orch, "_bytes_diagnostic_for_profile", broken_diagnostic)
    manifest = orch.run_smoke_gate(orch.LocalExecutor(), seed=1, out_dir=tmp_path)
    broken_row = next(r for r in manifest["bytes_diagnostic_rows"] if r["profile"] == "pqc")
    assert broken_row["ok"] is False
    assert "FileNotFoundError" in broken_row["note"]
    assert manifest["bytes_diagnostic_needs_decision"] is True
    # o mutante real: se a excecao propagasse, este teste nunca chegaria
    # aqui (run_smoke_gate teria estourado) -- smoke_ok so cai se os
    # criterios OFICIAIS (total_execucoes/failures/capture_proof_ok)
    # falharem, nunca por conta do diagnostico.
    assert manifest["smoke_ok"] is True


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
        tcp_preflight = _fake_tcp_preflight_call(remote_cmd)
        if tcp_preflight is not None:
            return tcp_preflight
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
        tcp_preflight = _fake_tcp_preflight_call(remote_cmd)
        if tcp_preflight is not None:
            return tcp_preflight
        if "sha256sum -c" in remote_cmd:
            return _SimpleProc(stdout="gateway: OK\n")
        if "listening on" in remote_cmd:
            return _SimpleProc(stdout="FOUND\n")
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
        if "listening on" in remote_cmd:
            return _SimpleProc(stdout="FOUND\n")
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
    with pytest.raises(RuntimeError):
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


# --- Decisao 68 (Emenda -- substitui a verificacao por Image ID):
# mutantes pedidos explicitamente -- tar adulterado reprova, camada
# adulterada reprova, binario (dentro da imagem) adulterado reprova,
# correto passa. Image ID nunca mais e motivo de aborto (so
# informativo).

def test_deliver_image_aborta_se_tar_local_adulterado(monkeypatch):
    """O .tar ja estagiado no controle foi adulterado (sha256 nao
    bate com `tar_sha256` pinado) -- tem que abortar ANTES de
    qualquer scp pro host, nunca so depois do load."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    # adultera o .tar do gateway DEPOIS que a fixture autouse ja o
    # escreveu certo -- simula corrupcao/adulteracao real.
    (executor.images_staging_dir / "gateway.tar").write_bytes(b"tar ADULTERADO\n")
    with pytest.raises(RuntimeError, match="sha256 do .tar"):
        executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    # Decisao 83: start_block entrega o backend (6 imagens) ANTES do
    # gateway -- esses scps sao esperados; so o scp do GATEWAY em si
    # (adulterado) nunca pode acontecer.
    assert not any(c[0] == "scp" and "gateway.tar" in " ".join(c) for c in calls), (
        "nenhum scp do gateway.tar pode acontecer com ele adulterado -- " + str(flat))
    assert not any("docker run -d --name v9-mtls" in c for c in flat), flat


def test_deliver_image_aborta_se_camada_adulterada(monkeypatch):
    """O host, pos `docker load`, devolve `RootFS.Layers` diferentes
    das pinadas (imagem de origem diferente, mesmo com o .tar
    passando a conferencia de transporte) -- tem que abortar ANTES
    de proxy/signer."""
    calls = []

    def fake_run(argv, timeout=None):
        base = _fake_run_factory(calls)(argv, timeout)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "RootFS.Layers" in remote_cmd and "mockopin-v9-gateway" in remote_cmd:
            return _SimpleProc(stdout=json.dumps(["sha256:" + "9" * 64]) + "\n")
        return base

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="identidade nao confere"):
        executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert not any("docker run -d --name v9-mtls" in c for c in flat), flat
    assert not any("start_tls_kem_proxy" in c for c in flat), flat
    delivered = {v["image_key"]: v for v in executor.image_delivery_verifications}
    assert delivered["gateway"]["layers_ok"] is False


def test_deliver_image_aborta_se_config_adulterada(monkeypatch):
    """O host devolve um `.Config` (Entrypoint/Cmd/Env/ExposedPorts)
    diferente do pinado -- tambem reprova, mesmo com camadas e tar
    corretos."""
    calls = []

    def fake_run(argv, timeout=None):
        base = _fake_run_factory(calls)(argv, timeout)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "{{json .Config}}" in remote_cmd and "mockopin-v9-gateway" in remote_cmd:
            return _SimpleProc(stdout=json.dumps({"Entrypoint": ["/bin/sh"], "Cmd": None, "Env": [], "ExposedPorts": None}) + "\n")
        return base

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="identidade nao confere"):
        executor.start_block("classico", "L0")
    delivered = {v["image_key"]: v for v in executor.image_delivery_verifications}
    assert delivered["gateway"]["config_ok"] is False


def test_deliver_image_aborta_se_binario_na_imagem_adulterado(monkeypatch):
    """O sha256 do binario DENTRO do container carregado no host
    (proxy, que tem binary_path_in_image) nao bate com o pinado --
    camadas/config/tar corretos, mas o binario real divergiu."""
    calls = []

    def fake_run(argv, timeout=None):
        base = _fake_run_factory(calls)(argv, timeout)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "entrypoint sha256sum" in remote_cmd and "mockopin-v9-proxy" in remote_cmd:
            return _SimpleProc(stdout="9" * 64 + "  /proxy\n")
        return base

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="identidade nao confere"):
        executor.start_block("classico", "L0")
    # a entrega do gateway (antes do proxy) tem que ter passado --
    # so o proxy, com o binario adulterado, reprova.
    delivered = {v["image_key"]: v for v in executor.image_delivery_verifications}
    assert delivered["gateway"]["ok"] is True
    assert delivered["proxy"]["binary_ok"] is False
    assert delivered["proxy"]["ok"] is False


def test_deliver_image_correto_passa_com_nova_verificacao(monkeypatch):
    """Tar, camadas, config e binario todos corretos -- `_deliver_
    image` tem que passar pras 3 imagens que `start_block` sempre
    entregava (gateway/proxy/pqc-signer) MAIS as 6 do backend de
    negocio (Decisao 83), sem nenhum Image ID sendo conferido."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("classico", "L0")
    delivered_keys = {v["image_key"] for v in executor.image_delivery_verifications}
    assert delivered_keys == {"gateway", "proxy", "pqc-signer"} | set(orch.deliver_images.BACKEND_IMAGE_KEYS)
    assert all(v["ok"] for v in executor.image_delivery_verifications)
    for v in executor.image_delivery_verifications:
        assert v["ok"] is True, v
        assert v["layers_ok"] is True and v["config_ok"] is True and v["binary_ok"] is True, v
    flat = [" ".join(c) for c in calls]
    assert any("docker run -d --name v9-mtls" in c for c in flat), flat


def test_deliver_image_registra_tempo_e_tamanho_do_2o_salto(monkeypatch):
    """Decisao 60, item 4: cada entrega registra `elapsed_seconds`
    (real, medido -- nunca estimado) e `tar_bytes`, pro ensaio
    reportar por host/imagem. `slow` marca so acima de
    DELIVERY_SLOW_THRESHOLD_SECONDS -- nunca aborta por conta
    propria."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("classico", "L0")
    for v in executor.image_delivery_verifications:
        assert isinstance(v["elapsed_seconds"], float) and v["elapsed_seconds"] >= 0, v
        assert v["tar_bytes"] > 0, v
        assert v["slow"] is False, v  # fake e instantaneo, nunca passa de 10min


def test_mutante_entrega_lenta_e_marcada_slow(monkeypatch):
    """Mutacao: forca uma entrega 'lenta' via monkeypatch de time.monotonic
    -- confirma que `slow` de fato depende do tempo medido, nao e
    sempre False por acidente."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")

    real_monotonic = orch.time.monotonic
    call_count = [0]

    def fake_monotonic():
        call_count[0] += 1
        # primeira chamada (t0, dentro de _deliver_image) normal; as
        # seguintes avancam 601s, simulando uma entrega lenta.
        return real_monotonic() if call_count[0] == 1 else real_monotonic() + 601

    monkeypatch.setattr(orch.time, "monotonic", fake_monotonic)
    executor.start_block("classico", "L0")
    assert any(v["slow"] for v in executor.image_delivery_verifications), executor.image_delivery_verifications


# --- Decisao 58 (pedido independente, item 1): tabela de dependencias
# do caminho remoto -- achado real (19): start_block chamava
# of.start_pqc_signer_service() no cliente sem NUNCA entregar
# mockopin-pqc-signer pra la (mesma classe de bug que a v8 encontrou
# em deliver_images.sh). `_assert_every_used_image_was_delivered_first`
# e o "executor simulado que registra os comandos e as imagens"
# pedido -- generico, reusavel por qualquer teste que exercite
# start_block/dedicated_capture.

_IMAGE_USAGE_MARKERS = {
    # Marcador distinto do proprio comando de entrega (scp do .tar
    # LOCAL pro host, Decisao 59) -- senao a entrega conta como "uso"
    # dela mesma (o nome da imagem aparece nos dois comandos).
    "gateway": "docker run -d --name v9-mtls",
    "measure": "--entrypoint tshark mockopin-v9-measure",
    "proxy": "start_tls_kem_proxy",
    "pqc-signer": "start_pqc_signer_service",
}


def _assert_every_used_image_was_delivered_first(calls):
    """Pra cada imagem com um marcador de USO presente em `calls`,
    confere que uma entrega real (scp do `<imagem>.tar` JA ESTAGIADO
    no controle pro host, via `_deliver_image`, Decisao 59) apareceu
    num indice ANTERIOR na mesma lista de chamadas -- fail-closed:
    imagem usada sem entrega registrada, ou entregue DEPOIS do uso,
    reprova."""
    flat = [" ".join(c) for c in calls]
    delivered_at = {}
    for i, c in enumerate(flat):
        for key in _IMAGE_USAGE_MARKERS:
            if f"{key}.tar ec2-user@" in c and key not in delivered_at:
                delivered_at[key] = i
    for key, marker in _IMAGE_USAGE_MARKERS.items():
        usage_indices = [i for i, c in enumerate(flat) if marker in c]
        if not usage_indices:
            continue  # esta imagem nunca foi usada nesta chamada -- nada a conferir
        assert key in delivered_at, (
            f"imagem '{key}' foi usada ({marker!r}) mas NUNCA entregue via _deliver_image -- " + str(flat)
        )
        assert delivered_at[key] < min(usage_indices), (
            f"imagem '{key}' foi usada ({marker!r}) ANTES de ser entregue (entrega no indice "
            f"{delivered_at[key]}, uso no indice {min(usage_indices)}) -- " + str(flat)
        )


def test_toda_imagem_usada_no_caminho_remoto_foi_entregue_antes(monkeypatch):
    """Exercita start_block (via dedicated_capture, que tambem entrega
    e usa 'measure') e confere as 4 imagens reais do caminho remoto
    (gateway/proxy/pqc-signer/measure) -- este e o teste que teria
    pegado o achado 19 se existisse antes desta rodada."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.dedicated_capture("classico", "L0")
    _assert_every_used_image_was_delivered_first(calls)


def test_mutante_pqc_signer_nao_entregue_e_pego(monkeypatch):
    """Mutacao: reproduz o bug ORIGINAL do achado 19 -- `_deliver_image`
    nunca entrega 'pqc-signer' (como no codigo antes desta rodada) --
    o teste acima, reaplicado sobre esta mutacao, tem que reprovar."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    real_deliver_image = orch.SSHExecutor._deliver_image

    def mutant_deliver_image(self, image_key, host):
        if image_key == "pqc-signer":
            return  # mutante: nunca entrega -- reproduz o achado 19 original
        return real_deliver_image(self, image_key, host)

    monkeypatch.setattr(orch.SSHExecutor, "_deliver_image", mutant_deliver_image)
    executor.start_block("classico", "L0")
    with pytest.raises(AssertionError, match="pqc-signer"):
        _assert_every_used_image_was_delivered_first(calls)


# --- Decisao 59 (achado real: o controle nunca roda docker, nem SSH
# chega do operador direto no servidor/cliente -- so do controle,
# Security Group em main.tf). A entrega por .tar JA ESTAGIADO no
# controle (deliver_images.py, rodando na maquina do operador,
# entrega so ATE o controle) e a UNICA via que SSHExecutor usa.

def test_deliver_image_nunca_invoca_docker_localmente(monkeypatch):
    """`cli._run` com `argv[0] == "docker"` seria o processo QUE RODA
    SSHExecutor chamando docker na sua PROPRIA maquina -- so faz
    sentido se essa maquina for o operador (tem Docker); rodando do
    controle (onde SSHExecutor roda de verdade, Decisao 59), isso
    quebraria ("docker: command not found" ou pior, nenhum Docker
    instalado la de proposito). Nenhuma chamada deste tipo pode
    acontecer em start_block/dedicated_capture."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.dedicated_capture("classico", "L0")
    local_docker_calls = [c for c in calls if c and c[0] == "docker"]
    assert not local_docker_calls, (
        "SSHExecutor nunca pode invocar `docker` localmente (o controle nao tem Docker) -- " + str(local_docker_calls)
    )


def test_deliver_image_nunca_faz_docker_save_pipe_ssh(monkeypatch):
    """Reproduz o padrao ANTIGO (Decisao 55, corrigido na Decisao 59) --
    `sh -c "docker save <imagem> | ssh ... docker load"` -- nenhuma
    chamada deste arquivo pode conter esse padrao: a entrega agora e
    scp de um .tar LOCAL (ja estagiado) pro host, nunca um pipe que
    exige Docker na maquina que executa SSHExecutor."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.dedicated_capture("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert not any("docker save" in c for c in flat), (
        "nenhuma chamada pode fazer `docker save` -- isso e responsabilidade exclusiva de "
        "deliver_images.py, na maquina do OPERADOR -- " + str(flat)
    )


def test_deliver_image_falha_alto_se_tar_nao_esta_estagiado(monkeypatch, tmp_path):
    """Fail-closed: se `deliver_images.py` nunca rodou (o .tar nao
    esta no diretorio de estagiamento), `_deliver_image` tem que
    levantar ANTES de tentar qualquer scp/ssh pro host -- nunca
    silenciosamente tentar entregar um arquivo inexistente."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    empty_staging = tmp_path / "images_vazio"
    empty_staging.mkdir()
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key", images_staging_dir=str(empty_staging))
    with pytest.raises(RuntimeError, match="rode deliver_images.py primeiro"):
        executor._deliver_image("gateway", executor._server_ip())
    assert calls == [], "nenhuma chamada scp/ssh pode acontecer sem o .tar estagiado -- " + str(calls)


# --- Decisao 81 (achado real, ao vivo, numa fleet nova): capture_
# ready_check() so LIA se mockopin-v9-measure ja existia no servidor
# -- nunca entregava. Numa fleet recem-provisionada, nada jamais
# tinha entregue essa imagem antes do primeiro dedicated_capture (que
# so roda DEPOIS da porta de fumaca passar) -- preflight reprovava
# sempre, por falta de uma imagem que ele mesmo nunca tentava
# entregar.

def test_capture_ready_check_entrega_measure_antes_de_rodar_o_probe(monkeypatch):
    order = []
    inventory = _inventory_l0()
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")

    def fake_deliver_image(self, image_key, host):
        order.append(("deliver", image_key, host))

    def fake_run_capture_preflight(hosts, key_path=None):
        order.append(("probe", tuple(hosts)))
        return {"go": True, "checks": []}

    monkeypatch.setattr(orch.SSHExecutor, "_deliver_image", fake_deliver_image)
    monkeypatch.setattr(orch.preflight, "run_capture_preflight", fake_run_capture_preflight)

    result = executor.capture_ready_check()
    assert result == {"go": True, "checks": []}
    assert order == [("deliver", "measure", executor._server_ip()),
                      ("probe", (executor._server_ip(),))], (
        "a entrega de 'measure' tem que acontecer ANTES do probe -- " + str(order)
    )


def test_mutante_capture_ready_check_nunca_entrega_measure_e_pego(monkeypatch):
    """Mutacao: capture_ready_check() volta a so rodar o probe, sem
    entregar 'measure' primeiro -- o teste acima tem que reprovar com
    essa mutacao, provando que depende de fato da entrega."""
    inventory = _inventory_l0()
    executor = orch.SSHExecutor(inventory, key_path="/fake/key")
    calls = []
    monkeypatch.setattr(orch.SSHExecutor, "_deliver_image",
                         lambda self, image_key, host: calls.append((image_key, host)))
    monkeypatch.setattr(orch.preflight, "run_capture_preflight", lambda hosts, key_path=None: {"go": True, "checks": []})

    def mutant_capture_ready_check(self):
        # mutante: nunca chama _deliver_image, vai direto pro probe
        return orch.preflight.run_capture_preflight([self._server_ip()], key_path=self.key_path)

    monkeypatch.setattr(orch.SSHExecutor, "capture_ready_check", mutant_capture_ready_check)
    executor.capture_ready_check()
    assert calls == [], "mutante nunca deveria ter entregado measure -- confirma que o teste real dependia disso"


def test_capture_ready_check_cobre_os_3_servidores_em_modo_campanha(monkeypatch):
    """Lacuna encontrada e fechada agora (pedido do Luciano, confirmacao
    da generalizacao achado 10/condicao 4): o teste acima so cobria o
    piloto (1 servidor). Em modo campanha com os 3 servidores REAIS da
    campanha oficial (sa-east-1/us-east-1/ap-northeast-1),
    `capture_ready_check()` tem que entregar 'measure' e rodar o probe
    nos 3, nunca so no primeiro/unico."""
    order = []
    inventory = {
        "control": {"public_ip": "203.0.113.10"},
        "servers": {
            "sa-east-1": {"public_ip": "203.0.113.50"},
            "us-east-1": {"public_ip": "203.0.113.51"},
            "ap-northeast-1": {"public_ip": "203.0.113.52"},
        },
        "clients": {"L219": {"public_ip": "203.0.113.70"}},
    }
    executor = orch.SSHExecutor(
        inventory, key_path="/fake/key",
        route_server={"L0-sa-east-1": "sa-east-1", "L219": "sa-east-1",
                      "L0-us-east-1": "us-east-1", "L0-ap-northeast-1": "ap-northeast-1"},
    )

    def fake_deliver_image(self, image_key, host):
        order.append(("deliver", image_key, host))

    def fake_run_capture_preflight(hosts, key_path=None):
        order.append(("probe", tuple(hosts)))
        return {"go": True, "checks": []}

    monkeypatch.setattr(orch.SSHExecutor, "_deliver_image", fake_deliver_image)
    monkeypatch.setattr(orch.preflight, "run_capture_preflight", fake_run_capture_preflight)

    result = executor.capture_ready_check()
    assert result == {"go": True, "checks": []}
    delivered_hosts = {c[2] for c in order if c[0] == "deliver"}
    assert delivered_hosts == {"203.0.113.50", "203.0.113.51", "203.0.113.52"}, order
    probe_call = next(c for c in order if c[0] == "probe")
    assert set(probe_call[1]) == {"203.0.113.50", "203.0.113.51", "203.0.113.52"}, order


def test_mutante_capture_ready_check_campanha_so_1_servidor_e_pego(monkeypatch):
    """Mutante: usa `[self._server_ip()]` (jeito antigo, 1 servidor) em
    vez de `_all_server_ips()` -- confirma que, em modo campanha, isso
    levanta (route=None e invalido) em vez de silenciosamente cobrir
    so 1 dos 3 servidores."""
    inventory = {
        "control": {"public_ip": "203.0.113.10"},
        "servers": {"sa-east-1": {"public_ip": "203.0.113.50"}, "us-east-1": {"public_ip": "203.0.113.51"}},
        "clients": {"L219": {"public_ip": "203.0.113.70"}},
    }
    executor = orch.SSHExecutor(inventory, key_path="/fake/key", route_server={"L219": "sa-east-1"})
    with pytest.raises(KeyError):
        executor._server_ip()  # mutante: route=None por default, nao existe em modo campanha


# --- Decisao 58, achado 18: sondagem TCP pura (preflight_tcp.py real
# da v8), restaurada -- uma vez por rota, DE DENTRO do cliente, ANTES
# de qualquer entrega/execucao cara.

def test_tcp_preflight_roda_do_cliente_antes_de_qualquer_entrega(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    tcp_idx = next(i for i, c in enumerate(flat) if "/dev/tcp/" in c)
    deliver_idx = next(i for i, c in enumerate(flat) if "gateway.tar ec2-user@" in c)
    assert tcp_idx < deliver_idx, flat
    # a chamada tem que ter disparado do CLIENTE (203.0.113.60), nunca
    # do controle/operador -- mesma exigencia literal da v8 real.
    assert any("203.0.113.60" in c and "/dev/tcp/" in c for c in flat), flat
    assert executor.tcp_preflight_results == [
        {"route": "L0", "gateway_ip": "10.0.1.50", "ok": True, "outcome": "OK", "output": "OK"}
    ]


def test_tcp_preflight_aborta_se_timeout_de_verdade(monkeypatch):
    """So TIMEOUT (nenhuma resposta, SG/VPC bloqueando de verdade)
    reprova -- Decisao 65: REFUSED (RST rapido, nada escutando ainda
    na 443) e um resultado ESPERADO antes do gateway subir, nunca um
    sintoma de rede errada."""
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "/dev/tcp/" in remote_cmd:
            return _SimpleProc(stdout="TIMEOUT\n")
        return _SimpleProc(stdout='{"calls": [], "call_count": 0, "retries": []}')

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="nao alcancou"):
        executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert not any("docker save" in c for c in flat), (
        "nenhuma entrega de imagem pode acontecer se a sondagem TCP der timeout de verdade -- " + str(flat)
    )


def test_tcp_preflight_passa_com_connection_refused(monkeypatch):
    """Achado real (execucao real do piloto, Decisao 65): no primeiro
    bloco de qualquer rota o gateway AINDA NAO EXISTE (e o primeiro
    passo de start_block, de proposito) -- a porta 443 responde
    "connection refused" (RST), nunca um timeout. Isso tem que PASSAR
    (prova que o Security Group deixou o pacote passar), nunca
    abortar."""
    calls = []
    base_fake = _fake_run_factory(calls)

    def fake_run(argv, timeout=None):
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "/dev/tcp/" in remote_cmd:
            calls.append(argv)
            return _SimpleProc(stdout="REFUSED\n")
        return base_fake(argv, timeout)

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("classico", "L0")  # nao deveria levantar
    assert executor.tcp_preflight_results[0]["ok"] is True
    assert executor.tcp_preflight_results[0]["outcome"] == "REFUSED"


def test_tcp_preflight_roda_so_uma_vez_por_rota(monkeypatch):
    """Troca de PERFIL (dentro da mesma rota) nunca precisa refazer a
    sondagem TCP -- a rota/SG nao mudam entre perfis."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("classico", "L0")
    executor.start_block("pqc", "L0")
    flat = [" ".join(c) for c in calls]
    assert sum(1 for c in flat if "/dev/tcp/" in c) == 1, flat
    assert len(executor.tcp_preflight_results) == 1


# --- Decisao 58, achado real: `_launch_gateway` montava `/real-certs`
# a partir de `$(pwd)/../../mock-service-os/certs` -- caminho que so
# faz sentido na validacao LOCAL via shim (onde `cwd` e forcado pro
# repositorio real); numa instancia remota de verdade, `$(pwd)` resolve
# pro diretorio de login SSH (`/home/ec2-user`), e nada neste pacote
# jamais entregava nada em `/home/ec2-user/../../mock-service-os/
# certs`. Corrigido pra `~/mock-service-os/certs` (onde
# `deliver_source.py`, novo, entrega de verdade) no caso remoto real;
# o caminho antigo so continua pra `local_shim_bridge_join=True`.

def test_launch_gateway_monta_real_certs_de_home_no_caso_remoto_real(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")  # local_shim_bridge_join=False (default)
    executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    gateway_launches = [c for c in flat if "docker run -d --name v9-mtls" in c]
    assert gateway_launches, flat
    assert all("~/mock-service-os/certs:/real-certs:ro" in c for c in gateway_launches), gateway_launches
    assert all("$(pwd)/../../mock-service-os/certs" not in c for c in gateway_launches), gateway_launches
    # Decisao 83 (pedido do Luciano -- fecha a limitacao que a Decisao
    # 69 tinha registrado): o backend de negocio AGORA roda de
    # verdade no servidor remoto tambem, entao a rede
    # `insurance-server-lambdas_default` passa a existir de verdade
    # la (criada pelo proprio `docker compose up`) -- o gateway entra
    # nela nos DOIS modos agora (pra resolver auth/mockapi por alias
    # Docker), MAS, so no caso remoto real, TAMBEM publica a porta no
    # host (o cliente sempre disca o IP do HOST, nunca um alias).
    assert all("-p 443:443" in c for c in gateway_launches), gateway_launches
    assert all("insurance-server-lambdas_default" in c for c in gateway_launches), gateway_launches
    assert all("--network-alias auth.local" in c for c in gateway_launches), gateway_launches


def test_launch_gateway_mantem_pwd_relativo_so_na_validacao_local_via_shim(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key", local_shim_bridge_join=True)
    executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    gateway_launches = [c for c in flat if "docker run -d --name v9-mtls" in c]
    assert gateway_launches, flat
    assert all("$(pwd)/../../mock-service-os/certs:/real-certs:ro" in c for c in gateway_launches), gateway_launches
    # Decisao 69: a validacao LOCAL ainda precisa da rede/alias (outros
    # containers do stack de compose resolvem "mtls" por ela) -- so o
    # caso remoto real troca pra `-p 443:443` (teste acima).
    assert all("insurance-server-lambdas_default" in c for c in gateway_launches), gateway_launches
    assert all("--network-alias mtls" in c for c in gateway_launches), gateway_launches
    assert all("-p 443:443" not in c for c in gateway_launches), gateway_launches


def test_launch_gateway_aborta_se_docker_run_falha(monkeypatch):
    """Decisao 69 (achado real): sem checar o retorno de `docker run
    -d`, uma rede inexistente (ou qualquer outro erro de `docker run`)
    deixava o container em "Created" (nunca "Up") e so apareceria 2
    passos depois, numa mensagem sem pista da causa raiz. Agora aborta
    na hora, com a saida real do `docker run` na mensagem."""
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "docker run -d --name v9-mtls" in remote_cmd:
            return _SimpleProc(returncode=1, stderr="docker: Error response from daemon: network not found.\n")
        if "/dev/tcp/" in remote_cmd:
            return _SimpleProc(stdout="OK\n")
        return _SimpleProc(stdout='{"calls": [], "call_count": 0, "retries": []}')

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="'docker run -d' falhou"):
        executor._launch_gateway("classico")


def test_launch_gateway_aborta_se_container_nunca_fica_pronto(monkeypatch):
    """Decisao 69 (achado real, ao vivo): `docker run -d` pode retornar
    0 e o container ainda nunca ficar pronto (nunca loga "listening
    on" -- foi exatamente o que aconteceu na Fase A real, por causa da
    rede inexistente, mas poderia ser qualquer outra causa). O laco de
    espera antigo nunca checava isso -- a falha so aparecia 2 passos
    depois em `_verify_running_gateway_binary`, sem pista da causa."""
    calls = []

    def fake_run(argv, timeout=None):
        calls.append(argv)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "listening on" in remote_cmd:
            return _SimpleProc(stdout="")  # nunca encontra "listening on"
        if "docker ps -a" in remote_cmd:
            return _SimpleProc(stdout="Created\n")
        return _SimpleProc(stdout='{"calls": [], "call_count": 0, "retries": []}')

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="nunca logou 'listening on'"):
        executor._launch_gateway("classico")


# --- Decisao 58, item 5 (INFRA_REHEARSAL.md): exercicio remoto de
# start_block/stop_block, sem execucao cronometrada, nunca contado nas
# 60/12 oficiais.

def test_exercise_start_stop_sobe_e_desce_sem_execucao_nem_manifest(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    report = orch.exercise_start_stop(executor, "classico", "L0")
    flat = [" ".join(c) for c in calls]

    assert report["start_block_ok"] is True
    assert report["stop_block_ok"] is True
    assert any("docker run -d --name v9-mtls" in c for c in flat), flat
    assert any("docker stop tls_kem_proxy_run pqc_signer_service_run" in c for c in flat), flat
    assert not any("campaign_client_runner.py" in c for c in flat), (
        "o exercicio NUNCA pode disparar uma execucao real -- " + str(flat)
    )
    # nenhum arquivo de manifesto/execucao e escrito por este exercicio.
    # "fake_home" e so a fixture autouse de images_staging_dir (Decisao
    # 59) -- nunca escrita por exercise_start_stop em si. Nenhum
    # manifest.json/piloto_calls.json/criterio6_execucoes.json (os
    # artefatos reais de um bloco oficial) pode existir.
    written = [p.name for p in tmp_path.glob("*") if p.name != "fake_home"]
    assert not written, "exercise_start_stop nao deveria escrever nada em disco: " + str(written)


def test_exercise_start_stop_tambem_entrega_pqc_signer(monkeypatch):
    """O mesmo achado 19 vale aqui -- o exercicio tem que confirmar a
    entrega das 3 imagens do caminho remoto (mais as 6 do backend,
    Decisao 83), nao so subir o gateway."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    orch.exercise_start_stop(executor, "classico", "L0")
    delivered_keys = {v["image_key"] for v in executor.image_delivery_verifications}
    assert delivered_keys == {"gateway", "proxy", "pqc-signer"} | set(orch.deliver_images.BACKEND_IMAGE_KEYS)
    assert all(v["ok"] for v in executor.image_delivery_verifications)


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


# --- Decisao 83 (pedido do Luciano, apos a Decisao 82): backend de
# negocio da v8 (auth/mongo_seed/mockapi + psql/localstack/mongodb)
# portado pro piloto v9 -- entregue UMA vez por fleet, subido ANTES
# do gateway com health check real, incluido no stop, comparacao de
# CPU/memoria.

def test_deliver_backend_images_entrega_as_6_imagens_uma_vez(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor._deliver_backend_images()
    delivered_keys = {v["image_key"] for v in executor.image_delivery_verifications}
    assert delivered_keys == set(orch.deliver_images.BACKEND_IMAGE_KEYS)
    assert executor._backend_delivered == {executor._server_ip()}


def test_deliver_backend_images_e_idempotente_nunca_reentrega(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor._deliver_backend_images()
    n_calls_1a_vez = len(calls)
    executor._deliver_backend_images()  # 2a chamada -- nunca deveria disparar SSH/scp de novo
    assert len(calls) == n_calls_1a_vez, "a 2a chamada nunca deveria disparar nenhuma chamada nova"


def test_mutante_guarda_de_idempotencia_removida_e_pega(monkeypatch):
    """Mutacao: remove a guarda `if self._backend_delivered: return` --
    o teste de idempotencia acima tem que reprovar com essa mutacao,
    provando que ele depende de fato da guarda."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")

    def mutant_deliver_backend_images(self):
        for key in orch.deliver_images.BACKEND_IMAGE_KEYS:
            self._deliver_image(key, self._server_ip())
        self._backend_delivered = True

    monkeypatch.setattr(orch.SSHExecutor, "_deliver_backend_images", mutant_deliver_backend_images)
    executor._deliver_backend_images()
    n_calls_1a_vez = len(calls)
    executor._deliver_backend_images()
    assert len(calls) > n_calls_1a_vez, "mutante deveria ter reentregue (prova que o teste real dependia da guarda)"


def test_start_block_sobe_o_backend_antes_do_gateway_com_health_check(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    backend_calls = [c for c in flat if "docker compose --profile main up -d --force-recreate auth mongo_seed mockapi" in c]
    assert backend_calls, flat
    assert all("curl -sf http://127.0.0.1:3000/jwks" in c for c in backend_calls), backend_calls
    assert all("Startup completed" in c for c in backend_calls), backend_calls
    assert all("~/insurance-server-lambdas" in c for c in backend_calls), (
        "caminho remoto real tem que ser ~-relativo -- " + str(backend_calls)
    )
    # backend sobe ANTES do gateway.
    backend_idx = next(i for i, c in enumerate(flat) if "docker compose" in c)
    gateway_idx = next(i for i, c in enumerate(flat) if "docker run -d --name v9-mtls" in c)
    assert backend_idx < gateway_idx, flat


def test_start_block_usa_crypto_profile_do_backend_traduzido(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("hibrido-v8", "L0")
    flat = [" ".join(c) for c in calls]
    assert any("CRYPTO_PROFILE=hybrid docker compose" in c for c in flat), flat


def test_start_block_aborta_se_subir_o_backend_falha(monkeypatch):
    def fake_run(argv, timeout=None):
        base = _fake_run_factory(calls)(argv, timeout)
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if "docker compose --profile main up" in remote_cmd:
            return _SimpleProc(returncode=1, stderr="mockapi exited: psql connection refused")
        return base

    calls = []
    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="backend de negocio"):
        executor.start_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    assert not any("docker run -d --name v9-mtls" in c for c in flat), (
        "o gateway nunca pode subir se o backend falhou -- " + str(flat)
    )


def test_stop_block_tambem_para_o_backend_de_negocio(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.stop_block("classico", "L0")
    flat = [" ".join(c) for c in calls]
    stop_calls = [c for c in flat if "docker compose --profile main stop auth mongo_seed mockapi" in c]
    assert stop_calls, flat
    # stop, NUNCA down -- down derrubaria a rede que o gateway usa.
    assert not any(" down " in c or c.endswith(" down") for c in stop_calls), stop_calls


def test_sample_cpu_mem_le_proc_stat_e_meminfo(monkeypatch):
    def fake_run(argv, timeout=None):
        if argv and argv[0] == "ssh" and "/proc/stat" in argv[-1]:
            return _SimpleProc(stdout="cpu  100 0 50 800 0 0 0 0\n---MEMINFO---\nMemTotal:  1000 kB\nMemFree: 200 kB\n")
        return _SimpleProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    sample = executor._sample_cpu_mem("203.0.113.50")
    assert "sampled_at_utc" in sample
    assert sample["proc_stat_line"] == "cpu  100 0 50 800 0 0 0 0"
    assert "MemTotal" in sample["proc_meminfo_raw"]


def test_sample_cpu_mem_nunca_quebra_se_ssh_falha(monkeypatch):
    monkeypatch.setattr(cli, "_run", lambda argv, timeout=None: _SimpleProc(returncode=1, stderr="connection timed out"))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    sample = executor._sample_cpu_mem("203.0.113.50")
    assert "error" in sample
    assert "sampled_at_utc" in sample


def test_start_block_registra_amostras_de_cpu_mem_antes_e_depois_do_backend(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_factory(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    executor.start_block("classico", "L0")
    labels = [s["label"] for s in executor.cpu_mem_samples]
    assert labels == ["antes_do_backend", "depois_do_backend"]


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

    def spying_dedicated_capture(self, profile, route, capturas_dir=None):
        calls_to_dedicated_capture.append((profile, route))
        return real_dedicated_capture(self, profile, route, capturas_dir=capturas_dir)

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

# Decisao 91 (Emenda -- bug de parsing do criterio 1, item b): formato
# novo de 6 colunas (frame, stream, srcport, tcp.len, tipos, tamanhos)
# -- stream "0", srcport "50000" (cliente) / "443" (servidor), tcp.len
# fabricado (nenhum teste estrutural abaixo confere consistencia
# bytes-brutos-vs-gateway, so `test_dedicated_capture_extrai_tamanhos_
# que_o_avaliador_aceita`, que fabrica os DOIS lados coerentes entre
# si explicitamente).
# Emenda robustez-de-captura (pedido do Luciano, item 3): `dedicated_
# capture` agora exige decifragem completa das 6 conexoes mTLS reais
# (`ec.capture_decryption_complete`, N_mTLS=6, Decisao 91) antes de
# aceitar uma tentativa -- o fixture simula as 6, identicas, nunca so
# 1 (que bastava antes desta Emenda, mas reprovaria agora).
_TSHARK_FAKE_OUTPUT = "".join(
    f"{3 * s + 1}\t{s}\t50000\t100\t1\t332\n"
    f"{3 * s + 2}\t{s}\t443\t200\t2,8,13,11,15,20\t183,6,105,6350,3571,32\n"
    f"{3 * s + 3}\t{s}\t50000\t150\t11,15,20\t6352,3571,32\n"
    for s in range(6)
)


def _fake_run_dedicated_capture(calls, iface="eth0", tcpdump_pid="12345", tshark_output=_TSHARK_FAKE_OUTPUT,
                                 gateway_log_output=""):
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
        if "/dev/tcp/" in remote_cmd:
            proc.stdout = "OK\n"
        elif "ip -o -4 route show to default" in remote_cmd:
            proc.stdout = f"{iface}\n"
        elif "nohup tcpdump" in remote_cmd:
            proc.stdout = f"{tcpdump_pid}\n"
        elif "campaign_client_runner.py" in remote_cmd:
            proc.stdout = '{"calls": [], "call_count": 0, "retries": []}'
        elif "docker logs -t --since" in remote_cmd:
            # Decisao 91, item (d): janela de log do gateway (handshake
            # BytesIn/Out REAIS) -- buscada em volta do disparo da
            # execucao de captura, nunca confundida com a checagem de
            # "listening on" (string distinta, ver abaixo).
            proc.stdout = gateway_log_output
        elif "tls.handshake.type" in remote_cmd:
            proc.stdout = tshark_output
        elif "sha256sum -c" in remote_cmd:
            proc.stdout = "gateway: OK\n"
        elif "listening on" in remote_cmd:
            proc.stdout = "FOUND\n"
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
    cabecalho" do avaliador se encaixam sem ajuste nenhum aqui.

    Decisao 91 (item d): o fake tambem fornece tcp.len/handshakeBytesIn/
    Out COERENTES entre si (100+150=250 bytes do cliente, 200 bytes do
    servidor) -- sem isso a verificacao de consistencia obrigatoria
    reprovaria por FALTA de evidencia, nunca por escolha."""
    hb = ec.HANDSHAKE_MESSAGE_BASELINE["hibrido-v8"]
    ch = ec.CLIENTHELLO_BASELINE["hibrido-v8"] - 4
    cert = ec.CERTIFICATE_BASELINE["hibrido-v8"] - 4
    # Emenda robustez-de-captura (pedido do Luciano, item 3): 6 streams
    # IDENTICOS (N_mTLS=6, Decisao 91) -- `ec.capture_decryption_
    # complete` agora exige as 6, nunca so 1, antes de aceitar a
    # tentativa como final.
    tshark_output = "".join(
        f"{3*s+1}\t{s}\t50000\t100\t1\t{ch}\n"
        f"{3*s+2}\t{s}\t443\t200\t2,8,13,11,15,20\t"
        f"{hb['ServerHello']-4},{hb['EncryptedExtensions']-4},{hb['CertificateRequest']-4},"
        f"{cert},{hb['CertificateVerify_servidor']-4},{hb['Finished_servidor']-4}\n"
        f"{3*s+3}\t{s}\t50000\t150\t11,15,20\t{hb['Certificate_cliente']-4},{hb['CertificateVerify_cliente']-4},{hb['Finished_cliente']-4}\n"
        for s in range(6)
    )
    gateway_log_output = "".join(
        'gateway: hibrido-v8 connection OK remoteAddr=10.0.0.9:50000 sni="mtls" '
        'curve=SecP384r1MLKEM1024 dualAuthenticated=false clientCert="hibrido_v8_client" '
        "handshakeBytesIn=250 handshakeBytesOut=200\n"
        for _ in range(6)
    )
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(
        calls, tshark_output=tshark_output, gateway_log_output=gateway_log_output))
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
    def mutant_launch_gateway(self, profile, keylog=False, route=None):
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


# --- Emenda robustez-de-captura (pedido do Luciano, item 3, apos a
# Decisao 95 achar que L0 so decifra ClientHello/ServerHello nos 4
# perfis): `dedicated_capture` reteNta (ate MAX_CAPTURE_ATTEMPTS) so
# quando o MODO DE FALHA for decifragem incompleta -- nunca por
# divergencia de tamanho.

def _tshark_output_n_streams(n):
    return "".join(
        f"{3*s+1}\t{s}\t50000\t100\t1\t332\n"
        f"{3*s+2}\t{s}\t443\t200\t2,8,13,11,15,20\t183,6,105,6350,3571,32\n"
        f"{3*s+3}\t{s}\t50000\t150\t11,15,20\t6352,3571,32\n"
        for s in range(n)
    )


def _fake_run_dedicated_capture_variavel(calls, tshark_outputs):
    """Como `_fake_run_dedicated_capture`, mas a saida do tshark varia
    por CHAMADA (uma por tentativa) -- `tshark_outputs[i]` pra a
    (i+1)-esima chamada; a ultima entrada se repete se faltar."""
    state = {"tshark_calls": 0}

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
        if "/dev/tcp/" in remote_cmd:
            proc.stdout = "OK\n"
        elif "ip -o -4 route show to default" in remote_cmd:
            proc.stdout = "eth0\n"
        elif "nohup tcpdump" in remote_cmd:
            proc.stdout = "12345\n"
        elif "campaign_client_runner.py" in remote_cmd:
            proc.stdout = '{"calls": [], "call_count": 0, "retries": []}'
        elif "docker logs -t --since" in remote_cmd:
            proc.stdout = ""
        elif "tls.handshake.type" in remote_cmd:
            idx = min(state["tshark_calls"], len(tshark_outputs) - 1)
            proc.stdout = tshark_outputs[idx]
            state["tshark_calls"] += 1
        elif "sha256sum -c" in remote_cmd:
            proc.stdout = "gateway: OK\n"
        elif "listening on" in remote_cmd:
            proc.stdout = "FOUND\n"
        elif "sha256sum /gateway" in remote_cmd:
            proc.stdout = f"{_FAKE_GATEWAY_SHA256}  /gateway\n"
        else:
            image_id_stdout = _fake_image_id_for_remote_cmd(remote_cmd)
            if image_id_stdout is not None:
                proc.stdout = image_id_stdout
        return proc
    return fake_run, state


def test_dedicated_capture_retenta_quando_decifragem_incompleta_na_1a_tentativa(monkeypatch):
    """1a tentativa: so 1 dos 6 streams decifrou (sintoma real da
    Decisao 95 em L0) -- tem que retentar, nunca aceitar como final.
    2a tentativa: as 6 decifram -- aceita, para de retentar."""
    calls = []
    fake_run, state = _fake_run_dedicated_capture_variavel(
        calls, [_tshark_output_n_streams(1), _tshark_output_n_streams(6)])
    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli, "run_scp", lambda *a, **k: _SimpleProc())
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    block = executor.dedicated_capture("classico", "L0")
    assert state["tshark_calls"] == 2, "tinha que ter tentado de novo exatamente 1 vez (2 tentativas no total)"
    row = ec._message_sizes_for_profile(block, "classico")
    assert row["n_streams"] == 6


def test_dedicated_capture_falha_apos_max_tentativas_com_decifragem_sempre_incompleta(monkeypatch):
    calls = []
    fake_run, state = _fake_run_dedicated_capture_variavel(calls, [_tshark_output_n_streams(1)])
    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli, "run_scp", lambda *a, **k: _SimpleProc())
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    with pytest.raises(RuntimeError, match="decifragem incompleta"):
        executor.dedicated_capture("classico", "L0")
    assert state["tshark_calls"] == executor.MAX_CAPTURE_ATTEMPTS


def test_dedicated_capture_preserva_pcap_keylog_de_toda_tentativa_incluindo_falhas(monkeypatch, tmp_path):
    """Pedido do Luciano (item 0+3): TODA tentativa (sucesso ou falha)
    tem pcap+keylog preservados no `capturas_dir` local -- nunca so a
    vencedora, nunca descartados silenciosamente."""
    calls = []
    fake_run, state = _fake_run_dedicated_capture_variavel(
        calls, [_tshark_output_n_streams(1), _tshark_output_n_streams(1), _tshark_output_n_streams(6)])
    monkeypatch.setattr(cli, "_run", fake_run)

    scp_pairs = []

    def fake_run_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        scp_pairs.append((src, dst))
        if "@" not in dst:  # so escreve quando dst e um caminho LOCAL (pull remoto->local)
            Path(dst).write_text("conteudo-fake", encoding="utf-8")
        return _SimpleProc()

    monkeypatch.setattr(cli, "run_scp", fake_run_scp)
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    capturas_dir = tmp_path / "criterio1_capturas"
    capturas_dir.mkdir()
    executor.dedicated_capture("classico", "L0", capturas_dir=capturas_dir)

    retries_dir = capturas_dir / "capturas_brutas"
    for attempt in (1, 2, 3):
        assert (retries_dir / f"classico_L0_tentativa{attempt}.pcap").is_file(), list(retries_dir.iterdir())
        assert (retries_dir / f"classico_L0_tentativa{attempt}.keylog").is_file()
    # a vencedora (tentativa 3) tambem ganha o nome SEM sufixo.
    assert (capturas_dir / "classico_L0.pcap").is_file()
    assert (capturas_dir / "classico_L0.keylog").is_file()


def test_mutante_dedicated_capture_sem_checar_decifragem_aceitaria_captura_parcial():
    """Mutante = o comportamento ANTIGO (antes desta Emenda): aceita a
    1a tentativa so porque `n_handshake_rows > 0`, sem nunca checar
    `ec.capture_decryption_complete` -- com 1 de 6 streams decifrados
    (sintoma real da Decisao 95), o mutante aceitaria incorretamente
    onde o codigo real exige retry."""
    lines_1_de_6 = [l for l in _tshark_output_n_streams(1).splitlines() if l]
    n_handshake_rows_mutante = sum(1 for l in lines_1_de_6 if len(l.split("\t")) >= 6 and l.split("\t")[4] and l.split("\t")[5])
    mutant_aceita = n_handshake_rows_mutante > 0  # mutante: nunca confere completude
    assert mutant_aceita is True  # aceitaria errado

    real = ec.capture_decryption_complete(lines_1_de_6)
    assert real["complete"] is False  # o codigo real rejeita a MESMA captura


# --- Achado 10 (implementado, pedido do Luciano, generalizacao pra N
# servidores): sampler periodico real de CPU/steal, porta fiel do
# mecanismo da v8 (_cpu_mem_sampler_start_cmd/_steal_pct_from_cpu_
# jsonl de campaign_run.py), SO em modo campanha -- nunca no piloto.

def test_steal_pct_from_cpu_jsonl_formula_real(tmp_path):
    """Dados reais no formato que o sampler escreve -- 3 campos de
    /proc/stat (user/nice/system/idle/iowait/irq/softirq/steal),
    delta cumulativo entre a 1a e a ULTIMA linha, nunca uma razao
    desde o boot."""
    jsonl_path = tmp_path / "test.cpu_mem.jsonl"
    lines = [
        json.dumps({"sampled_at_utc": "t0", "proc_stat_line": "cpu 100 0 50 1000 0 0 0 10", "proc_meminfo_raw": ""}),
        json.dumps({"sampled_at_utc": "t1", "proc_stat_line": "cpu 150 0 70 1100 0 0 0 30", "proc_meminfo_raw": ""}),
        json.dumps({"sampled_at_utc": "t2", "proc_stat_line": "cpu 200 0 90 1200 0 0 0 60", "proc_meminfo_raw": ""}),
    ]
    jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 1a linha: total=100+0+50+1000+0+0+0+10=1160, steal=10
    # ultima linha: total=200+0+90+1200+0+0+0+60=1550, steal=60
    # dtotal=1550-1160=390, dsteal=60-10=50 -> 100*50/390 = 12.8205...%
    result = orch._steal_pct_from_cpu_jsonl(jsonl_path)
    assert result == pytest.approx(100 * 50 / 390)


def test_steal_pct_from_cpu_jsonl_menos_de_2_linhas_e_none(tmp_path):
    jsonl_path = tmp_path / "test.cpu_mem.jsonl"
    jsonl_path.write_text(json.dumps({"proc_stat_line": "cpu 1 1 1 1 1 1 1 1"}) + "\n", encoding="utf-8")
    assert orch._steal_pct_from_cpu_jsonl(jsonl_path) is None


def test_steal_pct_from_cpu_jsonl_arquivo_ausente_e_none(tmp_path):
    assert orch._steal_pct_from_cpu_jsonl(tmp_path / "nao-existe.jsonl") is None


def test_mutante_steal_pct_razao_desde_o_boot_e_pego(tmp_path):
    """Mutante: usa a ULTIMA linha sozinha (razao desde o boot) em vez
    do delta entre 1a e ultima -- confirma que o teste real acima
    depende de fato do delta, nunca aceitaria o mutante por acidente."""
    jsonl_path = tmp_path / "test.cpu_mem.jsonl"
    lines = [
        json.dumps({"proc_stat_line": "cpu 100 0 50 1000 0 0 0 10"}),
        json.dumps({"proc_stat_line": "cpu 150 0 70 1100 0 0 0 30"}),
        json.dumps({"proc_stat_line": "cpu 200 0 90 1200 0 0 0 60"}),
    ]
    jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    last = json.loads(lines[-1])
    fields = [int(x) for x in last["proc_stat_line"].split()[1:11]]
    mutant_result = 100 * fields[7] / sum(fields)  # razao desde o boot, nunca delta
    real_result = orch._steal_pct_from_cpu_jsonl(jsonl_path)
    assert mutant_result != real_result


def test_sampler_de_steal_nunca_roda_no_piloto(monkeypatch):
    """Gate explicito (compatibilidade, item 1): route_server=None
    (piloto) -- start_block/stop_block NUNCA chamam o sampler, zero
    chamada SSH nova, cpu_steal_samples fica vazio sempre."""
    calls = []
    monkeypatch.setattr(cli, "_run", _fake_run_dedicated_capture(calls))
    executor = orch.SSHExecutor(_inventory_l0(), key_path="/fake/key")
    assert executor.route_server is None
    executor.start_block("classico", "L0")
    executor.stop_block("classico", "L0")
    assert executor.cpu_steal_samples == []
    assert executor._cpu_steal_sampler_paths == {}
    flat = [" ".join(c) for c in calls]
    assert not any("cpu_mem.jsonl" in c or "cpu_mem.pid" in c for c in flat), (
        "o piloto nunca pode ganhar chamadas novas do sampler de steal -- achado de compatibilidade"
    )


def test_sampler_de_steal_roda_em_modo_campanha(monkeypatch):
    """Modo campanha (route_server setado): start_block dispara o
    sampler no SERVIDOR E NO CLIENTE (paridade com a v8 real,
    campaign_run.py, que sempre amostrou os 2 lados -- achado
    confirmado nesta rodada antes de implementar, nunca suposto),
    stop_block para e traz o resultado dos 2 -- cpu_steal_samples
    ganha 2 entradas reais por bloco (server + client)."""
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
        tcp_pre = _fake_tcp_preflight_call(remote_cmd)
        if tcp_pre is not None:
            return tcp_pre
        if "jwks" in remote_cmd or "Startup completed" in remote_cmd:
            return _SimpleProc(stdout="")
        if "sha256sum -c" in remote_cmd:
            return _SimpleProc(stdout="gateway: OK\n")
        if "listening on" in remote_cmd:
            return _SimpleProc(stdout="FOUND\n")
        if "sha256sum /gateway" in remote_cmd:
            return _SimpleProc(stdout=f"{_FAKE_GATEWAY_SHA256}  /gateway\n")
        image_id_stdout = _fake_image_id_for_remote_cmd(remote_cmd)
        if image_id_stdout is not None:
            return _SimpleProc(stdout=image_id_stdout)
        return _SimpleProc()

    def fake_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        if "cpu_mem.jsonl" in src:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_text(
                json.dumps({"proc_stat_line": "cpu 100 0 50 1000 0 0 0 10"}) + "\n" +
                json.dumps({"proc_stat_line": "cpu 200 0 90 1200 0 0 0 60"}) + "\n",
                encoding="utf-8",
            )
        return _SimpleProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli, "run_scp", fake_scp)
    inventory = {
        "control": {"public_ip": "203.0.113.10", "private_ip": "10.0.0.10"},
        "servers": {"sa-east-1": {"public_ip": "203.0.113.50", "private_ip": "10.0.0.50"}},
        "clients": {"L219": {"public_ip": "203.0.113.70", "private_ip": "10.0.2.70", "colocated": False}},
    }
    executor = orch.SSHExecutor(inventory, key_path="/fake/key", route_server={"L219": "sa-east-1"})
    executor.start_block("classico", "L219")
    assert ("classico", "L219") in executor._cpu_steal_sampler_paths
    assert set(executor._cpu_steal_sampler_paths[("classico", "L219")].keys()) == {"server", "client"}
    executor.stop_block("classico", "L219")
    assert executor._cpu_steal_sampler_paths == {}
    assert len(executor.cpu_steal_samples) == 2
    by_role = {s["host_role"]: s for s in executor.cpu_steal_samples}
    assert set(by_role.keys()) == {"server", "client"}
    assert by_role["server"]["profile"] == "classico" and by_role["server"]["route"] == "L219"
    assert by_role["server"]["host"] == "203.0.113.50"
    assert by_role["client"]["host"] == "203.0.113.70"
    assert by_role["server"]["steal_pct"] == pytest.approx(100 * 50 / 390)
    assert by_role["client"]["steal_pct"] == pytest.approx(100 * 50 / 390)


def test_mutante_sampler_de_steal_so_servidor_nunca_cliente_e_pego(monkeypatch):
    """Mutante: reproduz o comportamento ANTIGO (so o servidor,
    paridade incompleta com a v8 real) -- confirma que o teste acima
    reprovaria essa regressao."""
    inventory = {
        "servers": {"sa-east-1": {"public_ip": "203.0.113.50"}},
        "clients": {"L219": {"public_ip": "203.0.113.70"}},
    }
    executor = orch.SSHExecutor(inventory, key_path="/fake/key", route_server={"L219": "sa-east-1"})
    mutant_sides = {"server": ("203.0.113.50", "x.jsonl", "x.pid")}  # mutante: sem "client"
    assert "client" not in mutant_sides, "mutante nunca amostra o cliente -- exatamente a lacuna fechada agora"


def test_sampler_de_steal_cobre_servidores_distintos_em_rotas_diferentes(monkeypatch):
    """Lacuna encontrada e fechada agora (pedido do Luciano, confirmacao
    da generalizacao achado 10/condicao 4): o teste acima so exercitava
    1 servidor (sa-east-1). Com 2 rotas mapeadas pra 2 servidores REAIS
    distintos da campanha oficial (sa-east-1/us-east-1) no MESMO
    executor, o sampler tem que amostrar o HOST CERTO de cada bloco,
    nunca sempre o mesmo servidor por acidente de closure/estado
    compartilhado."""
    hosts_sampled = []

    def fake_run(argv, timeout=None):
        local_docker = _fake_local_docker_gateway_binary_call(argv)
        if local_docker is not None:
            return local_docker
        sh_save_load = _fake_sh_docker_save_load_call(argv)
        if sh_save_load is not None:
            return sh_save_load
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if argv and argv[0] == "ssh" and ("cpu_mem.jsonl" in remote_cmd or "cpu_mem.pid" in remote_cmd):
            hosts_sampled.append(argv[-2] if len(argv) >= 2 else None)
        tcp_pre = _fake_tcp_preflight_call(remote_cmd)
        if tcp_pre is not None:
            return tcp_pre
        if "jwks" in remote_cmd or "Startup completed" in remote_cmd:
            return _SimpleProc(stdout="")
        if "sha256sum -c" in remote_cmd:
            return _SimpleProc(stdout="gateway: OK\n")
        if "listening on" in remote_cmd:
            return _SimpleProc(stdout="FOUND\n")
        if "sha256sum /gateway" in remote_cmd:
            return _SimpleProc(stdout=f"{_FAKE_GATEWAY_SHA256}  /gateway\n")
        image_id_stdout = _fake_image_id_for_remote_cmd(remote_cmd)
        if image_id_stdout is not None:
            return _SimpleProc(stdout=image_id_stdout)
        return _SimpleProc()

    def fake_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        if "cpu_mem.jsonl" in src:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_text(
                json.dumps({"proc_stat_line": "cpu 100 0 50 1000 0 0 0 10"}) + "\n" +
                json.dumps({"proc_stat_line": "cpu 200 0 90 1200 0 0 0 60"}) + "\n",
                encoding="utf-8",
            )
        return _SimpleProc()

    monkeypatch.setattr(cli, "_run", fake_run)
    monkeypatch.setattr(cli, "run_scp", fake_scp)
    inventory = {
        "control": {"public_ip": "203.0.113.10", "private_ip": "10.0.0.10"},
        "servers": {
            "sa-east-1": {"public_ip": "203.0.113.50", "private_ip": "10.0.0.50"},
            "us-east-1": {"public_ip": "203.0.113.51", "private_ip": "10.0.0.51"},
        },
        "clients": {
            "L219": {"public_ip": "203.0.113.70", "private_ip": "10.0.2.70", "colocated": False},
            "L14": {"public_ip": "203.0.113.71", "private_ip": "10.0.2.71", "colocated": False},
        },
    }
    executor = orch.SSHExecutor(
        inventory, key_path="/fake/key",
        route_server={"L219": "sa-east-1", "L14": "us-east-1"},
    )
    executor.start_block("classico", "L219")
    executor.stop_block("classico", "L219")
    executor.start_block("classico", "L14")
    executor.stop_block("classico", "L14")

    assert len(executor.cpu_steal_samples) == 4  # 2 rotas x (server+client)
    l219_server = next(s for s in executor.cpu_steal_samples if s["route"] == "L219" and s["host_role"] == "server")
    l219_client = next(s for s in executor.cpu_steal_samples if s["route"] == "L219" and s["host_role"] == "client")
    l14_server = next(s for s in executor.cpu_steal_samples if s["route"] == "L14" and s["host_role"] == "server")
    l14_client = next(s for s in executor.cpu_steal_samples if s["route"] == "L14" and s["host_role"] == "client")
    assert l219_server["host"] == "203.0.113.50" and l219_client["host"] == "203.0.113.70"
    assert l14_server["host"] == "203.0.113.51" and l14_client["host"] == "203.0.113.71"
    # a amostragem SSH real tem que ter alcancado os 4 hosts distintos (2 servidores + 2 clientes).
    for ip in ("203.0.113.50", "203.0.113.70", "203.0.113.51", "203.0.113.71"):
        assert any(ip in (h or "") for h in hosts_sampled), (ip, hosts_sampled)

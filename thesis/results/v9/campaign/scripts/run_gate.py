#!/usr/bin/env python3
"""Decisao 165 (pedido do Luciano, item 2 -- "a ultima tentativa de
fechar a matriz"): o lancador PADRAO local dos 4 perfis -- "o mesmo
caminho que a campanha e o piloto usam" (orchestrator.SSHExecutor,
local_shim_bridge_join=True, Decisao 49), nunca um script paralelo
que reinventa subir container/trocar perfil.

Pra cada perfil (orch.PROFILES -- classico/pqc/hibrido-v8/hibrido-and):
  1. sobe o backend (docker compose, auth/mongo_seed/mockapi) e o
     gateway v9 pelo MESMO `SSHExecutor.start_block()` que a campanha
     oficial usa. A verificacao de TRANSITO (scp + sha256sum -c do
     binario/imagens -- `_verify_gateway_binary`/`_verify_running_
     gateway_binary`/`_deliver_image`) e pulada nesta instancia,
     mesmo precedente que `start_block` JA aplica a `_deliver_backend_
     images` sob `local_shim_bridge_join=True` (linha "if not self.
     local_shim_bridge_join: self._deliver_backend_images(route)"):
     essas verificacoes existem pra provar que um binario/imagem
     sobreviveu o SALTO controle->host remoto sem corrupcao/adulteracao
     -- em validacao local pura nao ha salto nenhum (a imagem Docker
     JA esta nesta mesma maquina), e o unico jeito de faze-las passar
     de verdade seria contra PINS.json, que fixa os hashes das imagens
     OFICIAIS da campanha remota (muda so por Emenda numerada em
     DECISIONS.md -- fora do escopo deste script, que e so pra
     validacao local). Pulado aqui do mesmo jeito -- nunca verificado
     com um pin desatualizado/errado, e nunca alterando PINS.json pra
     forcar a passagem.
  2. confere a pre-condicao do item 1 (thesis/scripts/tests/
     conftest.assert_stack_profile_matches) -- FALHA (nunca pula) se
     o perfil vivo nao bater.
  3. roda `pytest thesis/scripts/tests/` com CRYPTO_PROFILE=<perfil
     opin_flow> e V9_HARNESS=1 (os testes aplicaveis a cada perfil se
     auto-selecionam pelos seus proprios skips -- este script nunca
     escolhe arquivo por perfil).
  4. relanca proxy/signer (pytest os para no finally de cada modulo;
     reusa `opin_flow.start_tls_kem_proxy`/`start_pqc_signer_service`
     direto, as MESMAS funcoes que start_block/pytest ja usam) e roda
     UMA execucao completa pelo caminho do harness real (relay.go,
     via `SSHExecutor.run_execution` -> `campaign_client_runner.py`)
     -- confere 44 chamadas HTTP e 6 handshakes cliente-gateway
     (`orchestrator._assert_call_and_handshake_counts`, nunca
     reimplementado aqui) e o perfil/curva negociados
     (`orchestrator._assert_profile_negotiated`).
  5. derruba TUDO antes do proximo perfil: `docker compose down` (sem
     -v, sem --rmi, sem prune -- pedido explicito do item 2, uma
     divergencia deliberada de `stop_block`, que so faz `stop` pra
     preservar a rede entre blocos de uma CAMPANHA; este script nao e
     uma campanha, cada perfil comeca de uma folha limpa) + `docker
     rm -f` do container do gateway (nunca gerenciado pelo compose).

Saida: matriz JSON (thesis/results/v9/campaign/run_gate_results/) +
tabela no stdout. `--preflight-only` pula o pytest (so sobe/verifica/
roda a execucao/derruba) -- o mesmo subconjunto que serve de pre-voo
do piloto real (achado de infra antes de gastar uma janela inteira).

Invoque como:
  python run_gate.py                       # os 4 perfis, gate completo
  python run_gate.py --profiles classico    # so 1 perfil
  python run_gate.py --preflight-only       # pre-voo, sem pytest
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import cli  # noqa: E402
import orchestrator as orch  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[5]
THESIS_SCRIPTS_DIR = REPO_ROOT / "thesis" / "scripts"
TESTS_DIR = THESIS_SCRIPTS_DIR / "tests"
COMPOSE_DIR = REPO_ROOT / "insurance-server-lambdas"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "run_gate_results"

ROUTE = "L0"
_LEGACY_MTLS_CONTAINER = "insurance-server-lambdas-mtls-1"


def _inventory() -> dict:
    return {
        "server": {"public_ip": "127.0.0.1", "private_ip": "127.0.0.1"},
        "clients": {ROUTE: {"public_ip": "127.0.0.1", "private_ip": "127.0.0.1", "colocated": True}},
    }


def _skip_transit_verification(executor: "orch.SSHExecutor") -> None:
    """Pula so a verificacao de TRANSITO (scp + sha256sum -c) de
    gateway/proxy/pqc-signer -- ver docstring do modulo. `_launch_
    gateway` (quem de fato sobe o container) nunca e tocado -- so os 3
    metodos que verificam que um ARQUIVO sobreviveu um salto de rede
    que, em validacao local pura, nunca acontece."""
    executor._verify_gateway_binary = lambda profile, route: None
    executor._verify_running_gateway_binary = lambda verification: None
    executor._deliver_image = lambda image_key, host: None


def stop_legacy_mtls_alias_collision() -> None:
    """Achado real, ao vivo, nesta validacao: o servico LEGADO
    `mtls` (insurance-server-lambdas/docker-compose.yml, mock_mtls) e
    automaticamente aliasado pelo proprio compose ao seu nome de
    servico, "mtls" -- o MESMO alias que `_launch_gateway` registra
    pro gateway v9 real (`--network-alias mtls`). Se o `mtls` legado
    ja estiver de pe na rede compartilhada (leftover de uma sessao
    anterior -- NUNCA sobe de novo sozinho: nao e dependencia de
    auth/mongo_seed/mockapi, e o comando de `start_block` nunca o
    nomeia), o DNS embutido do Docker passa a alternar entre os dois
    containers pra resolucoes de "mtls" -- confirmado ao vivo:
    handshake ia e voltava entre OK e "x509: certificate is valid for
    auth.local,... not mtls" (o cert do mock_mtls legado, que nunca
    teve "mtls" no SAN) na mesma sequencia de chamadas. Corrigido
    aqui, uma vez por execucao do gate (nunca por perfil -- apos o
    primeiro `docker compose down` de cada iteracao o servico nem
    existe mais) -- nunca dentro de uma fixture de teste (item 1: a
    responsabilidade de um stack limpo e do LANCADOR, nunca do
    teste)."""
    cli.run_ssh("127.0.0.1", f"docker rm -f {_LEGACY_MTLS_CONTAINER} 2>/dev/null; true", key_path=None)


def _make_executor(images_staging_dir: Path) -> "orch.SSHExecutor":
    executor = orch.SSHExecutor(
        _inventory(), key_path=None, local_shim_bridge_join=True,
        images_staging_dir=images_staging_dir, route_server=None,
    )
    _skip_transit_verification(executor)
    return executor


# Decisao 169 (pedido do Luciano, item 4 -- "confirme... que o
# docker compose e o run_gate.py sobem com as imagens ja carregadas,
# sem reconstruir, falhando se o compose tentasse construir"):
# `docker compose up` (chamado por `start_block`) so builda uma
# imagem com `build:` no compose (auth/mongo_seed) se ela NAO
# existir ainda, ou se `--build` for passado -- `start_block` nunca
# passa `--build` (confirmado lendo orchestrator.py), entao o risco
# real NUNCA e o compose builder sozinho; e um `docker build`/
# `./gradlew optimizedDockerBuild` rodado por FORA deste script (por
# um auditor, por exemplo -- achado real NESTA MESMA rodada: um
# rebuild assim sobrescreveu `raidiam-insurance-lambdas:latest` ate
# ser corrigido com `docker tag` de volta). A checagem abaixo
# detecta exatamente isso: snapshot do Image Id de cada imagem
# ANTES do gate inteiro, reconfirmado IDENTICO depois -- falha alto
# se mudou, e falha alto tambem se a imagem simplesmente nao existe
# (nunca deixa o compose criar uma nova silenciosamente).
#
# `tar_sha256` do PINS.json NAO e reusado aqui como criterio, de
# proposito: e o mesmo campo que a Decisao 68 ja desqualificou como
# identidade de CONTEUDO (so serve pra integridade de TRANSITO,
# operador->host remoto) por causa da camada de certs efemera; e,
# pra auth/mongo_seed/mockapi especificamente, o proprio PINS.json
# atual reflete o estado PRE-normalizacao de LF (Decisao 166-169) --
# comparar contra ele aqui reprovaria toda imagem carregada hoje,
# mesmo as que a Decisao 169 ja provou equivalentes modulo fim de
# linha/chave efemera. Pra `gateway`/`proxy` (que TEM binario Go
# proprio, nao sujeito a CRLF), `binary_sha256` do PINS.json AINDA e
# o criterio de conteudo -- continua comparado abaixo.
_REQUIRED_LOCAL_IMAGES = {
    "gateway": "mockopin-v9-gateway:latest",
    "proxy": "mockopin-v9-proxy:latest",
    "measure": "mockopin-v9-measure:latest",
    "pqc-signer": "mockopin-pqc-signer:latest",
    "auth": "insurance-server-lambdas-auth:latest",
    "mongo_seed": "insurance-server-lambdas-mongo_seed:latest",
    "mockapi": "raidiam-insurance-lambdas:latest",
}


def _docker_image_id(docker_image: str) -> str | None:
    proc = cli.run_ssh("127.0.0.1", f"docker image inspect {docker_image} --format '{{{{.Id}}}}'", key_path=None)
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None


def snapshot_local_images() -> dict:
    """Falha alto (nunca deixa passar silenciosamente) se alguma das
    7 imagens que o stack local usa nao existir -- esse e o caso em
    que `docker compose up`/`_launch_gateway` tentariam criar uma do
    zero; preferimos abortar aqui, ANTES do gate, a deixar o compose
    builder rodar sem supervisao."""
    snapshot = {}
    missing = []
    for image_key, docker_image in _REQUIRED_LOCAL_IMAGES.items():
        image_id = _docker_image_id(docker_image)
        if image_id is None:
            missing.append(docker_image)
        snapshot[image_key] = {"docker_image": docker_image, "image_id": image_id}
    if missing:
        raise RuntimeError(
            f"snapshot_local_images: {missing} nao estao carregadas localmente -- "
            f"rode make/docker build manualmente primeiro; este gate NUNCA builda imagem nenhuma"
        )

    pins = orch.load_pins()
    for image_key in ("gateway", "proxy"):
        image_pins = pins["images"][image_key]
        binary_path = image_pins["binary_path_in_image"]
        expected_sha256 = image_pins["binary_sha256"]
        docker_image = _REQUIRED_LOCAL_IMAGES[image_key]
        bin_proc = cli.run_ssh(
            "127.0.0.1", f"docker run --rm --entrypoint sha256sum {docker_image} {binary_path}", key_path=None,
        )
        actual_sha256 = bin_proc.stdout.split()[0] if bin_proc.returncode == 0 and bin_proc.stdout.strip() else None
        snapshot[image_key]["binary_sha256_expected"] = expected_sha256
        snapshot[image_key]["binary_sha256_actual"] = actual_sha256
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"snapshot_local_images: binary_sha256 de {image_key} carregado localmente "
                f"({actual_sha256!r}) NAO bate com PINS.json ({expected_sha256!r})"
            )
    return snapshot


def assert_local_images_unchanged(before: dict, after: dict) -> None:
    changed = {
        image_key: {"before": before[image_key]["image_id"], "after": after[image_key]["image_id"]}
        for image_key in _REQUIRED_LOCAL_IMAGES
        if before[image_key]["image_id"] != after[image_key]["image_id"]
    }
    if changed:
        raise RuntimeError(
            f"assert_local_images_unchanged: {changed} -- alguma imagem foi reconstruida/sobrescrita "
            f"DURANTE o gate (nunca deveria, nem por compose nem por nada mais rodando nesta maquina)"
        )


# Decisao 166 (pedido do Luciano, diagnostico de classico/pqc
# travando em start_block com "open /certs/<profile>_client.crt: no
# such file or directory" apesar do arquivo existir no host com mtime
# correto): lista exata dos arquivos que o PROPRIO
# thesis/results/v9/integration/proxy/main.go's `buildClientTLSConfig`
# le de V9_CERTS_DIR pra cada perfil (lida do codigo-fonte, nunca
# adivinhada) -- usada SO pelo diagnostico abaixo, nunca pelo proxy em
# si (que continua resolvendo seus proprios caminhos, sem alteracao).
_REQUIRED_CERT_FILES = {
    "classico": ["classico_client.crt", "classico_client.key", "classico_ca.crt"],
    "pqc": ["pqc_client.crt", "pqc_client.key", "pqc_ca.crt"],
    "hibrido-v8": ["hibrido_v8_client.crt", "hibrido_v8_client.key", "hibrido_v8_ca.crt"],
    "hibrido-and": [
        "hibrido_and_rsa_client.crt", "hibrido_and_rsa_client.key", "hibrido_and_rsa_ca.crt",
        "hibrido_and_mldsa_client.crt", "hibrido_and_mldsa_client.key", "hibrido_and_mldsa_ca.crt",
    ],
}
_DIAG_IMAGE = "alpine:3"


def wait_for_cert_mount_visible(gateway_profile: str, timeout_seconds: int = 30) -> dict:
    """Item 1(b) desta rodada de diagnostico: ANTES de `start_block`
    (que e quem de fato lanca o proxy real, nunca tocado aqui), sobe
    um container DESCARTAVEL com o MESMO bind mount (`V9_CERTS_DIR:
    /certs:ro`) que `opin_flow.start_tls_kem_proxy(detached=True)` vai
    usar, e roda `test -f` pra cada arquivo exigido por este perfil
    (`_REQUIRED_CERT_FILES`), repetindo por ate `timeout_seconds`.
    Isto e SO diagnostico -- nunca bloqueia nem adia o `start_block`
    real (que roda do mesmo jeito depois, com ou sem sucesso aqui);
    so registra quanto tempo o mount levou pra ficar visivel por FORA
    do proxy, pra separar "o mount genuinamente nao propagou a tempo"
    de outra causa."""
    sys.path.insert(0, str(THESIS_SCRIPTS_DIR))
    import opin_flow as of
    certs_dir = of.V9_CERTS_DIR
    required = _REQUIRED_CERT_FILES[gateway_profile]
    test_expr = " && ".join(f"test -f /certs/{name}" for name in required)
    started = time.monotonic()
    deadline = started + timeout_seconds
    attempt = 0
    while True:
        attempt += 1
        r = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{certs_dir}:/certs:ro", _DIAG_IMAGE, "sh", "-c", test_expr],
            capture_output=True, text=True, timeout=20,
        )
        waited = round(time.monotonic() - started, 2)
        if r.returncode == 0:
            return {"visible": True, "waited_seconds": waited, "attempts": attempt}
        if time.monotonic() >= deadline:
            return {
                "visible": False, "waited_seconds": waited, "attempts": attempt,
                "last_stderr": r.stderr.strip()[-1000:],
            }
        time.sleep(1)


def capture_cert_mount_failure_diagnostics(gateway_profile: str) -> dict:
    """Item 1(c): so chamado quando `start_block` de fato falhar com
    o erro de certificado -- nunca roda no caminho feliz. Junta: logs
    do `tls_kem_proxy` (container real, se ainda existir), `ls -la` no
    host E dentro de um container descartavel com o MESMO mount, e o
    mtime/ctime de cada arquivo exigido -- tudo so leitura, nada
    recria/conserta nada."""
    sys.path.insert(0, str(THESIS_SCRIPTS_DIR))
    import opin_flow as of
    certs_dir = of.V9_CERTS_DIR
    diag: dict = {"certs_dir": str(certs_dir)}

    logs = subprocess.run(["docker", "logs", of.TLS_KEM_PROXY_CONTAINER_NAME], capture_output=True, text=True)
    diag["tls_kem_proxy_logs"] = ((logs.stdout or "") + (logs.stderr or ""))[-4000:]

    host_ls = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{certs_dir}:/certs:ro", _DIAG_IMAGE, "ls", "-la", "/certs"],
        capture_output=True, text=True,
    )
    diag["container_ls"] = (host_ls.stdout or host_ls.stderr or "").strip()

    diag["host_stat"] = {}
    for name in _REQUIRED_CERT_FILES[gateway_profile]:
        p = certs_dir / name
        if not p.exists():
            diag["host_stat"][name] = "AUSENTE no host"
            continue
        st = p.stat()
        diag["host_stat"][name] = {
            "size": st.st_size,
            "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            "ctime_utc": datetime.fromtimestamp(st.st_ctime, tz=timezone.utc).isoformat(),
        }
    return diag


def assert_precondition(opin_profile: str) -> None:
    """Item 1: a MESMA checagem que as fixtures de teste usam -- este
    script nunca duplica a logica, so chama a funcao real."""
    sys.path.insert(0, str(TESTS_DIR))
    import conftest as test_conftest
    test_conftest.assert_stack_profile_matches(opin_profile)


def run_pytest_for_profile(opin_profile: str) -> dict:
    env = dict(os.environ, CRYPTO_PROFILE=opin_profile, V9_HARNESS="1")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(TESTS_DIR), "-q"],
        cwd=str(TESTS_DIR), env=env, capture_output=True, text=True, timeout=600,
    )
    return {"returncode": proc.returncode, "stdout_tail": proc.stdout[-4000:], "stderr_tail": proc.stderr[-2000:]}


def _relaunch_client_proxy_and_signer(opin_profile: str):
    """Decisao 165: pytest para proxy/signer no finally de cada modulo
    de teste (item 1 -- as fixtures nunca deixam nada pra tras) -- pra
    rodar a execucao do item 2 depois do pytest, relanca os dois pelas
    MESMAS funcoes que start_block/pytest ja usam
    (`opin_flow.start_tls_kem_proxy`/`start_pqc_signer_service`),
    nunca uma chamada docker nova. V9_HARNESS=1 forcado + reload, mesmo
    padrao de `test_hybrid_and_gate.py`'s `_with_v9_harness_forced`."""
    import importlib
    os.environ["V9_HARNESS"] = "1"
    os.environ.pop("REMOTE_GATEWAY_HOST", None)
    sys.path.insert(0, str(THESIS_SCRIPTS_DIR))
    import opin_flow as of
    importlib.reload(of)
    proxy = of.start_tls_kem_proxy(opin_profile, detached=True)
    signer_started = of.start_pqc_signer_service(opin_profile)
    return of, proxy, signer_started


def run_one_harness_execution(executor: "orch.SSHExecutor", gateway_profile: str, opin_profile: str) -> dict:
    of, proxy, signer_started = _relaunch_client_proxy_and_signer(opin_profile)
    try:
        result = executor.run_execution(gateway_profile, ROUTE, 1)
    finally:
        of.stop_pqc_signer_service(signer_started)
        of.stop_tls_kem_proxy(proxy)
        os.environ.pop("V9_HARNESS", None)
    orch._assert_call_and_handshake_counts(gateway_profile, ROUTE, 1, result)
    orch._assert_profile_negotiated(gateway_profile, ROUTE, 1, result)
    return {
        "n_calls": len(result.get("insurance", [])) + len(result.get("person", [])),
        "n_handshakes": orch._count_client_facing_handshakes(result.get("gateway_log_lines", [])),
        "curveID": result.get("curveID"),
        "dualAuthenticated": result.get("dualAuthenticated"),
        "tlsVersion": result.get("tlsVersion"),
    }


def teardown_stack(executor: "orch.SSHExecutor", gateway_profile: str) -> None:
    """Item 2 (divergencia deliberada de `stop_block`, pedido
    explicito): `docker compose down` de verdade (sem -v/--rmi/
    prune), nunca so `stop` -- cada perfil deste gate comeca de uma
    folha limpa, diferente de uma campanha (que preserva a rede entre
    blocos). `stop_block` ainda roda primeiro, pra parar proxy/signer
    do cliente pelo caminho normal; o gateway (nunca gerenciado pelo
    compose) leva um `docker rm -f` explicito depois do `down`."""
    try:
        executor.stop_block(gateway_profile, ROUTE)
    except Exception:
        pass
    # COMPOSE_PROFILES precisa cobrir TODOS os profiles declarados no
    # docker-compose.yml (achado ao vivo nesta validacao: sem isso,
    # `docker compose down` resolve o conjunto de servicos do projeto
    # contra o profile ATIVO -- nenhum aqui, ja que todo servico do
    # arquivo exige profile explicito -- e nao remove NADA, mesmo com
    # containers rodando) -- mesma lista que `conftest.py`'s mensagem
    # de skip ja usa pra subir o stack (main,dev,cs,build-only).
    cli.run_ssh(
        "127.0.0.1",
        'cd "$(pwd)/../../insurance-server-lambdas" && '
        "COMPOSE_PROFILES=main,dev,cs,build-only docker compose down",
        key_path=None,
    )
    cli.run_ssh("127.0.0.1", f"docker rm -f {executor.gateway_container} 2>/dev/null; true", key_path=None)


def run_gate_for_profile(executor: "orch.SSHExecutor", gateway_profile: str, run_pytest: bool) -> dict:
    opin_profile = orch.CLIENT_CRYPTO_PROFILE_ENV[gateway_profile]
    entry = {"gateway_profile": gateway_profile, "opin_profile": opin_profile, "ok": False, "steps": {}}
    try:
        # Decisao 166, item 1(b): so diagnostico -- registra quanto
        # tempo o MESMO bind mount levou pra ficar visivel por fora
        # do proxy real, mas nunca espera por isso antes de chamar
        # start_block (que roda do mesmo jeito, com ou sem isto).
        entry["cert_mount_wait"] = wait_for_cert_mount_visible(gateway_profile)
        try:
            executor.start_block(gateway_profile, ROUTE)
            entry["steps"]["start_block"] = "ok"
        except Exception as start_block_exc:
            if "no such file or directory" in str(start_block_exc) and "_client" in str(start_block_exc):
                entry["diagnostics"] = capture_cert_mount_failure_diagnostics(gateway_profile)
            raise

        assert_precondition(opin_profile)
        entry["steps"]["precondition"] = "ok"

        if run_pytest:
            pytest_result = run_pytest_for_profile(opin_profile)
            entry["pytest"] = pytest_result
            entry["steps"]["pytest"] = "ok" if pytest_result["returncode"] == 0 else "FAILED"
            if pytest_result["returncode"] != 0:
                raise RuntimeError(f"pytest falhou (rc={pytest_result['returncode']}) -- ver entry['pytest']")
        else:
            entry["steps"]["pytest"] = "skipped (--preflight-only)"

        execution = run_one_harness_execution(executor, gateway_profile, opin_profile)
        entry["execution"] = execution
        entry["steps"]["execution"] = "ok"
        entry["ok"] = True
    except Exception as e:
        entry["error"] = str(e)
        entry["steps"].setdefault("failure", str(e))
    finally:
        teardown_stack(executor, gateway_profile)
        entry["steps"]["teardown"] = "ok"
    return entry


def print_table(matrix: list[dict]) -> None:
    header = f"{'perfil':<14}{'start_block':<14}{'precond':<12}{'pytest':<10}{'44 chamadas':<14}{'6 handshakes':<14}{'OK':<6}"
    print(header)
    print("-" * len(header))
    for entry in matrix:
        execu = entry.get("execution", {})
        n_calls = execu.get("n_calls", "-")
        n_hs = execu.get("n_handshakes", "-")
        print(
            f"{entry['gateway_profile']:<14}{entry['steps'].get('start_block', '-'):<14}"
            f"{entry['steps'].get('precondition', '-'):<12}{entry['steps'].get('pytest', '-'):<10}"
            f"{str(n_calls):<14}{str(n_hs):<14}{'SIM' if entry['ok'] else 'NAO':<6}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", nargs="+", default=list(orch.PROFILES), choices=list(orch.PROFILES))
    ap.add_argument("--preflight-only", action="store_true", help="pula o pytest -- so infra + 1 execucao por perfil")
    args = ap.parse_args()

    shim_bin_dir = Path(tempfile.mkdtemp(prefix="v9_run_gate_shim_"))
    cli.enable_local_shell_shim(scripts_cwd=THESIS_SCRIPTS_DIR, python_exe=sys.executable, shim_bin_dir=shim_bin_dir)

    executor = _make_executor(Path.home() / "images")

    matrix = []
    images_before = snapshot_local_images()
    try:
        stop_legacy_mtls_alias_collision()
        for gateway_profile in args.profiles:
            print(f"== {gateway_profile} ==", file=sys.stderr)
            entry = run_gate_for_profile(executor, gateway_profile, run_pytest=not args.preflight_only)
            matrix.append(entry)
    finally:
        cli.disable_local_shell_shim()
    images_after = snapshot_local_images()
    assert_local_images_unchanged(images_before, images_after)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"run_gate_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")

    print_table(matrix)
    print(f"\nmatriz completa: {out_path}")
    return 0 if all(e["ok"] for e in matrix) else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Ensaio OFFLINE completo (pedido do Luciano, item d) -- roda o
orquestrador inteiro em modo campanha contra um inventario simulado
(3 servidores, 8 clientes, 4 perfis, 2 janelas de 32 celulas + 5
aquecimentos/celula/janela), passando por captura, dedicated_criteria
(criterio 2/7 de campanha) e os 7 criterios do avaliador (incluindo a
variante de campanha do criterio 2). NUNCA chamada de rede real,
NUNCA AWS -- so cli._run/cli.run_scp monkeypatchados (reusa os fakes
ja validados de test_orchestrator.py, nunca reinventa).

ACHADO REAL desta rodada (nunca escondido, reportado como pedido):
rodando ponta a ponta, o orquestrador em si (start_block/aquecimento/
run_execution/stop_block/dedicated_capture, os 3 servidores, os
samplers, collect_full_logs, run_criterio2_campaign, run_criterio7)
completa SEM QUEBRAR nenhuma vez -- 0 excecoes, 2 janelas x 32
celulas x (5 aquecimentos + 1 medida) = 384 execucoes reais simuladas
+ 64 capturas dedicadas. MAS, dos 7 criterios do avaliador, SO os
criterios 2 (corrigido nesta mesma rodada, achado B.5) e 5 (zero
erros, route/cardinalidade-agnostico por desenho) funcionam contra
dados de campanha -- os criterios 1, 3, 4, 6 e 7 tem cardinalidade
(60 execucoes/12 capturas, `EXPECTED_EXECUCOES_PILOTO`) e/ou rotulos
de rota (`PILOT_ROUTES=("L0","L219","L325")`, `L325_PROFILES`,
`NOMINAL_RTT_MS`) HARDCODED pro piloto -- a MESMA classe de gap que o
criterio 2 tinha antes desta rodada (achado B.5), nunca fechada pros
outros 5. Nenhum destes 5 foi wireado nesta rodada (fora do escopo
pedido) -- reportado aqui como achado concreto do ensaio, pra decisao
futura do Luciano."""
import json
import sys
import traceback
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent / "tests"))
sys.path.insert(0, str(SCRIPTS_DIR.parents[1] / "integration"))

import cli  # noqa: E402
import orchestrator as orch  # noqa: E402
import dedicated_criteria as dc  # noqa: E402
import campaign_topology as ct  # noqa: E402
import evaluate_criteria as ec  # noqa: E402
import test_orchestrator as to  # noqa: E402 -- reusa os fakes de tcpdump/tshark/docker ja validados

BREAKAGES = []


def report(step, exc):
    BREAKAGES.append((step, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))))
    print(f"\n*** QUEBROU em: {step} ***")
    print(f"{type(exc).__name__}: {exc}")


# --- Inventario simulado, 3 servidores + 8 clientes, mesmo formato de
# terraform_campanha_oficial/outputs.tf.
def build_inventory():
    servers = {sid: {"public_ip": f"203.0.113.{10+i}", "private_ip": f"10.0.0.{10+i}"}
               for i, sid in enumerate(ct.CAMPAIGN_SERVERS)}
    clients = {}
    for i, route in enumerate(ct.CAMPAIGN_ROUTES):
        colocated = route.startswith("L0-")
        clients[route] = {
            "public_ip": f"203.0.113.{60+i}", "private_ip": f"10.0.2.{60+i}",
            "colocated": colocated,
        }
    return {
        "control": {"public_ip": "203.0.113.5", "private_ip": "10.0.0.5"},
        "servers": servers, "clients": clients,
    }


import hashlib

_FAKE_GATEWAY_BINARY_BYTES = b"fake gateway elf binary -- ensaio offline"
_FAKE_GATEWAY_SHA256 = hashlib.sha256(_FAKE_GATEWAY_BINARY_BYTES).hexdigest()


class _SimpleProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _connection_ok_lines(n=6):
    return [f'gateway: PERFIL connection OK remoteAddr=203.0.113.{10+i}:5100{i} sni="mtls" '
            f'curve=SecP384r1MLKEM1024 dualAuthenticated=false clientCert="c"' for i in range(n)]


def make_fake_run(calls, extra_scp_targets):
    base_calls = []
    base_fake_run = to._fake_run_dedicated_capture(base_calls, gateway_log_output="\n".join(_connection_ok_lines()) + "\n")

    def fake_run(argv, timeout=None):
        calls.append(list(argv))
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        # Casos NOVOS de campanha (criterio 2/7 de campanha, sampler),
        # nunca cobertos pelo fake do piloto reusado abaixo -- checados
        # primeiro; tudo o mais cai no fake ja validado (tcpdump/
        # tshark/docker/sha256/listening on/campaign_client_runner.py).
        if "criterio2_probe.py" in remote_cmd:
            return _SimpleProc()
        if remote_cmd.startswith("test -f") and "criterio2_initcwnd" in remote_cmd:
            return _SimpleProc(stdout="FOUND\n")
        if remote_cmd.startswith("test -f /tmp/criterio1_"):
            return _SimpleProc(stdout="FOUND\n")
        if "criterio7_rtt.py probe" in remote_cmd:
            return _SimpleProc(stdout=json.dumps({"rtt_ms_probe": 50.0, "n_samples_probe": 20}))
        if "criterio7_rtt.py pcap" in remote_cmd:
            return _SimpleProc(stdout=json.dumps({"rtt_ms_pcap": 49.5, "n_samples_pcap": 1}))
        if "cpu_mem.jsonl" in remote_cmd or "cpu_mem.pid" in remote_cmd:
            return _SimpleProc()
        return base_fake_run(argv, timeout=timeout)
    return fake_run


def make_fake_scp():
    def fake_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        Path(dst).parent.mkdir(parents=True, exist_ok=True) if "@" not in str(dst) else None
        if "cpu_mem.jsonl" in str(src):
            local_dst = dst
            Path(local_dst).parent.mkdir(parents=True, exist_ok=True)
            Path(local_dst).write_text(
                json.dumps({"proc_stat_line": "cpu 100 0 50 1000 0 0 0 10"}) + "\n" +
                json.dumps({"proc_stat_line": "cpu 200 0 90 1200 0 0 0 60"}) + "\n",
                encoding="utf-8",
            )
        elif "criterio2_initcwnd" in str(src):
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_text(json.dumps({
                "route": "L123", "instance_type": "m7i-flex.large", "profile": "classico",
                "bytes_sent_total": 71680, "bytes_sent_within_first_rtt_window": 14480,
                "mss_bytes": 1448, "mss_channels_agree": True, "ss_ti_cwnd": 10,
                "offloads": {"tso": "off", "gso": "off", "gro": "off"},
            }), encoding="utf-8")
        elif str(dst).endswith(".pcap") or "criterio2" in str(src):
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_bytes(b"pcap falso")
        else:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            Path(dst).write_text("conteudo falso\n", encoding="utf-8")
        return _SimpleProc()
    return fake_scp


def main():
    import shutil
    import tempfile
    out_dir = Path(tempfile.mkdtemp(prefix="v9_ensaio_offline_campanha_"))
    print(f"(saida temporaria em {out_dir} -- nunca commitada)")

    inventory = build_inventory()
    calls = []
    cli._run = make_fake_run(calls, [])
    cli.run_scp = make_fake_scp()

    # Entrega de imagem (deliver_images.py, sha256/layers/config/binario
    # pinados em PINS.json) ja tem cobertura dedicada e extensa em
    # test_orchestrator.py (test_deliver_image_*) -- BYPASSADA aqui de
    # proposito (no-op) pra este ensaio focar no que ainda NUNCA foi
    # exercitado ponta a ponta: orquestracao/generalizacao de N
    # servidores, captura, criterio 2/7 de campanha, avaliador.
    orch.SSHExecutor._deliver_image = lambda self, image_key, host: None
    # Verificacao sha256 do binario do gateway (deliver_images.py's
    # output local, gateway_binary_info.json) -- mesma logica de
    # bypass, mesmo motivo (ja coberta a fundo em test_orchestrator.py
    # test_start_block_verifica_binario_correto_e_passa e correlatos).
    def _fake_verify_gateway_binary(self, profile, route):
        verification = {"profile": profile, "route": route, "sha256_expected": _FAKE_GATEWAY_SHA256}
        self.gateway_binary_verifications.append(verification)
        return verification
    orch.SSHExecutor._verify_gateway_binary = _fake_verify_gateway_binary
    orch.SSHExecutor._verify_running_gateway_binary = lambda self, verification: None

    executor = orch.SSHExecutor(inventory, key_path="/fake/key", route_server=dict(ct.CAMPAIGN_ROUTE_SERVER))

    print("=== PASSO 1: capture_ready_check (3 servidores) ===")
    try:
        result = executor.capture_ready_check()
        print("OK:", result)
    except Exception as e:
        report("capture_ready_check", e)

    print("\n=== PASSO 2: run_pilot, janela 1 (32 celulas, n_warmup=5) ===")
    manifest1 = None
    try:
        manifest1 = orch.run_pilot(
            executor, seed=1, out_dir=out_dir / "janela_01",
            n_per_profile=1, routes=list(ct.CAMPAIGN_ROUTES), profiles=list(orch.PROFILES),
            skip_dedicated_captures=False, n_warmup_per_profile=5,
        )
        print("OK: total_execucoes=", manifest1["total_execucoes"], "total_aquecimentos=", manifest1["total_aquecimentos"],
              "total_capturas=", manifest1["total_capturas"])
    except Exception as e:
        report("run_pilot janela 1", e)

    print("\n=== PASSO 3: run_pilot, janela 2 (32 celulas, n_warmup=5) ===")
    manifest2 = None
    try:
        manifest2 = orch.run_pilot(
            executor, seed=2, out_dir=out_dir / "janela_02",
            n_per_profile=1, routes=list(ct.CAMPAIGN_ROUTES), profiles=list(orch.PROFILES),
            skip_dedicated_captures=False, n_warmup_per_profile=5,
        )
        print("OK: total_execucoes=", manifest2["total_execucoes"], "total_aquecimentos=", manifest2["total_aquecimentos"])
    except Exception as e:
        report("run_pilot janela 2", e)

    janela1_dir = out_dir / "janela_01"

    print("\n=== PASSO 4: collect_full_logs (deve cobrir os 3 servidores) ===")
    try:
        logs_result = dc.collect_full_logs(executor, janela1_dir)
        servers_seen = {k for k in logs_result["containers"].keys() if any(k.startswith(f"{s}_") for s in ct.CAMPAIGN_SERVERS)}
        print("OK: chaves com prefixo de servidor =", len(servers_seen), "de", len(logs_result["containers"]),
              "-- servidores distintos:", {k.rsplit("_", 1)[0] if False else k.split("_v9-mtls")[0].split("_insurance")[0] for k in servers_seen})
    except Exception as e:
        report("collect_full_logs", e)

    print("\n=== PASSO 5: run_criterio2_campaign (L325 + 2 direcoes, entre outras) ===")
    try:
        c2_results = dc.run_criterio2_campaign(executor, janela1_dir)
        falhas = [k for k, v in c2_results.items() if not v["ok"]]
        print("OK: combinacoes =", list(c2_results.keys()))
        print("falhas =", falhas)
    except Exception as e:
        report("run_criterio2_campaign", e)

    print("\n=== PASSO 6: run_criterio7 em todas as rotas nao-L0 ===")
    try:
        non_l0_routes = tuple(r for r in ct.CAMPAIGN_ROUTES if not r.startswith("L0-"))
        c7_result = dc.run_criterio7(executor, janela1_dir, routes=non_l0_routes)
        print("OK: rotas =", list(c7_result.keys()))
    except Exception as e:
        report("run_criterio7", e)

    print("\n=== PASSO 7: os 7 criterios do avaliador (incluindo criterion_2_initcwnd_campaign) ===")
    try:
        if manifest1:
            log_text = Path(manifest1["combined_log"]).read_text(encoding="utf-8")
            execucoes = json.loads(Path(manifest1["calls_json"]).read_text(encoding="utf-8"))
            c1 = ec.criterion_1_message_sizes(log_text, str(janela1_dir))
            c2 = ec.criterion_2_initcwnd_campaign(str(janela1_dir))
            c3 = ec.criterion_3_distant_route(str(janela1_dir))
            c4 = ec.criterion_4_counts(execucoes, log_text)
            c5 = ec.criterion_5_zero_errors(log_text)
            c6 = ec.criterion_6_instrumentation(log_text, str(janela1_dir))
            c7 = ec.criterion_7_latency_sanity(str(janela1_dir))
            for r in (c1, c2, c3, c4, c5, c6, c7):
                status = "PASS" if r["pass"] else "FAIL"
                note = r.get("note", "")
                print(f"criterio {r['criterion']} ({r['name']}): {status} {('-- ' + str(note)) if note else ''}")
        else:
            print("PULADO -- manifest1 nao existe (passo 2 quebrou)")
    except Exception as e:
        report("7 criterios", e)

    print("\n\n========== RESUMO ==========")
    if not BREAKAGES:
        print("NENHUMA quebra -- todos os passos completaram.")
    else:
        print(f"{len(BREAKAGES)} passo(s) quebraram:")
        for step, tb in BREAKAGES:
            print(f"\n--- {step} ---")
            print(tb)


if __name__ == "__main__":
    main()

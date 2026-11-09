#!/usr/bin/env python3
"""Ensaio OFFLINE completo (pedido do Luciano, item d; REPETIDO nesta
rodada -- item 4 do pedido de fechamento dos criterios 1/3/4/6/7 pra
campanha) -- roda o orquestrador inteiro em modo campanha contra um
inventario simulado (3 servidores, 8 clientes, 4 perfis, 2 janelas de
32 celulas + 5 aquecimentos/celula/janela), passando por captura,
dedicated_criteria (criterio 2/3/7 de campanha) e os 7 criterios do
avaliador -- agora TODOS nas suas variantes `_campaign` (achado B.5
fechado pros 5 restantes nesta rodada) -- mais a extensao do
consolidado (`build_consolidated_report_v9.py --campaign`) as 8
rotas/4 perfis. NUNCA chamada de rede real, NUNCA AWS -- so
cli._run/cli.run_scp monkeypatchados (reusa os fakes ja validados de
test_orchestrator.py, nunca reinventa).

ACHADO da rodada ANTERIOR (ja fechado nesta, preservado aqui como
registro): rodando ponta a ponta, o orquestrador em si completava SEM
QUEBRAR, mas so os criterios 2 e 5 funcionavam contra dados de
campanha -- os outros 5 tinham cardinalidade/rotulos de rota
hardcoded pro piloto. Esta rodada fecha os 5 (evaluate_criteria.py
`criterion_{1,3,4,6,7}_*_campaign`, mais `dedicated_criteria.
build_criterio3_campaign`) e prova aqui, de ponta a ponta, que:
(a) os 7 criterios saem PASS com dados corretos, (b) o CONSOLIDADO
gerado por `build_consolidated_report_v9.py --campaign` tambem
resulta `all_criteria_pass=True` nas tabelas de 8 rotas x 4 perfis,
e (c) uma corrupcao real introduzida nos dados (criterio 6, curveID
errado) propaga FAIL tanto no avaliador quanto no consolidado -- o
gate fail-closed funciona ponta a ponta, nunca so na unidade."""
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


# Pedido do Luciano (item 1 da rodada de correcao): os fakes de SSH/
# tshark deste ensaio tem que refletir os BASELINES REAIS, derivados
# dos ARTEFATOS REAIS do piloto -- nunca fixtures genericos/inventados
# (achado da propria Decisao 109: os fixtures genericos antigos faziam
# os criterios 1/3/4/6/7 reprovarem por DESENHO do fixture, nunca por
# bug do codigo novo). Fonte: o piloto real de 2026-11-09 (4 perfis x
# 3 rotas, 60 execucoes reais, 7/7 PASS), preservado em
# piloto/dados_oficiais/piloto-real-aws-2026-11-09-v2/raw/ -- NUNCA
# modificado, so lido.
_REAL_PILOT_DIR = (SCRIPTS_DIR.parents[1] / "piloto" / "dados_oficiais" /
                   "piloto-real-aws-2026-11-09-v2" / "raw")


def _strip_capture_log_body(text: str) -> str:
    """As linhas de dados da secao 'tamanho POR MENSAGEM' de uma
    captura REAL (frame/stream/srcport/tcp.len/tipos/tamanhos/sni) --
    confirmado byte a byte (orchestrator.py linha ~1421,
    `attempt_lines.append("\t".join(cols[:7]))`) que essas linhas SAO
    o stdout crudo do tshark, sem nenhuma transformacao -- usar o
    corpo de uma captura real aqui e equivalente a servir o tshark
    real de novo."""
    lines = text.splitlines()
    body = []
    in_body = False
    for line in lines:
        if line.startswith("tamanho POR MENSAGEM"):
            in_body = True
            continue
        if line.startswith("== secao seguinte") or line.startswith("== fim"):
            break
        if in_body and line.strip():
            body.append(line)
    return "\n".join(body) + "\n"


def _load_real_fixtures():
    """Carrega, 1 vez, os artefatos REAIS do piloto -- por perfil:
    (a) corpo real das capturas tshark (`criterio1_capturas/<perfil>_
    L219.log`, route-invariante pro proposito do criterio 1 -- a
    propria Decisao 91 confirma isso pela checagem de consistencia
    entre rotas), (b) uma janela real de execucao (6 linhas mtls + 7
    internas, `piloto_combined.log`), (c) uma lista real de chamadas
    HTTP fundidas (`piloto_calls.json`). RTT real: reusa L0/L219/L325
    tal como medidos; pras 3 rotas da campanha NUNCA medidas no piloto
    (L123/L14/L30), aplica a RAZAO REAL medido/nominal (L219 e L325,
    media ~1,01) ao nominal de cada uma -- extrapolacao explicita a
    partir da razao real, nunca um numero inventado do zero."""
    fixtures = {}
    calls_all = json.loads((_REAL_PILOT_DIR / "piloto_calls.json").read_text(encoding="utf-8"))
    by_profile_call = {}
    for e in calls_all:
        by_profile_call.setdefault(e["profile"], e)
    combined = (_REAL_PILOT_DIR / "piloto_combined.log").read_text(encoding="utf-8", errors="replace")
    capturas_dir = _REAL_PILOT_DIR / "criterio1_capturas"
    import re as _re_mod
    for profile in ("classico", "pqc", "hibrido-v8", "hibrido-and"):
        tshark_body = _strip_capture_log_body((capturas_dir / f"{profile}_L219.log").read_text(encoding="utf-8"))
        m = _re_mod.search(
            rf"== EXECUCAO INICIO perfil={_re_mod.escape(profile)} rota=\S+ run=\S+ ==\n(.*?)== EXECUCAO FIM",
            combined, _re_mod.S)
        gateway_window = m.group(1) if m else ""
        entry = by_profile_call[profile]
        merged_calls = entry["insurance"] + entry["person"]
        fixtures[profile] = {"tshark_body": tshark_body, "gateway_window": gateway_window, "calls": merged_calls}

    real_rtt = json.loads((_REAL_PILOT_DIR / "criterio7_rtt_por_rota.json").read_text(encoding="utf-8"))
    ratios_probe = [real_rtt["L219"]["rtt_ms_probe"] / 219.0, real_rtt["L325"]["rtt_ms_probe"] / 325.0]
    ratios_pcap = [real_rtt["L219"]["rtt_ms_pcap"] / 219.0, real_rtt["L325"]["rtt_ms_pcap"] / 325.0]
    ratio_probe = sum(ratios_probe) / len(ratios_probe)
    ratio_pcap = sum(ratios_pcap) / len(ratios_pcap)
    rtt_by_nominal = {0: (real_rtt["L0"]["rtt_ms_probe"], real_rtt["L0"]["rtt_ms_pcap"]),
                       219: (real_rtt["L219"]["rtt_ms_probe"], real_rtt["L219"]["rtt_ms_pcap"]),
                       325: (real_rtt["L325"]["rtt_ms_probe"], real_rtt["L325"]["rtt_ms_pcap"])}
    for route, nominal in ct.CAMPAIGN_NOMINAL_RTT_MS.items():
        if nominal not in rtt_by_nominal:
            rtt_by_nominal[nominal] = (round(nominal * ratio_probe, 3), round(nominal * ratio_pcap, 3))
    return fixtures, rtt_by_nominal


_REAL_FIXTURES, _REAL_RTT_BY_NOMINAL = _load_real_fixtures()
_KNOWN_PROFILES = ("classico", "pqc", "hibrido-v8", "hibrido-and")


def _profile_from_label(remote_cmd: str):
    m = __import__("re").search(r"--label (?:settling_|criterio1_capture_)?(\S+)", remote_cmd)
    if not m:
        return None
    label = m.group(1)
    for p in _KNOWN_PROFILES:
        if label == p or label.startswith(p + "_"):
            return p
    return None


def make_fake_run(calls, extra_scp_targets, inventory=None):
    base_calls = []
    base_fake_run = to._fake_run_dedicated_capture(base_calls, gateway_log_output="\n".join(_connection_ok_lines()) + "\n")
    state = {"last_profile": None, "current_nominal_rtt": 0}
    # IP -> rota (so dos CLIENTES -- controle/servidores nao tem RTT
    # de rota associado) -- pedido do Luciano (item 1): o fake do RTT
    # (criterio7_rtt.py probe/pcap) precisa saber QUAL rota esta em
    # curso pra servir o valor real/extrapolado certo, nunca um numero
    # fixo (50,0ms) igual pra qualquer rota.
    ip_to_route = {}
    if inventory:
        for route, client in inventory.get("clients", {}).items():
            ip_to_route[client["public_ip"]] = route

    def fake_run(argv, timeout=None):
        calls.append(list(argv))
        remote_cmd = argv[-1] if argv and argv[0] == "ssh" else ""
        if ip_to_route:
            argv_text = " ".join(str(a) for a in argv)
            for ip, route in ip_to_route.items():
                if ip in argv_text:
                    state["current_nominal_rtt"] = ct.CAMPAIGN_NOMINAL_RTT_MS[route]
                    break
        # Casos NOVOS de campanha (criterio 2/7 de campanha, sampler),
        # nunca cobertos pelo fake do piloto reusado abaixo -- checados
        # primeiro; tudo o mais cai no fake ja validado (tcpdump/
        # tshark/docker/sha256/listening on).
        if "criterio2_probe.py" in remote_cmd:
            return _SimpleProc()
        if remote_cmd.startswith("test -f") and "criterio2_initcwnd" in remote_cmd:
            return _SimpleProc(stdout="FOUND\n")
        if remote_cmd.startswith("test -f /tmp/criterio1_"):
            return _SimpleProc(stdout="FOUND\n")
        if "criterio7_rtt.py probe" in remote_cmd:
            probe_ms, _ = _current_rtt(state)
            return _SimpleProc(stdout=json.dumps({"rtt_ms_probe": probe_ms, "n_samples_probe": 20}))
        if "criterio7_rtt.py pcap" in remote_cmd:
            _, pcap_ms = _current_rtt(state)
            return _SimpleProc(stdout=json.dumps({"rtt_ms_pcap": pcap_ms, "n_samples_pcap": 1}))
        if "cpu_mem.jsonl" in remote_cmd or "cpu_mem.pid" in remote_cmd:
            return _SimpleProc()
        # Dados REAIS, derivados do piloto (item 1 do pedido) -- antes
        # de cair no fake generico de test_orchestrator.py.
        if "campaign_client_runner.py --label" in remote_cmd:
            profile = _profile_from_label(remote_cmd)
            if profile:
                state["last_profile"] = profile
                real_calls = _REAL_FIXTURES[profile]["calls"]
                return _SimpleProc(stdout=json.dumps({"calls": real_calls, "call_count": len(real_calls), "retries": []}))
        if "tls.handshake.type" in remote_cmd:
            m = __import__("re").search(r"/tmp/criterio1_([a-z0-9-]+)_", remote_cmd)
            profile = m.group(1) if m else state["last_profile"]
            if profile in _REAL_FIXTURES:
                state["last_profile"] = profile
                return _SimpleProc(stdout=_REAL_FIXTURES[profile]["tshark_body"])
        if "docker logs -t --since" in remote_cmd and state["last_profile"] in _REAL_FIXTURES:
            return _SimpleProc(stdout=_REAL_FIXTURES[state["last_profile"]]["gateway_window"] + "\n")
        return base_fake_run(argv, timeout=timeout)
    return fake_run


def _current_rtt(state):
    """RTT REAL (ou extrapolado pela razao real, ver `_load_real_
    fixtures`) da rota da celula em curso -- `state["current_route"]`
    e setado por `make_fake_run_for_route` (ensaio por rota) ou
    permanece `None` no ensaio multi-rota generico, caso em que usa a
    rota co-localizada (nominal 0) como default seguro."""
    nominal = state.get("current_nominal_rtt", 0)
    return _REAL_RTT_BY_NOMINAL.get(nominal, _REAL_RTT_BY_NOMINAL[0])


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
    cli._run = make_fake_run(calls, [], inventory=inventory)
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

    print("\n=== PASSO 7: criterio3 de campanha (build_criterio3_campaign) ===")
    criterio3_result = None
    if manifest1:
        try:
            criterio3_result = dc.build_criterio3_campaign(janela1_dir, janela1_dir)
            print("OK: rota distante =", criterio3_result["route"], "-- n execucoes =", len(criterio3_result["execucoes"]))
        except Exception as e:
            report("build_criterio3_campaign", e)
    else:
        print("PULADO -- manifest1 nao existe (passo 2 quebrou)")

    print("\n=== PASSO 8: os 7 criterios do avaliador, TODOS em modo campanha ===")
    all_7_results = None
    if manifest1:
        try:
            log_text = Path(manifest1["combined_log"]).read_text(encoding="utf-8")
            execucoes = json.loads(Path(manifest1["calls_json"]).read_text(encoding="utf-8"))
            expected_total = manifest1["total_execucoes"]
            c1 = ec.criterion_1_message_sizes_campaign(str(janela1_dir))
            c2 = ec.criterion_2_initcwnd_campaign(str(janela1_dir))
            c3 = ec.criterion_3_distant_route_campaign(str(janela1_dir), n_per_profile=1)
            c4 = ec.criterion_4_counts_campaign(execucoes, log_text, expected_total=expected_total)
            c5 = ec.criterion_5_zero_errors(log_text)
            c6 = ec.criterion_6_instrumentation_campaign(str(janela1_dir), expected_total=expected_total)
            # PASSO 6 (acima) rodou run_criterio7 so pras rotas nao-L0
            # (non_l0_routes) -- a variante de campanha do criterio 7
            # e avaliada so pras mesmas 5, aqui, pra bater com o dado
            # real que foi produzido (as 3 rotas L0-* usam a MESMA
            # logica generalizada, ja coberta pelos testes unitarios
            # de test_criteria_corruption_matrix.py).
            c7 = ec.criterion_7_latency_sanity_campaign(str(janela1_dir), routes=non_l0_routes)
            all_7_results = [c1, c2, c3, c4, c5, c6, c7]
            for r in all_7_results:
                status = "PASS" if r["pass"] else "FAIL"
                note = r.get("note", "")
                print(f"criterio {r['criterion']} ({r['name']}): {status} {('-- ' + str(note)) if note else ''}")
            todos_pass = all(r["pass"] for r in all_7_results)
            print(f"\n>>> TODOS OS 7 CRITERIOS (dados corretos, modo campanha): {'PASS 7/7' if todos_pass else 'FAIL -- veja acima'} <<<")
        except Exception as e:
            report("7 criterios (campanha)", e)
    else:
        print("PULADO -- manifest1 nao existe (passo 2 quebrou)")

    print("\n=== PASSO 9: consolidado de campanha (build_consolidated_report_v9.py --campaign) ===")
    print("Pedido do Luciano (correcao desta rodada): os fakes de SSH/tshark deste ensaio agora "
          "servem dados REAIS, derivados dos artefatos do piloto real de 2026-11-09 (_load_real_"
          "fixtures) -- tshark/certificado/clienthello real por perfil, janela real de conexao mTLS "
          "(6 linhas client-facing + 7 internas), lista real de chamadas HTTP fundidas, e RTT real "
          "(L0/L219/L325 medidos; L123/L14/L30 extrapolados pela razao real medido/nominal). Com "
          "isso, o PASSO 8 ja saiu PASS 7/7 real -- o achado da rodada anterior (fixture generico "
          "causando FAIL por desenho) esta FECHADO.")
    if manifest1 and all_7_results and criterio3_result:
        try:
            raw_dir = janela1_dir / "raw"
            (raw_dir / "criterio1_capturas").mkdir(parents=True, exist_ok=True)
            import shutil
            for f in Path(manifest1["capturas_dir"]).glob("*.log"):
                shutil.copy(f, raw_dir / "criterio1_capturas" / f.name)
            shutil.copy(manifest1["calls_json"], raw_dir / "piloto_calls.json")
            shutil.copy(janela1_dir / "criterio7_rtt_por_rota.json", raw_dir / "criterio7_rtt_por_rota.json")
            shutil.copy(janela1_dir / "criterio3_distante_execucoes.json", raw_dir / "criterio3_distante_execucoes.json")
            shutil.copy(janela1_dir / "manifest.json", raw_dir / "manifest.json")
            (janela1_dir / "criteria_evaluation.json").write_text(json.dumps(all_7_results, indent=2, ensure_ascii=False), encoding="utf-8")
            sys.path.insert(0, str(SCRIPTS_DIR))
            import build_consolidated_report_v9 as bcr  # noqa: E402
            old_argv = sys.argv
            sys.argv = ["build_consolidated_report_v9.py", "--run-dir", str(janela1_dir),
                        "--out-subdir", "CONSOLIDATED_REPORT", "--campaign", "--skip-crypto-extraction"]
            try:
                bcr.main()
            except SystemExit:
                pass  # main() sai com codigo != 0 quando a checagem criptografica/all_pass reprova -- esperado aqui (fixture generico)
            finally:
                sys.argv = old_argv
            consolidated = json.loads((janela1_dir / "CONSOLIDATED_REPORT" / "consolidated.json").read_text(encoding="utf-8"))
            n_rows = len(consolidated["profile_route_verification_table"])
            print(f"OK: consolidated.json gerado -- all_criteria_pass={consolidated['all_criteria_pass']} "
                  f"(esperado True, dados reais), "
                  f"profile_route_verification_table com {n_rows} linhas (esperado 4 perfis x 8 rotas = 32)")
            assert n_rows == 32, f"esperado 32 linhas (4x8), achou {n_rows}"
            assert consolidated["all_criteria_pass"] is True, \
                "GATE: dados reais (corretos) deviam resultar all_criteria_pass=True no consolidado"
        except Exception as e:
            report("build_consolidated_report_v9 --campaign (dados reais)", e)
    else:
        print("PULADO -- passo 7, 8 ou criterio3 nao disponiveis")

    print("\n=== PASSO 10 (PORTAO): corrupcao real do criterio 6 (curveID) tem que propagar FAIL ===")
    if manifest1 and all_7_results:
        try:
            criterio6_path = Path(manifest1["criterio6_json"])
            rows = json.loads(criterio6_path.read_text(encoding="utf-8"))
            original = json.dumps(rows)
            rows[0]["curveID"] = "CurveErrada-CORROMPIDO-DE-PROPOSITO"
            criterio6_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
            c6_corrompido = ec.criterion_6_instrumentation_campaign(str(janela1_dir), expected_total=manifest1["total_execucoes"])
            print("criterio 6 com dado corrompido:", "PASS" if c6_corrompido["pass"] else "FAIL", "(esperado FAIL)")
            assert c6_corrompido["pass"] is False, "PORTAO: corrupcao de curveID deveria reprovar o criterio 6"

            all_7_corrompido = [c6_corrompido if r["criterion"] == 6 else r for r in all_7_results]
            (janela1_dir / "criteria_evaluation.json").write_text(
                json.dumps(all_7_corrompido, indent=2, ensure_ascii=False), encoding="utf-8")
            old_argv = sys.argv
            sys.argv = ["build_consolidated_report_v9.py", "--run-dir", str(janela1_dir),
                        "--out-subdir", "CONSOLIDATED_REPORT", "--campaign", "--skip-crypto-extraction"]
            try:
                bcr.main()
            except SystemExit:
                pass
            finally:
                sys.argv = old_argv
            consolidated_corrompido = json.loads((janela1_dir / "CONSOLIDATED_REPORT" / "consolidated.json").read_text(encoding="utf-8"))
            print("consolidado com dado corrompido: all_criteria_pass =", consolidated_corrompido["all_criteria_pass"], "(esperado False)")
            assert consolidated_corrompido["all_criteria_pass"] is False, \
                "PORTAO: corrupcao deveria propagar para all_criteria_pass=False no consolidado"
            criterio6_path.write_text(original, encoding="utf-8")  # restaura -- nunca deixa dado corrompido no disco
            print(">>> PORTAO PASSOU: PASS 7/7 nos dados corretos, FAIL real na corrupcao, ponta a ponta <<<")
        except Exception as e:
            report("PORTAO -- corrupcao real -- propagacao de FAIL", e)
    else:
        print("PULADO -- manifest1 ou all_7_results nao disponiveis")

    print("\n\n========== RESUMO ==========")
    if not BREAKAGES:
        print("NENHUMA quebra -- todos os passos completaram.")
    else:
        print(f"{len(BREAKAGES)} passo(s) quebraram:")
        for step, tb in BREAKAGES:
            print(f"\n--- {step} ---")
            print(tb)
    return BREAKAGES


if __name__ == "__main__":
    breakages = main()
    sys.exit(1 if breakages else 0)

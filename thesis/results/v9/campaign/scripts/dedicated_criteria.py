#!/usr/bin/env python3
"""v9, piloto: liga os 3 produtores dedicados dos criterios 2
(initcwnd real), 3 (zero erros na rota mais distante) e 7 (RTT por
rota) ao pipeline real e ao consolidador (Decisao 85, pedido do
Luciano) -- antes desta Decisao, nenhum dos 3 jamais rodava contra o
piloto real (gap conhecido e documentado, Decisao 79). Chamado DEPOIS
que `run_pilot` ja terminou (precisa das 60 execucoes reais pro
criterio 3, e dos pcaps dedicados -- ja escritos em `/tmp` no
servidor por `dedicated_capture`/`_launch_gateway` -- pro canal pcap
do criterio 7).

Decisao 85, achado real de projeto (corrigido nos 2 produtores, nunca
aqui): nem `criterio2_probe.py` nem `criterio7_rtt.py` tinham como
rodar `tshark` -- o servidor real nunca tem esse binario no PATH do
host (so dentro de `mockopin-v9-measure`, a mesma imagem pinada que
`dedicated_capture` ja usa). Os dois produtores foram corrigidos pra
rodar `tshark` via `docker run --entrypoint tshark mockopin-v9-
measure` -- nunca reconstroem nem mudam a imagem."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402
import orchestrator as orch  # noqa: E402

_INTEGRATION_DIR = Path(__file__).resolve().parents[2] / "integration"
sys.path.insert(0, str(_INTEGRATION_DIR))
import evaluate_criteria as ec  # noqa: E402

CRITERIO2_LISTEN_PORT = 9876
# Decisao 85: NUNCA L0 -- criterio2_probe.py so e significativo com
# RTT > 0 de verdade (docstring do proprio script, "limite
# estrutural"); L0 e colocated (RTT ~0).
CRITERIO2_PROBE_ROUTE = "L219"
_REMOTE_CRITERIO2_OUT = "/tmp/criterio2_initcwnd.json"
_REMOTE_PRODUCERS_DIR = "~/thesis/results/v9/integration/producers"


def run_criterio2(executor, out_dir: Path, route: str = CRITERIO2_PROBE_ROUTE, direction: str = "server-to-client",
                   label: str | None = None) -> dict:
    """Sobe `criterio2_probe.py` num dos dois lados (background),
    dispara UMA conexao de teste do OUTRO lado (`/dev/tcp` puro, mesmo
    mecanismo que `_tcp_preflight` ja usa -- nunca `nc`, nem sempre
    instalado), espera o arquivo aparecer, traz o JSON de volta pro
    `out_dir`.

    `direction="server-to-client"` (default, piloto, igual sempre):
    probe escuta no SERVIDOR, o CLIENTE dispara -- mede o initcwnd do
    SERVIDOR. `direction="client-to-server"` (gap fechado, pedido do
    Luciano): INVERTE os papeis -- o probe escuta no CLIENTE, o
    SERVIDOR dispara -- mede o initcwnd do CLIENTE. Exige uma regra de
    ingress nova na porta do probe, do servidor pro cliente (ver
    `terraform_campanha_oficial/main.tf`, variavel `criterio2_reverse_
    ingress_cidrs` do modulo) -- nunca existe no piloto, por isso este
    `direction` so faz sentido em modo campanha.

    `label` (None = piloto, caminhos remotos/locais FIXOS, identicos a
    sempre -- compatibilidade, item 1): identifica a combinacao rota+
    direcao nos nomes de arquivo, pra rodar varias vezes (por servidor/
    rota/direcao) sem colidir -- campanha oficial sempre passa um."""
    if direction == "server-to-client":
        listener_host = executor._server_ip(route)
        trigger_host = executor._client_ip(route)
        target_ip = executor._server_gateway_ip(route)
    elif direction == "client-to-server":
        listener_host = executor._client_ip(route)
        trigger_host = executor._server_ip(route)
        target_ip = executor._client_ip(route)
    else:
        raise ValueError(f"run_criterio2: direction invalida: {direction!r} (server-to-client ou client-to-server)")

    remote_out = _REMOTE_CRITERIO2_OUT if label is None else f"/tmp/criterio2_initcwnd_{label}.json"
    remote_pcap = "/tmp/criterio2.pcap" if label is None else f"/tmp/criterio2_{label}.pcap"
    remote_log = "/tmp/criterio2_probe.log" if label is None else f"/tmp/criterio2_probe_{label}.log"

    iface_proc = cli.run_ssh(listener_host, "ip -o -4 route show to default | awk '{print $5}' | head -1",
                              key_path=executor.key_path)
    iface = (iface_proc.stdout or "").strip()
    if not iface:
        raise RuntimeError("run_criterio2: nao consegui descobrir a interface primaria do host que escuta")

    rm_proc = cli.run_ssh(listener_host, f"rm -f {remote_out} {remote_log}", key_path=executor.key_path)
    launch_cmd = (
        f"cd {_REMOTE_PRODUCERS_DIR} && "
        f"nohup python3 criterio2_probe.py --listen-port {CRITERIO2_LISTEN_PORT} --iface {iface} "
        f"--route {route} --instance-type m7i-flex.large --profile classico "
        f"--pcap {remote_pcap} --out {remote_out} > {remote_log} 2>&1 &"
    )
    # Decisao 94 (achado real, ao vivo, na primeira execucao real deste
    # script, Passo 11.5): o processo em segundo plano SEMPRE iniciava
    # com sucesso (confirmado via `ps aux`/log no servidor, repetidas
    # vezes, com o PID vivo e realmente escutando) mesmo quando a
    # SESSAO SSH que o lancava nunca retornava a tempo (estourava o
    # timeout de 50s do cliente) -- NUNCA um problema de sintaxe do
    # comando (`< /dev/null`, `stdin=DEVNULL`, `setsid`, `sh -c
    # '...& echo $!'`, `ssh -f`: nenhuma das 5 tentativas mudou nada,
    # o MESMO comando simples de sempre, sem nenhuma dessas adicoes,
    # retornou em ~1,3s assim que testado manualmente, de novo, apos
    # so uns 15s de intervalo). Causa real: a sessao de controle tinha
    # acabado de terminar as 60 execucoes + 12 capturas reais do Passo
    # 11 (muitas conexoes SSH em sequencia rapida pro mesmo par de
    # hosts) -- throttling transitorio do lado do servidor (`sshd` ou
    # a pilha de rede), nunca visto fora dessa janela. Corrigido com
    # retry simples (backoff curto), nunca mudando o mecanismo de
    # lancamento em si.
    start_proc = None
    for attempt in range(3):
        try:
            start_proc = cli.run_ssh(listener_host, launch_cmd, key_path=executor.key_path)
            break
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise RuntimeError(
                    "run_criterio2: a sessao SSH que sobe o probe nunca retornou em 3 tentativas "
                    "(timeout, provavel throttling transitorio do servidor logo apos o Passo 11)"
                )
            time.sleep(15)
    if start_proc.returncode != 0:
        raise RuntimeError(f"run_criterio2: falhou subindo o probe: {cli.redact(start_proc.stderr)}")
    time.sleep(2)  # da tempo do probe abrir a porta e comecar o tcpdump antes do outro lado discar

    connect_proc = cli.run_ssh(
        trigger_host,
        f"timeout 20 bash -c 'cat < /dev/tcp/{target_ip}/{CRITERIO2_LISTEN_PORT} > /dev/null'",
        key_path=executor.key_path, connect_timeout=30,
    )
    if connect_proc.returncode != 0:
        raise RuntimeError(f"run_criterio2: conexao de teste falhou: {cli.redact(connect_proc.stderr)}")

    for _ in range(10):
        check = cli.run_ssh(listener_host, f"test -f {remote_out} && echo FOUND", key_path=executor.key_path)
        if "FOUND" in (check.stdout or ""):
            break
        time.sleep(1)
    else:
        log_proc = cli.run_ssh(listener_host, f"cat {remote_log} 2>/dev/null", key_path=executor.key_path)
        raise RuntimeError(
            f"run_criterio2: {remote_out} nunca apareceu -- "
            f"log do probe: {cli.redact(log_proc.stdout)}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = "criterio2_initcwnd.json" if label is None else f"criterio2_initcwnd_{label}.json"
    local_path = out_dir / out_name
    scp_proc = cli.run_scp(f"ec2-user@{listener_host}:{remote_out}", str(local_path), key_path=executor.key_path)
    if scp_proc.returncode != 0:
        raise RuntimeError(f"run_criterio2: scp do resultado falhou: {cli.redact(scp_proc.stderr)}")

    # Pedido do Luciano (item 0, regra fail-closed nova): o pcap bruto
    # deste teste dedicado ficava SO no servidor (/tmp/criterio2.pcap),
    # destruido junto com a instancia no teardown -- nunca fazia parte
    # do que `collect_artifacts.py` verifica por sha256 (so o JSON).
    # Trazido agora pra DENTRO do MESMO `out_dir` que o manifesto
    # global ja cobre -- vira evidencia bruta preservada por construcao,
    # nunca um passo separado de verificacao.
    pcap_name = "criterio2_probe.pcap" if label is None else f"criterio2_probe_{label}.pcap"
    pcap_local_path = out_dir / pcap_name
    pcap_scp_proc = cli.run_scp(f"ec2-user@{listener_host}:{remote_pcap}", str(pcap_local_path), key_path=executor.key_path)
    if pcap_scp_proc.returncode != 0:
        raise RuntimeError(f"run_criterio2: scp do pcap bruto falhou: {cli.redact(pcap_scp_proc.stderr)}")

    return json.loads(local_path.read_text(encoding="utf-8"))


def run_criterio2_campaign(executor, out_dir: Path, routes=None) -> dict:
    """Pedido do Luciano (generalizacao N-servidores): o probe do
    criterio 2 rodava SO 1 vez, SO em L219, SO na direcao servidor->
    cliente -- 2 gaps declarados como limitacao, nunca fechados (L325
    nunca testado; cliente->servidor nunca medido). Fecha os dois:
    roda uma vez por ROTA dada (default -- `campaign_topology.
    CAMPAIGN_ROUTES` com RTT>0, ou seja, tudo exceto as 3 L0 -- inclui
    L325 explicitamente) E nas duas direcoes (precisa da regra de
    ingress reversa, ver docstring de `run_criterio2`). Cada chamada
    usa um `label` unico (`{route}_{direction}`), nunca colide.
    Qualquer falha individual e registrada, nunca aborta as outras --
    o resultado final diz exatamente quais rodaram e quais nao."""
    import campaign_topology as ct
    routes = routes if routes is not None else [r for r in ct.CAMPAIGN_ROUTES if ct.CAMPAIGN_NOMINAL_RTT_MS[r] > 0]
    results = {}
    for route in routes:
        for direction in ("server-to-client", "client-to-server"):
            label = f"{route}_{direction}"
            try:
                results[label] = {"ok": True, "data": run_criterio2(executor, out_dir, route=route, direction=direction, label=label)}
            except Exception as e:  # noqa: BLE001 -- registra QUALQUER falha individual, nunca aborta as outras rotas/direcoes
                results[label] = {"ok": False, "error": str(e)}
    return results


def run_criterio7(executor, out_dir: Path, routes=("L0", "L219", "L325")) -> dict:
    """Por rota: canal 1 (`probe`, do CLIENTE contra a porta 443 ja
    aberta do servidor) + canal 2 (`pcap`, reaproveita o pcap
    dedicado que `_launch_gateway`/`dedicated_capture` JA escreve em
    `/tmp/criterio1_<perfil>_<rota>.pcap` no servidor -- nenhuma
    captura nova) -- `combine` acumula os dois num unico
    `criterio7_rtt_por_rota.json`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "criterio7_rtt_por_rota.json"
    if out_path.exists():
        out_path.unlink()
    result = {}
    for route in routes:
        client_ip = executor._client_ip(route)
        server_ip = executor._server_ip()
        gw_ip = executor._server_gateway_ip(route)

        probe_proc = cli.run_ssh(
            client_ip,
            f"cd {_REMOTE_PRODUCERS_DIR} && python3 criterio7_rtt.py probe --host {gw_ip} --port 443 --n 20",
            key_path=executor.key_path,
        )
        if probe_proc.returncode != 0:
            raise RuntimeError(f"run_criterio7({route}): canal probe falhou: {cli.redact(probe_proc.stderr)}")
        probe = json.loads(probe_proc.stdout)

        # Qualquer perfil prova o canal (SYN/SYN-ACK nunca depende de
        # perfil criptografico) -- usa o primeiro que `run_pilot`
        # escreveu de verdade (ordem de PROFILES, nunca suposto).
        pcap_path = None
        for profile in ("classico", "pqc", "hibrido-v8", "hibrido-and"):
            candidate = f"/tmp/criterio1_{profile}_{route}.pcap"
            check = cli.run_ssh(server_ip, f"test -f {candidate} && echo FOUND", key_path=executor.key_path)
            if "FOUND" in (check.stdout or ""):
                pcap_path = candidate
                break
        if pcap_path is None:
            raise RuntimeError(f"run_criterio7({route}): nenhum pcap dedicado encontrado em /tmp no servidor")

        pcap_proc = cli.run_ssh(
            server_ip,
            f"cd {_REMOTE_PRODUCERS_DIR} && python3 criterio7_rtt.py pcap --pcap {pcap_path} --port 443",
            key_path=executor.key_path,
        )
        if pcap_proc.returncode != 0:
            raise RuntimeError(f"run_criterio7({route}): canal pcap falhou: {cli.redact(pcap_proc.stderr)}")
        pcap = json.loads(pcap_proc.stdout)

        result[route] = {
            "rtt_ms_probe": probe["rtt_ms_probe"], "n_samples_probe": probe["n_samples_probe"],
            "rtt_ms_pcap": pcap["rtt_ms_pcap"],
        }
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


# Pedido do Luciano (item 0, regra fail-closed nova): nomes reais dos
# 3 containers de negocio (docker-compose `insurance-server-lambdas`,
# Decisao 83) -- o gateway e sempre `executor.gateway_container`
# (configuravel), nunca hardcoded junto com estes.
_BACKEND_CONTAINERS = ("insurance-server-lambdas-auth-1", "insurance-server-lambdas-mongo_seed-1",
                       "insurance-server-lambdas-mockapi-1")


def collect_full_logs(executor, out_dir: Path) -> dict:
    """Pedido do Luciano (item 0, regra fail-closed nova: teardown so
    depois dos brutos coletados e VERIFICADOS por sha256 -- "12 pcaps,
    12 keylogs, flights extraidos, logs de TODAS as instancias e dos
    conteineres"). Antes desta Emenda, SO uma JANELA de tempo do log
    do gateway (`_gateway_logs`, usada dentro de uma execucao
    especifica) era preservada -- `auth`/`mongo_seed`/`mockapi` NUNCA
    tinham log nenhum guardado, e o proprio gateway so tinha trechos,
    nunca o log CHEIO da sessao inteira. Escreve dentro do MESMO
    `out_dir` que `collect_artifacts.py` ja hasheia por completo (`find
    . -type f`) -- vira evidencia bruta coberta pelo manifesto sha256
    existente, por construcao, nunca um segundo sistema de verificacao
    paralelo.

    Generalizacao pra N servidores (pedido do Luciano): piloto
    (`executor.route_server is None`) continua 1 servidor so, nomes de
    arquivo SEM sufixo -- identico a antes. Campanha oficial (N
    servidores): um conjunto de logs POR servidor, nome prefixado pelo
    id do servidor (nunca colide entre eles)."""
    out_dir = Path(out_dir)
    logs_dir = out_dir / "full_container_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    if getattr(executor, "route_server", None) is None:
        server_ips_by_label = {"": executor._server_ip()}
    else:
        server_ips_by_label = {f"{server_id}_": ip["public_ip"] for server_id, ip in executor.inventory["servers"].items()}

    written = {}
    for label, server_ip in server_ips_by_label.items():
        for container in (executor.gateway_container,) + _BACKEND_CONTAINERS:
            proc = cli.run_ssh(server_ip, f"docker logs -t {container} 2>&1", key_path=executor.key_path)
            key = f"{label}{container}"
            (logs_dir / f"{key}.log").write_text(proc.stdout or "", encoding="utf-8")
            written[key] = {"bytes": len(proc.stdout or ""), "rc": proc.returncode, "server_ip": server_ip}

    # Diagnostico leve de cada instancia (servidor(es) + clientes da
    # fleet) -- best-effort, NUNCA fail-closed (nenhum achado real
    # ate agora dependeu disto; registrado so pela completude literal
    # do pedido, "logs de todas as instancias"). `dmesg` sem
    # permissao/ausente escreve uma nota explicita, nunca quebra a
    # coleta dos containers (que SAO fail-closed, ver acima).
    instance_ips = {f"server_{label.rstrip('_') or 'unico'}": ip for label, ip in server_ips_by_label.items()}
    instance_ips.update({f"client_{route}": executor._client_ip(route) for route in executor.inventory.get("clients", {})})
    for name, ip in instance_ips.items():
        try:
            proc = cli.run_ssh(ip, "dmesg 2>&1 | tail -n 200 || echo 'dmesg indisponivel'", key_path=executor.key_path)
            (logs_dir / f"instancia_{name}_dmesg.log").write_text(proc.stdout or "", encoding="utf-8")
        except Exception as e:  # nunca fail-closed -- so diagnostico
            (logs_dir / f"instancia_{name}_dmesg.log").write_text(f"indisponivel: {e}\n", encoding="utf-8")

    return {"containers": written, "instances": list(instance_ips)}


def build_criterio3(collected_dir: Path, out_dir: Path) -> dict:
    """Adapter: reaproveita o PROPRIO avaliador (`evaluate_criteria.
    criterion_4_counts`, nunca reimplementado) pra obter o `ok` por
    execucao -- cada linha ja compara contagens HTTP/mTLS reais
    contra o esperado; filtra pra `route == "L325"` e escreve no
    formato que `criterion_3_distant_route` espera."""
    combined_log = (collected_dir / "piloto_combined.log").read_text(encoding="utf-8", errors="replace")
    execucoes = json.loads((collected_dir / "piloto_calls.json").read_text(encoding="utf-8"))
    c4 = ec.criterion_4_counts(execucoes, combined_log)
    execucoes_l325 = [
        {"profile": r["profile"], "route": "L325", "ok": r["ok"]}
        for r in c4["rows"] if r["route"] == "L325"
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "criterio3_l325_execucoes.json"
    result = {"execucoes": execucoes_l325}
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def run_all(executor, collected_dir: Path, out_dir: Path) -> dict:
    """Roda os 3, na ordem -- criterio3 nunca depende de rede (so le
    dados ja coletados), roda primeiro; 2/7 precisam da fleet viva.
    `collect_full_logs` (item 0, regra fail-closed nova) roda por
    ULTIMO, DEPOIS de 2/7 -- precisa da fleet AINDA viva (SSH), mas so
    faz sentido depois que os criterios dedicados ja rodaram (senao
    perderia os proprios logs deles)."""
    report = {"criterio3": build_criterio3(collected_dir, out_dir)}
    report["criterio2"] = run_criterio2(executor, out_dir)
    report["criterio7"] = run_criterio7(executor, out_dir)
    report["full_logs"] = collect_full_logs(executor, out_dir)
    return report


def main():
    """Roda DO CONTROLE (mesma convencao de orchestrator.py -- so o
    controle alcanca servidor/clientes direto), DEPOIS que `run_pilot`
    ja terminou, contra o MESMO diretorio que `--out` ja escreveu
    (`piloto_combined.log`/`piloto_calls.json` ja estao la -- nunca
    precisa de `collect_artifacts.py` rodar antes pra criterio 3).
    Escreve os 3 arquivos novos NO MESMO diretorio -- um unico pull
    depois (`collect_artifacts.py`) traz tudo de uma vez."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory-json", required=True)
    ap.add_argument("--ssh-key", required=True)
    ap.add_argument("--dir", required=True, help="o MESMO --out que run_pilot/run_smoke_gate ja usou")
    args = ap.parse_args()

    inventory = json.load(open(args.inventory_json, encoding="utf-8"))
    executor = orch.SSHExecutor(inventory, key_path=args.ssh_key)
    report = run_all(executor, Path(args.dir), Path(args.dir))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

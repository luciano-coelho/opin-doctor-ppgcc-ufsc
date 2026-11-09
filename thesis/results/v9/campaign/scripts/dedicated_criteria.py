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


def run_criterio2(executor, out_dir: Path, route: str = CRITERIO2_PROBE_ROUTE) -> dict:
    """Sobe `criterio2_probe.py` no SERVIDOR (background), dispara UMA
    conexao de teste do CLIENTE da `route` dada (`/dev/tcp` puro,
    mesmo mecanismo que `_tcp_preflight` ja usa -- nunca `nc`, nem
    sempre instalado), espera o arquivo aparecer, traz o JSON de
    volta pro `out_dir`."""
    server_ip = executor._server_ip()
    iface_proc = cli.run_ssh(server_ip, "ip -o -4 route show to default | awk '{print $5}' | head -1",
                              key_path=executor.key_path)
    iface = (iface_proc.stdout or "").strip()
    if not iface:
        raise RuntimeError("run_criterio2: nao consegui descobrir a interface primaria do servidor")

    rm_proc = cli.run_ssh(server_ip, f"rm -f {_REMOTE_CRITERIO2_OUT} /tmp/criterio2_probe.log", key_path=executor.key_path)
    launch_cmd = (
        f"cd {_REMOTE_PRODUCERS_DIR} && "
        f"nohup python3 criterio2_probe.py --listen-port {CRITERIO2_LISTEN_PORT} --iface {iface} "
        f"--route {route} --instance-type m7i-flex.large --profile classico "
        f"--out {_REMOTE_CRITERIO2_OUT} > /tmp/criterio2_probe.log 2>&1 &"
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
            start_proc = cli.run_ssh(server_ip, launch_cmd, key_path=executor.key_path)
            break
        except subprocess.TimeoutExpired:
            if attempt == 2:
                raise RuntimeError(
                    "run_criterio2: a sessao SSH que sobe o probe nunca retornou em 3 tentativas "
                    "(timeout, provavel throttling transitorio do servidor logo apos o Passo 11)"
                )
            time.sleep(15)
    if start_proc.returncode != 0:
        raise RuntimeError(f"run_criterio2: falhou subindo o probe no servidor: {cli.redact(start_proc.stderr)}")
    time.sleep(2)  # da tempo do probe abrir a porta e comecar o tcpdump antes do cliente discar

    gw_ip = executor._server_gateway_ip(route)
    client_ip = executor._client_ip(route)
    connect_proc = cli.run_ssh(
        client_ip,
        f"timeout 20 bash -c 'cat < /dev/tcp/{gw_ip}/{CRITERIO2_LISTEN_PORT} > /dev/null'",
        key_path=executor.key_path, connect_timeout=30,
    )
    if connect_proc.returncode != 0:
        raise RuntimeError(f"run_criterio2: conexao de teste do cliente falhou: {cli.redact(connect_proc.stderr)}")

    for _ in range(10):
        check = cli.run_ssh(server_ip, f"test -f {_REMOTE_CRITERIO2_OUT} && echo FOUND", key_path=executor.key_path)
        if "FOUND" in (check.stdout or ""):
            break
        time.sleep(1)
    else:
        log_proc = cli.run_ssh(server_ip, "cat /tmp/criterio2_probe.log 2>/dev/null", key_path=executor.key_path)
        raise RuntimeError(
            f"run_criterio2: {_REMOTE_CRITERIO2_OUT} nunca apareceu no servidor -- "
            f"log do probe: {cli.redact(log_proc.stdout)}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    local_path = out_dir / "criterio2_initcwnd.json"
    scp_proc = cli.run_scp(f"ec2-user@{server_ip}:{_REMOTE_CRITERIO2_OUT}", str(local_path), key_path=executor.key_path)
    if scp_proc.returncode != 0:
        raise RuntimeError(f"run_criterio2: scp do resultado falhou: {cli.redact(scp_proc.stderr)}")
    return json.loads(local_path.read_text(encoding="utf-8"))


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
    dados ja coletados), roda primeiro; 2/7 precisam da fleet viva."""
    report = {"criterio3": build_criterio3(collected_dir, out_dir)}
    report["criterio2"] = run_criterio2(executor, out_dir)
    report["criterio7"] = run_criterio7(executor, out_dir)
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

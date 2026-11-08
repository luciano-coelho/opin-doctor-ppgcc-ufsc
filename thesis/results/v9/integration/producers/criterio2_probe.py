#!/usr/bin/env python3
"""
v9, piloto, criterio 2 (initcwnd real) -- produtor de dados.

Decisao 34/37/40: o handshake TLS normal nunca satura o cwnd (o
primeiro voo do servidor, 1,6-12KB, e menor que 10xMSS); o metodo
real precisa de um teste DEDICADO, numa conexao NOVA, mandando >=64KB.

Ordem dos eventos, exatamente como pedido (item C.9 da revisao
independente): o snapshot de `ss -ti` e tirado LOGO DEPOIS do
accept(), ANTES de escrever qualquer byte -- depois que a escrita
comeca, o cwnd ja pode ter crescido pelo slow-start, e o snapshot
deixaria de refletir o initcwnd puro.

1. Inicia `tcpdump -s 0` na interface dada (bytes de verdade, sem
   truncar -- precisa ver o handshake TCP completo e os ACKs reais).
2. Aceita a conexao de teste.
3. Tira o snapshot de `ss -ti` IMEDIATAMENTE -- antes do primeiro
   `send()`.
4. Manda >=64KB.
5. Para o tcpdump, extrai via `tshark`: o MSS das opcoes do SYN e os
   bytes que o SERVIDOR mandou antes do primeiro ACK do cliente que
   reconhece esses bytes.
6. Registra `ethtool -k <iface>` (tso/gso/gro) -- sempre, mesmo que
   nao decida o resultado (Decisao 37).
7. Escreve o JSON no formato que `evaluate_criteria.py`'s
   `criterion_2_initcwnd` espera.

Uso:
  python criterio2_probe.py --listen-port 9999 --iface eth0 \
    --route L219 --instance-type m7i-flex.large --profile classico \
    --out criterio2_initcwnd.json

Limite estrutural, registrado honestamente (nao escondido): em
loopback local, o MSS e grande o bastante pra nunca segmentar de
verdade -- este script PODE ser testado localmente (mecanica
correta, JSON valido), mas o NUMERO de segmentos resultante so e
significativo contra uma rota real do piloto, com RTT > 0.
"""
import argparse
import json
import re
import socket
import subprocess
import sys
import time

PAYLOAD_BYTES = 70 * 1024  # > 64KB exigido (INITCWND_MIN_BYTES_SENT)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def start_tcpdump(iface, pcap_path, port):
    proc = subprocess.Popen(
        ["tcpdump", "-i", iface, "-s", "0", "-w", pcap_path, f"tcp port {port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)  # da tempo do tcpdump abrir a interface antes do accept
    return proc


def stop_tcpdump(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def ss_ti_snapshot(port) -> dict:
    """Le `ss -ti` AGORA (sem esperar nada) e extrai o campo `cwnd`
    da conexao estabelecida na porta dada -- chamado imediatamente
    apos accept(), antes de qualquer send()."""
    out = run(["ss", "-ti", f"dport = :{port}", "or", f"sport = :{port}"]).stdout
    m = re.search(r"cwnd:(\d+)", out)
    return {"raw": out.strip(), "cwnd": int(m.group(1)) if m else None}


def ethtool_offloads(iface) -> dict:
    out = run(["ethtool", "-k", iface]).stdout
    offloads = {}
    for key in ("tcp-segmentation-offload", "generic-segmentation-offload", "generic-receive-offload"):
        m = re.search(rf"^{re.escape(key)}:\s*(on|off)", out, re.M)
        offloads[key] = m.group(1) if m else "desconhecido"
    return {
        "tso": offloads["tcp-segmentation-offload"],
        "gso": offloads["generic-segmentation-offload"],
        "gro": offloads["generic-receive-offload"],
    }


def _tshark_argv(pcap_path):
    """Decisao 85 (pedido do Luciano): o servidor real nunca tem
    `tshark` no PATH do host (so dentro de `mockopin-v9-measure`, a
    MESMA imagem pinada que `dedicated_capture`/criterio 1 ja usa) --
    roda `tshark` dentro dela, nunca bare no host, nunca reconstroi
    nem muda a imagem."""
    return ["docker", "run", "--rm", "-v", "/tmp:/tmp:ro", "--entrypoint", "tshark",
            "mockopin-v9-measure", "-r", pcap_path]


def extract_mss_and_bytes_before_ack(pcap_path, port) -> tuple[int | None, int | None]:
    """tshark: MSS das opcoes do SYN do SERVIDOR (quem aceita a
    conexao, nao quem conecta); bytes que o SERVIDOR mandou (seq
    final - seq inicial do primeiro segmento de dados) ANTES do
    primeiro segmento vindo do CLIENTE com flag ACK que reconhece
    esses bytes (ack_num > seq inicial dos dados do servidor)."""
    # MSS anunciado pelo SERVIDOR no seu SYN-ACK (tcp.flags.syn==1 &&
    # tcp.flags.ack==1, origem = porta do servidor).
    mss_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.flags.syn==1 && tcp.flags.ack==1",
                                    "-T", "fields", "-e", "tcp.options.mss_val"],
    ).stdout.strip().splitlines()
    mss = int(mss_out[0]) if mss_out and mss_out[0] else None

    # Todos os segmentos de DADOS que o servidor mandou (porta de
    # origem = porta do servidor, len>0), em ordem.
    data_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.len>0",
                                    "-T", "fields", "-e", "tcp.seq", "-e", "tcp.len"],
    ).stdout.strip().splitlines()
    if not data_out:
        return mss, None
    first_seq = int(data_out[0].split("\t")[0])
    server_bytes_by_seq_end = [int(line.split("\t")[0]) + int(line.split("\t")[1]) for line in data_out if line]

    # Primeiro ACK do CLIENTE (porta de destino = porta do servidor,
    # flag ACK, sem SYN) e o numero de ACK que ele carrega.
    ack_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.dstport=={port} && tcp.flags.ack==1 && tcp.flags.syn==0",
                                    "-T", "fields", "-e", "tcp.ack"],
    ).stdout.strip().splitlines()
    if not ack_out:
        return mss, None
    first_client_ack = int(ack_out[0])

    # Bytes do servidor cujo seq_end <= o que esse primeiro ACK ja
    # reconhece foram mandados ANTES desse ACK chegar -- soma deles,
    # menos o seq inicial, da os bytes enviados antes do primeiro ACK.
    sent_before_ack = sum(1 for end in server_bytes_by_seq_end if end <= first_client_ack)
    bytes_before_ack = None
    if sent_before_ack > 0:
        bytes_before_ack = server_bytes_by_seq_end[sent_before_ack - 1] - first_seq
    return mss, bytes_before_ack


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen-port", type=int, required=True)
    ap.add_argument("--iface", required=True)
    ap.add_argument("--route", required=True)
    ap.add_argument("--instance-type", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--pcap", default="/tmp/criterio2.pcap")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tcpdump_proc = start_tcpdump(args.iface, args.pcap, args.listen_port)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", args.listen_port))
    srv.listen(1)
    print(f"aguardando conexao de teste na porta {args.listen_port}...", file=sys.stderr)
    conn, addr = srv.accept()

    # Snapshot ANTES de mandar qualquer byte -- ver docstring do
    # modulo pra justificativa da ordem.
    snapshot = ss_ti_snapshot(args.listen_port)

    sent = conn.sendall(b"\x00" * PAYLOAD_BYTES)
    conn.close()
    srv.close()
    time.sleep(1)  # da tempo do ultimo ACK chegar antes de parar a captura
    stop_tcpdump(tcpdump_proc)

    offloads = ethtool_offloads(args.iface)
    mss, bytes_before_ack = extract_mss_and_bytes_before_ack(args.pcap, args.listen_port)

    out = {
        "route": args.route,
        "instance_type": args.instance_type,
        "profile": args.profile,
        "bytes_sent_total": PAYLOAD_BYTES,
        "bytes_sent_before_first_client_ack": bytes_before_ack,
        "mss_bytes": mss,
        "ss_ti_cwnd": snapshot["cwnd"],
        "ss_ti_raw_snapshot": snapshot["raw"],
        "offloads": offloads,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

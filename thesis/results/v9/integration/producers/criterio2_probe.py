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
5. Para o tcpdump, extrai via `tshark`: o MSS ANUNCIADO no SYN-ACK
   (so diagnostico -- ver Emenda abaixo) e os bytes que o SERVIDOR
   mandou antes do primeiro ACK do cliente que reconhece esses bytes.
6. Registra `ethtool -k <iface>` (tso/gso/gro) -- sempre, mesmo que
   nao decida o resultado (Decisao 37).
7. Escreve o JSON no formato que `evaluate_criteria.py`'s
   `criterion_2_initcwnd` espera.

Emenda MSS-efetivo (pedido do Luciano, apos a Decisao 95 achar que
`mss_bytes` vinha do MSS ANUNCIADO no SYN-ACK do servidor -- a
capacidade LOCAL da NIC/jumbo frame, ex. 8961B, nunca o MSS que de
fato acaba sendo usado no caminho real entre regioes, reduzido por
PMTU discovery): `mss_bytes` agora vem da CONCORDANCIA entre dois
canais independentes do MSS EFETIVO -- (1) `ss -ti`, campo `mss`
reportado pelo proprio kernel; (2) o MAIOR payload real (`tcp.len`)
que o servidor de fato colocou no fio nesta conexao, direto do pcap.
Se os dois discordarem, `mss_bytes` sai `None` e o criterio FALHA por
essa razao especificamente (nunca usa um dos dois canais "por
default"). O MSS anunciado no SYN-ACK continua registrado
(`mss_synack_announced_bytes`), so como diagnostico/evidencia do
porque o metodo anterior estava errado -- nunca entra no calculo.

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
# Decisao 94 (achado real, ao vivo, na primeira execucao real deste
# script, Passo 11.5): o SERVIDOR roda Python 3.9 (mesma razao da
# Decisao 65 em orchestrator.py) -- `int | None` (PEP 604) so existe
# em runtime a partir do 3.10 sem isto. Adia a avaliacao de anotacao
# pra string, zero mudanca de comportamento (nada aqui inspeciona
# anotacao em runtime).
from __future__ import annotations

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
    # Decisao 94 (achado real, ao vivo, Passo 11.5): sem `sudo`,
    # `tcpdump` falha com "You don't have permission to perform this
    # capture on that device (CAP_NET_RAW may be required)" -- SILENCIOSO
    # (Popen nunca verifica o retorno), nunca escreve pcap nenhum, e
    # TODO o resto do script segue adiante com dados ausentes (mss_
    # bytes/bytes_before_ack = None) em vez de falhar alto. Mesma
    # correcao que `dedicated_capture`/`_launch_gateway`
    # (orchestrator.py) ja usam pro tcpdump real do criterio 1 --
    # nunca um privilegio novo, so o mesmo `sudo` sem senha que o
    # `ec2-user` real ja tem nesta AMI.
    proc = subprocess.Popen(
        ["sudo", "tcpdump", "-i", iface, "-s", "0", "-w", pcap_path, f"tcp port {port}"],
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
    """Le `ss -ti` AGORA (sem esperar nada) e extrai os campos `cwnd`
    e `mss` da conexao estabelecida na porta dada -- chamado
    imediatamente apos accept(), antes de qualquer send().

    Emenda MSS-efetivo (pedido do Luciano, apos a Decisao 95 achar que
    `mss_bytes` vinha do SYN-ACK -- capacidade LOCAL de jumbo frame da
    NIC, nunca o MSS EFETIVO do caminho real): o campo `mss` que o
    PROPRIO KERNEL reporta aqui e o MSS que ele de fato vai usar pra
    mandar dado por essa conexao (ja reduzido por PMTU/rota conhecida,
    quando aplicavel) -- vira um dos dois canais do MSS efetivo (ver
    `extract_mss_and_bytes_before_ack`, canal 2 = maior payload real
    observado no pcap)."""
    out = run(["ss", "-ti", f"dport = :{port}", "or", f"sport = :{port}"]).stdout
    cwnd_m = re.search(r"cwnd:(\d+)", out)
    mss_m = re.search(r"mss:(\d+)", out)
    return {"raw": out.strip(), "cwnd": int(cwnd_m.group(1)) if cwnd_m else None,
            "mss": int(mss_m.group(1)) if mss_m else None}


def ethtool_offloads(iface) -> dict:
    """Decisao 37: registrado SEMPRE, mas nunca decide o resultado do
    criterio 2 (so diagnostico de TSO/GSO/GRO). Decisao 94 (achado
    real, ao vivo, Passo 11.5): a AMI real (Amazon Linux 2023) nao tem
    `ethtool` instalado -- um `FileNotFoundError` aqui derrubava o
    script INTEIRO antes de sequer escrever o resultado do criterio 2,
    exatamente a classe de erro que a Decisao 37 ja disse que este
    campo nunca deveria causar. Fail-closed-pro-diagnostico-em-si
    (nunca None silencioso): "indisponivel" explicito, nunca inventado."""
    try:
        out = run(["ethtool", "-k", iface]).stdout
    except FileNotFoundError:
        return {"tso": "indisponivel", "gso": "indisponivel", "gro": "indisponivel"}
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


def extract_mss_and_bytes_before_ack(pcap_path, port) -> tuple[int | None, int | None, int | None]:
    """tshark: (1) MSS ANUNCIADO pelo SERVIDOR no seu SYN-ACK --
    diagnostico, NUNCA usado no calculo (Emenda MSS-efetivo, ver
    docstring do modulo: e so a capacidade LOCAL da NIC, nunca o MSS
    que de fato vai ser usado no caminho real); (2) o MAIOR payload
    real (`tcp.len`) entre os segmentos de dados que o SERVIDOR
    mandou -- canal 2 do MSS EFETIVO (cross-check obrigatorio contra
    `ss -ti`, feito no chamador); (3) bytes que o SERVIDOR mandou (seq
    final - seq inicial do primeiro segmento de dados) ANTES do
    primeiro segmento vindo do CLIENTE com flag ACK que reconhece
    esses bytes (ack_num > seq inicial dos dados do servidor)."""
    # MSS anunciado pelo SERVIDOR no seu SYN-ACK (tcp.flags.syn==1 &&
    # tcp.flags.ack==1, origem = porta do servidor) -- SO diagnostico.
    mss_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.flags.syn==1 && tcp.flags.ack==1",
                                    "-T", "fields", "-e", "tcp.options.mss_val"],
    ).stdout.strip().splitlines()
    mss_announced = int(mss_out[0]) if mss_out and mss_out[0] else None

    # Todos os segmentos de DADOS que o servidor mandou (porta de
    # origem = porta do servidor, len>0), em ordem.
    data_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.len>0",
                                    "-T", "fields", "-e", "tcp.seq", "-e", "tcp.len"],
    ).stdout.strip().splitlines()
    if not data_out:
        return mss_announced, None, None
    first_seq = int(data_out[0].split("\t")[0])
    server_bytes_by_seq_end = [int(line.split("\t")[0]) + int(line.split("\t")[1]) for line in data_out if line]
    # Canal 2 do MSS EFETIVO: o MAIOR payload real que o servidor de
    # fato colocou no fio nesta conexao -- se TSO/GSO estiver ligado
    # isso pode inflar pra um "superpacote" (registrado em `offloads`,
    # Decisao 37), o que faz esse canal DISCORDAR de `ss -ti` de
    # proposito (nunca concordar por acidente com um numero inflado).
    mss_pcap_max_payload = max(int(line.split("\t")[1]) for line in data_out if line)

    # Primeiro ACK do CLIENTE (porta de destino = porta do servidor,
    # flag ACK, sem SYN) e o numero de ACK que ele carrega.
    #
    # Decisao 94 (achado real, ao vivo, Passo 11.5, confirmado por
    # conteudo contra o pcap real): o PRIMEIRO ACK do cliente apos o
    # handshake e o que FECHA o 3-way handshake (ack_num == first_seq,
    # reconhece so o SYN, nunca nenhum byte de dado -- o servidor
    # normalmente nem comecou a mandar nada ainda) -- usar ESSE
    # (`ack_out[0]`, o bug original) faz `sent_before_ack` ser SEMPRE
    # 0 por construcao, nunca refletindo quantos bytes o servidor
    # realmente mandou antes do primeiro ACK relevante. A docstring
    # desta funcao ja dizia o certo ("ack_num > seq inicial dos dados
    # do servidor") -- o codigo nunca implementava essa condicao.
    # Corrigido: pula qualquer ACK que reconheca <= first_seq (so o
    # handshake), usa o primeiro que de fato reconhece algum byte de
    # dado real.
    ack_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.dstport=={port} && tcp.flags.ack==1 && tcp.flags.syn==0",
                                    "-T", "fields", "-e", "tcp.ack"],
    ).stdout.strip().splitlines()
    first_client_ack = None
    for line in ack_out:
        if not line:
            continue
        candidate = int(line)
        if candidate > first_seq:
            first_client_ack = candidate
            break
    if first_client_ack is None:
        return mss_announced, mss_pcap_max_payload, None

    # Bytes do servidor cujo seq_end <= o que esse primeiro ACK ja
    # reconhece foram mandados ANTES desse ACK chegar -- soma deles,
    # menos o seq inicial, da os bytes enviados antes do primeiro ACK.
    sent_before_ack = sum(1 for end in server_bytes_by_seq_end if end <= first_client_ack)
    bytes_before_ack = None
    if sent_before_ack > 0:
        bytes_before_ack = server_bytes_by_seq_end[sent_before_ack - 1] - first_seq
    return mss_announced, mss_pcap_max_payload, bytes_before_ack


# Emenda MSS-efetivo: diferenca maxima aceitavel (bytes) entre os dois
# canais independentes do MSS efetivo (`ss -ti` e maior payload real
# do pcap) pra considera-los "concordando" -- 0B por padrao (os dois
# medem a MESMA grandeza do MESMO jeito, sem motivo pra divergir nem
# um byte, salvo TSO/GSO inflando o pcap -- ver comentario acima).
MSS_CHANNELS_MAX_DIFF_BYTES = 0


def effective_mss(ss_ti_mss, mss_pcap_max_payload) -> tuple[int | None, bool]:
    """Emenda MSS-efetivo (pedido do Luciano): os DOIS canais
    (`ss -ti` e maior payload real do pcap) tem que CONCORDAR -- senao
    FALHA, nunca usa um dos dois sozinho "por default". Devolve
    `(mss_bytes_efetivo_ou_None, concordam_bool)`."""
    if not isinstance(ss_ti_mss, int) or not isinstance(mss_pcap_max_payload, int):
        return None, False
    agree = abs(ss_ti_mss - mss_pcap_max_payload) <= MSS_CHANNELS_MAX_DIFF_BYTES
    return (ss_ti_mss if agree else None), agree


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
    mss_announced, mss_pcap_max_payload, bytes_before_ack = extract_mss_and_bytes_before_ack(args.pcap, args.listen_port)
    mss_bytes, mss_channels_agree = effective_mss(snapshot["mss"], mss_pcap_max_payload)

    out = {
        "route": args.route,
        "instance_type": args.instance_type,
        "profile": args.profile,
        "bytes_sent_total": PAYLOAD_BYTES,
        "bytes_sent_before_first_client_ack": bytes_before_ack,
        "mss_synack_announced_bytes": mss_announced,  # diagnostico, nunca usado no calculo (ver docstring do modulo)
        "mss_pcap_max_payload_bytes": mss_pcap_max_payload,
        "ss_ti_mss": snapshot["mss"],
        "mss_channels_agree": mss_channels_agree,
        "mss_bytes": mss_bytes,  # MSS EFETIVO -- None se os dois canais discordarem
        "ss_ti_cwnd": snapshot["cwnd"],
        "ss_ti_raw_snapshot": snapshot["raw"],
        "offloads": offloads,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

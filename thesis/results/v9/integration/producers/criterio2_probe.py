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

Emenda robustez-de-janela (pedido do Luciano, achado real contra a
AWS real -- Decisao 101 relatou `segments_computed=2,0` e atribuiu
(errado) a TCP pacing; investigacao ao vivo do pcap real provou que
NAO havia pacing nenhum -- os 10 segmentos do 1o voo saem com ~9us
de distancia um do outro, ~1000x mais rapido do que o `pacing_rate`
reportado exigiria): a causa real era `extract_mss_and_bytes_before_
ack` contar so os bytes cobertos pelo PRIMEIRO pacote de ACK que via
-- sob RTT real, o cliente manda VARIOS ACKs chegando num cluster bem
apertado (confirmado: 5 ACKs em ~60us um do outro), e o primeiro
deles so cobria 2 dos 10 segmentos REALMENTE mandados no 1o voo.
Corrigido: `bytes_sent_within_first_rtt_window` conta por TIMESTAMP
DE ENVIO (nunca por numero de ACK), dentro da janela `[tempo do 1o
segmento de dados, +1 RTT]` -- o RTT vem de uma medicao
INDEPENDENTE, na MESMA conexao (SYN-ACK saindo -> ACK do handshake
voltando, mesmo metodo da Emenda RTT-pcap do criterio 7, Decisao 97)
-- nunca do comportamento dos ACKs de DADOS, que e exatamente o que
causava o bug original.

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


def extract_mss(pcap_path, port) -> tuple[int | None, int | None]:
    """tshark: (1) MSS ANUNCIADO pelo SERVIDOR no seu SYN-ACK --
    diagnostico, NUNCA usado no calculo (Emenda MSS-efetivo, ver
    docstring do modulo: e so a capacidade LOCAL da NIC, nunca o MSS
    que de fato vai ser usado no caminho real); (2) o MAIOR payload
    real (`tcp.len`) entre os segmentos de dados que o SERVIDOR
    mandou -- canal 2 do MSS EFETIVO (cross-check obrigatorio contra
    `ss -ti`, feito no chamador)."""
    mss_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.flags.syn==1 && tcp.flags.ack==1",
                                    "-T", "fields", "-e", "tcp.options.mss_val"],
    ).stdout.strip().splitlines()
    mss_announced = int(mss_out[0]) if mss_out and mss_out[0] else None

    data_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.len>0",
                                    "-T", "fields", "-e", "tcp.seq", "-e", "tcp.len"],
    ).stdout.strip().splitlines()
    if not data_out:
        return mss_announced, None
    # Canal 2 do MSS EFETIVO: o MAIOR payload real que o servidor de
    # fato colocou no fio nesta conexao -- se TSO/GSO estiver ligado
    # isso pode inflar pra um "superpacote" (registrado em `offloads`,
    # Decisao 37), o que faz esse canal DISCORDAR de `ss -ti` de
    # proposito (nunca concordar por acidente com um numero inflado).
    mss_pcap_max_payload = max(int(line.split("\t")[1]) for line in data_out if line)
    return mss_announced, mss_pcap_max_payload


def rtt_from_handshake_same_connection(pcap_path, port) -> float | None:
    """Emenda robustez-de-janela (pedido do Luciano, achado real:
    `extract_mss_and_bytes_before_ack` contava so os bytes cobertos
    pelo PRIMEIRO pacote de ACK visto, mas sob RTT real o cliente
    manda VARIOS ACKs chegando em cluster bem apertado -- confirmado
    por conteudo contra o pcap real desta rodada: 5 ACKs em ~60us um
    do outro, o primeiro cobrindo so 2 dos 10 segmentos REALMENTE
    mandados no 1o voo, fazendo `segments_computed` sair 2,0 em vez
    de 10 -- NUNCA um achado de pacing, como a Decisao 101 relatou
    por engano: a distancia real entre os 10 segmentos do 1o voo foi
    ~9us, ~1000x mais rapido do que o `pacing_rate` reportado exigiria
    -- sem nenhuma assinatura de pacing nos pacotes).

    RTT real desta MESMA conexao, medido do MESMO jeito que a Emenda
    RTT-pcap do criterio 7 (Decisao 97) -- SYN-ACK do servidor SAINDO
    -> primeiro ACK do cliente fechando o handshake CHEGANDO de volta
    (ida+volta completas) -- nunca derivado do numero de ACK de
    dados, que e exatamente o que causava o bug."""
    synack_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.flags.syn==1 && tcp.flags.ack==1",
                                    "-T", "fields", "-e", "frame.time_epoch"],
    ).stdout.strip().splitlines()
    ack_in = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.dstport=={port} && tcp.flags.ack==1 && tcp.flags.syn==0",
                                    "-T", "fields", "-e", "frame.time_epoch"],
    ).stdout.strip().splitlines()
    if not synack_out or not synack_out[0] or not ack_in or not ack_in[0]:
        return None
    return float(ack_in[0]) - float(synack_out[0])


def extract_bytes_sent_within_rtt_window(pcap_path, port, rtt_s) -> int | None:
    """Conta bytes de dados do SERVIDOR por TIMESTAMP DE ENVIO, dentro
    da janela `[tempo do 1o segmento de dados, +rtt_s]` -- NUNCA
    derivado do numero de ACK (o bug original) nem do PRIMEIRO pacote
    de ACK visto (o bug que a Decisao 101 corrigiu so parcialmente --
    ainda discordava quando varios ACKs chegam em cluster). Robusto a
    ACKs em cluster e a ACK atrasado/perdido, porque nunca olha pros
    ACKs pra decidir QUANTO foi mandado -- so para decidir ATE QUANDO
    (a janela de `rtt_s`, medida independentemente pelo handshake,
    `rtt_from_handshake_same_connection`)."""
    if rtt_s is None:
        return None
    data_out = run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.len>0",
                                    "-T", "fields", "-e", "frame.time_epoch", "-e", "tcp.len"],
    ).stdout.strip().splitlines()
    rows = []
    for line in data_out:
        if not line:
            continue
        t_s, len_s = line.split("\t")
        rows.append((float(t_s), int(len_s)))
    if not rows:
        return None
    rows.sort(key=lambda r: r[0])
    t0 = rows[0][0]
    window_end = t0 + rtt_s
    return sum(length for t, length in rows if t <= window_end)


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
    mss_announced, mss_pcap_max_payload = extract_mss(args.pcap, args.listen_port)
    mss_bytes, mss_channels_agree = effective_mss(snapshot["mss"], mss_pcap_max_payload)
    rtt_s = rtt_from_handshake_same_connection(args.pcap, args.listen_port)
    bytes_in_window = extract_bytes_sent_within_rtt_window(args.pcap, args.listen_port, rtt_s)

    out = {
        "route": args.route,
        "instance_type": args.instance_type,
        "profile": args.profile,
        "bytes_sent_total": PAYLOAD_BYTES,
        "bytes_sent_within_first_rtt_window": bytes_in_window,
        "rtt_ms_used_for_window": round(rtt_s * 1000.0, 3) if rtt_s is not None else None,
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

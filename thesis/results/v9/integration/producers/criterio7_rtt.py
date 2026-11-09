#!/usr/bin/env python3
"""
v9, piloto, criterio 7 (sanidade de latencia por rota) -- produtor de
dados.

Decisao 35/38/40: o grupo de seguranca do piloto so abre 443/22 --
NUNCA ping. Metodo real, confirmado contra `v8/DECISIONS.md` (linha
8546, "Pre-flight TCP/443"): um probe de CONEXAO TCP na porta 443,
N amostras, mediana -- mais um SEGUNDO canal independente, extraido
de uma captura `tcpdump -s 0` real (zero porta ou conexao extra -- os
dados ja existem na captura dedicada do criterio 1/2).

Decisao [EMENDA RTT-PCAP] (pedido do Luciano, apos a Decisao 95 achar
que o canal pcap estava medindo tempo de PROCESSAMENTO do servidor,
nunca RTT de rede real): a captura dedicada roda SO no SERVIDOR -- o
intervalo entre o SYN do cliente CHEGANDO e o SYN-ACK do servidor
SAINDO e os DOIS eventos na MESMA interface, sem NENHUMA propagacao de
rede entre eles, so o tempo de processamento local do kernel/gateway
pra responder. A SEGUNDA metade do 3-way handshake (SYN-ACK do
servidor SAINDO -> ACK do cliente fechando o handshake CHEGANDO de
volta) cobre IDA (servidor->cliente) E VOLTA (cliente->servidor)
completas -- RTT real de verdade, na MESMA captura so-do-servidor, sem
nenhum ponto de captura novo nem regra de SG nova. Pareamento por
`tcp.stream` (nunca por ordem/indice de lista -- streams podem
intercalar sob rede real, Decisao 91) -- o Decisao 94 ja confirmou que
o primeiro ACK do cliente apos o SYN-ACK fecha o handshake (nunca
reconhece dado), exatamente o evento que fecha esta segunda metade.

Uso:
  python criterio7_rtt.py probe --host <ip> --port 443 --n 20
      -> so o canal 1 (conexao TCP), imprime {"rtt_ms_probe":...,"n_samples_probe":...}
  python criterio7_rtt.py pcap --pcap <arquivo> --port 443
      -> so o canal 2 (SYN-ACK saindo -> ACK fechando o handshake chegando), imprime {"rtt_ms_pcap":...}
  python criterio7_rtt.py combine --route L219 --probe-json <a> --pcap-json <b> --out criterio7_rtt_por_rota.json
      -> junta os dois canais de uma rota no formato final; chamar 3x (uma por rota) com --merge pra acumular
"""
import argparse
import json
import socket
import statistics
import subprocess
import time


def tcp_connect_probe(host: str, port: int, n: int) -> dict:
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            s.connect((host, port))
            samples.append((time.perf_counter() - start) * 1000.0)
        finally:
            s.close()
    return {"rtt_ms_probe": round(statistics.median(samples), 3), "n_samples_probe": len(samples),
            "samples_ms": [round(x, 3) for x in samples]}


def _tshark_argv(pcap_path: str) -> list[str]:
    """Decisao 85 (pedido do Luciano): o servidor real nunca tem
    `tshark` no PATH do host (so dentro de `mockopin-v9-measure`, a
    MESMA imagem pinada que `dedicated_capture`/criterio 1 ja usa) --
    roda `tshark` dentro dela, nunca bare no host, nunca reconstroi
    nem muda a imagem. `-v /tmp:/tmp:ro` porque todo pcap deste
    pipeline vive sob `/tmp` (mesmo caminho dentro/fora do container,
    nunca precisa traduzir)."""
    return ["docker", "run", "--rm", "-v", "/tmp:/tmp:ro", "--entrypoint", "tshark",
            "mockopin-v9-measure", "-r", pcap_path]


def rtt_from_synack_ack_times(pairs: list[tuple[float, float]]) -> dict:
    """Emenda RTT-pcap (pedido do Luciano): matematica pura, pareada
    por `tcp.stream` (lista de pares `(synack_out_time, ack_in_time)`,
    ja casados por stream em `pcap_synack_ack_rtt`) -- RTT real = ACK
    chegando de volta MENOS SYN-ACK saindo, nunca SYN-ACK saindo menos
    SYN chegando (isso seria so tempo de processamento local, ver
    docstring do modulo)."""
    rtts = [(ack - synack) * 1000.0 for synack, ack in pairs]
    if not rtts:
        return {"rtt_ms_pcap": None, "n_samples_pcap": 0}
    return {"rtt_ms_pcap": round(statistics.median(rtts), 3), "n_samples_pcap": len(rtts)}


def pcap_synack_ack_rtt(pcap_path: str, port: int) -> dict:
    """Emenda RTT-pcap (pedido do Luciano, apos a Decisao 95): o
    SYN-ACK que o SERVIDOR manda (srcport==port) e o PRIMEIRO ACK que
    o CLIENTE manda de VOLTA (dstport==port, flags.ack==1,
    flags.syn==0) no MESMO `tcp.stream` -- esse primeiro ACK fecha o
    3-way handshake (Decisao 94 ja confirmou, por conteudo real, que
    ele nunca reconhece nenhum byte de dado, so o SYN), exatamente o
    evento que fecha a segunda metade do round-trip (servidor->
    cliente->servidor). Pareado por STREAM, nunca por ordem/indice de
    lista -- sob rede real varios handshakes podem intercalar (Decisao
    91 ja confirmou isso pro criterio 1 na MESMA captura)."""
    synack_out = subprocess.run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.flags.syn==1 && tcp.flags.ack==1",
                                    "-T", "fields", "-e", "tcp.stream", "-e", "frame.time_epoch"],
        capture_output=True, text=True,
    ).stdout.strip().splitlines()
    ack_in = subprocess.run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.dstport=={port} && tcp.flags.ack==1 && tcp.flags.syn==0",
                                    "-T", "fields", "-e", "tcp.stream", "-e", "frame.time_epoch"],
        capture_output=True, text=True,
    ).stdout.strip().splitlines()
    return pair_synack_ack_by_stream(synack_out, ack_in)


def pair_synack_ack_by_stream(synack_lines: list[str], ack_lines: list[str]) -> dict:
    """Fatorado pra ser testavel sem tshark/docker reais: `synack_lines`/
    `ack_lines` sao linhas `"<stream>\\t<frame.time_epoch>"` (saida bruta
    do `-T fields -e tcp.stream -e frame.time_epoch`). Pra cada stream,
    casa o SYN-ACK do servidor com o PRIMEIRO ack de volta do cliente
    (tshark preserva ordem cronologica -- a primeira ocorrencia de um
    stream em `ack_lines` e a cronologicamente primeira)."""
    synack_by_stream: dict[str, float] = {}
    for line in synack_lines:
        if not line:
            continue
        stream, t = line.split("\t")
        synack_by_stream[stream] = float(t)

    first_ack_by_stream: dict[str, float] = {}
    for line in ack_lines:
        if not line:
            continue
        stream, t = line.split("\t")
        if stream not in first_ack_by_stream:
            first_ack_by_stream[stream] = float(t)

    pairs = [(synack_by_stream[s], first_ack_by_stream[s])
             for s in synack_by_stream if s in first_ack_by_stream]
    return rtt_from_synack_ack_times(pairs)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("probe")
    p1.add_argument("--host", required=True)
    p1.add_argument("--port", type=int, default=443)
    p1.add_argument("--n", type=int, default=20)

    p2 = sub.add_parser("pcap")
    p2.add_argument("--pcap", required=True)
    p2.add_argument("--port", type=int, default=443)

    p3 = sub.add_parser("combine")
    p3.add_argument("--route", required=True)
    p3.add_argument("--probe-json", required=True)
    p3.add_argument("--pcap-json", required=True)
    p3.add_argument("--out", required=True)

    args = ap.parse_args()

    if args.cmd == "probe":
        print(json.dumps(tcp_connect_probe(args.host, args.port, args.n), indent=2))
    elif args.cmd == "pcap":
        print(json.dumps(pcap_synack_ack_rtt(args.pcap, args.port), indent=2))
    elif args.cmd == "combine":
        probe = json.load(open(args.probe_json, encoding="utf-8"))
        pcap = json.load(open(args.pcap_json, encoding="utf-8"))
        try:
            existing = json.load(open(args.out, encoding="utf-8"))
        except FileNotFoundError:
            existing = {}
        existing[args.route] = {
            "rtt_ms_probe": probe["rtt_ms_probe"],
            "n_samples_probe": probe["n_samples_probe"],
            "rtt_ms_pcap": pcap["rtt_ms_pcap"],
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        print(json.dumps(existing, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
v9, piloto, criterio 7 (sanidade de latencia por rota) -- produtor de
dados.

Decisao 35/38/40: o grupo de seguranca do piloto so abre 443/22 --
NUNCA ping. Metodo real, confirmado contra `v8/DECISIONS.md` (linha
8546, "Pre-flight TCP/443"): um probe de CONEXAO TCP na porta 443,
N amostras, mediana -- mais um SEGUNDO canal independente, SYN-
>SYN-ACK extraido de uma captura `tcpdump -s 0` real (zero porta ou
conexao extra -- os dados ja existem na captura dedicada do
criterio 1/2).

Uso:
  python criterio7_rtt.py probe --host <ip> --port 443 --n 20
      -> so o canal 1 (conexao TCP), imprime {"rtt_ms_probe":...,"n_samples_probe":...}
  python criterio7_rtt.py pcap --pcap <arquivo> --port 443
      -> so o canal 2 (SYN->SYN-ACK), imprime {"rtt_ms_pcap":...}
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


def rtt_from_syn_synack_times(syn_times: list[float], synack_times: list[float]) -> dict:
    """Decisao 85: matematica pura, fatorada de `pcap_syn_synack_rtt`
    pra ser reusada tanto localmente (tshark bare, caso de teste/
    validacao) quanto remotamente (tshark via docker no servidor
    real, Decisao 85) -- MESMO calculo, nunca duplicado."""
    rtts = [(synack - syn) * 1000.0 for syn, synack in zip(syn_times, synack_times)]
    if not rtts:
        return {"rtt_ms_pcap": None, "n_samples_pcap": 0}
    return {"rtt_ms_pcap": round(statistics.median(rtts), 3), "n_samples_pcap": len(rtts)}


def pcap_syn_synack_rtt(pcap_path: str, port: int) -> dict:
    """SYN do cliente (dstport==port, flags.syn==1, flags.ack==0) e o
    SYN-ACK correspondente (srcport==port, flags.syn==1,
    flags.ack==1) -- mesmo metodo que a v8 real usa na analise pos-
    campanha (v8/DECISIONS.md, linha 9970-9971), direto de uma
    captura ja existente, sem nenhuma conexao nova."""
    syn_out = subprocess.run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.dstport=={port} && tcp.flags.syn==1 && tcp.flags.ack==0",
                                    "-T", "fields", "-e", "frame.time_epoch"],
        capture_output=True, text=True,
    ).stdout.strip().splitlines()
    synack_out = subprocess.run(
        _tshark_argv(pcap_path) + ["-Y", f"tcp.srcport=={port} && tcp.flags.syn==1 && tcp.flags.ack==1",
                                    "-T", "fields", "-e", "frame.time_epoch"],
        capture_output=True, text=True,
    ).stdout.strip().splitlines()
    return rtt_from_syn_synack_times([float(x) for x in syn_out], [float(x) for x in synack_out])


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
        print(json.dumps(pcap_syn_synack_rtt(args.pcap, args.port), indent=2))
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

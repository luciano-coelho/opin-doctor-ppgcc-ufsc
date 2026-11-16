#!/usr/bin/env python3
"""Degrau 2, Etapa 0, item 3: mede, a partir do host de CONTROLE, o
overhead real de rede/SSH/cold-start pra cada cliente usado na campanha
suplementar -- insumo real do item D2/D5 do PLANO_DEGRAU2.md (substitui
as aproximacoes externas de RTT(controle,cliente) usadas no Degrau 1).

ESCRITO na Etapa 0 (so leitura de codigo, nenhum comando AWS) -- NUNCA
executado contra a AWS nesta rodada. So roda na Etapa 1 (sub-etapa
separada, com autorizacao explicita e o usuario presente), DEPLOYADO e
executado NO PROPRIO host de controle (nunca do notebook do operador --
o RTT control->cliente so e real medido dali).

So dependencias da stdlib (socket/subprocess/time/statistics/json) --
nenhuma dependencia do pacote da campanha, pra poder ser copiado e
rodado isoladamente no host de controle sem precisar do ambiente
completo do orquestrador.

Tres medicoes por cliente, 30 repeticoes cada:
  1. TCP connect puro a porta 22 (RTT real controle<->cliente, sem
     protocolo SSH nenhum por cima -- mede so o handshake TCP).
  2. `ssh <host> true`, conexao SSH NOVA a cada vez (sem ControlMaster/
     ControlPersist -- mesmo padrao de cli.py:run_ssh, nunca reaproveita
     conexao, pra medir o overhead de handshake SSH completo isolado).
  3. `ssh <host> python3 -c 'import latency_automation, opin_flow'`
     (overhead de SSH completo + cold-start do interpretador + imports
     dos MESMOS modulos que campaign_client_runner.py usa -- isola esse
     custo do custo de rodar o fluxo real).

Nunca le nem imprime conteudo de chave privada -- so o CAMINHO da chave
(`key_path`) e passado pro `ssh -i`."""
import argparse
import json
import socket
import statistics as st
import subprocess
import time
from pathlib import Path

N_REPS = 30
TCP_CONNECT_TIMEOUT_S = 10
SSH_TIMEOUT_S = 20


def probe_tcp_connect_ms(host: str, port: int = 22) -> list[float]:
    """RTT real controle<->cliente: tempo de um connect() TCP novo a
    cada repeticao (handshake de 3 vias), nunca reaproveitando socket."""
    out = []
    for _ in range(N_REPS):
        t0 = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=TCP_CONNECT_TIMEOUT_S):
                pass
        except OSError as e:
            raise RuntimeError(f"TCP connect a {host}:{port} falhou: {e}") from None
        out.append((time.monotonic() - t0) * 1000.0)
    return out


def probe_ssh_true_ms(host: str, user: str, key_path: str, port: int = 22) -> list[float]:
    """Overhead de handshake SSH completo (conexao nova a cada vez,
    sem ControlMaster/ControlPersist -- mesmo padrao de cli.py)."""
    argv = [
        "ssh", "-p", str(port), "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", "-o", f"ConnectTimeout={SSH_TIMEOUT_S}",
        "-o", "BatchMode=yes", "-i", key_path, f"{user}@{host}", "true",
    ]
    out = []
    for _ in range(N_REPS):
        t0 = time.monotonic()
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=SSH_TIMEOUT_S + 10)
        if proc.returncode != 0:
            raise RuntimeError(f"ssh {host} true falhou (rc={proc.returncode}): {proc.stderr}")
        out.append((time.monotonic() - t0) * 1000.0)
    return out


def probe_ssh_python_coldstart_ms(host: str, user: str, key_path: str, port: int = 22) -> list[float]:
    """Overhead de SSH completo + cold-start do interpretador Python +
    import dos MESMOS modulos que campaign_client_runner.py usa --
    roda no diretorio real do checkout (~/thesis/scripts), mesma
    convencao de orchestrator.py's remote_cmd."""
    remote_cmd = "cd ~/thesis/scripts && python3 -c 'import latency_automation, opin_flow'"
    argv = [
        "ssh", "-p", str(port), "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null", "-o", f"ConnectTimeout={SSH_TIMEOUT_S}",
        "-o", "BatchMode=yes", "-i", key_path, f"{user}@{host}", remote_cmd,
    ]
    out = []
    for _ in range(N_REPS):
        t0 = time.monotonic()
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=SSH_TIMEOUT_S + 30)
        if proc.returncode != 0:
            raise RuntimeError(f"ssh {host} cold-start falhou (rc={proc.returncode}): {proc.stderr}")
        out.append((time.monotonic() - t0) * 1000.0)
    return out


def summarize(values_ms: list[float]) -> dict:
    return {
        "n": len(values_ms), "median_ms": st.median(values_ms), "mean_ms": st.mean(values_ms),
        "min_ms": min(values_ms), "max_ms": max(values_ms),
        "stdev_ms": st.stdev(values_ms) if len(values_ms) > 1 else 0.0,
        "values_ms": values_ms,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="JSON com lista de {label, host, user, key_path}")
    parser.add_argument("--out", required=True, help="Caminho do JSON de saida")
    args = parser.parse_args()

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    results = {}
    for entry in inventory:
        label, host, user, key_path = entry["label"], entry["host"], entry["user"], entry["key_path"]
        print(f"[{label}] TCP connect x{N_REPS}...")
        tcp_ms = probe_tcp_connect_ms(host)
        print(f"[{label}] ssh true (conexao nova) x{N_REPS}...")
        ssh_true_ms = probe_ssh_true_ms(host, user, key_path)
        print(f"[{label}] ssh + cold-start Python x{N_REPS}...")
        ssh_cold_ms = probe_ssh_python_coldstart_ms(host, user, key_path)
        results[label] = {
            "host_role_only": entry.get("role", "unknown"),
            "tcp_connect_ms": summarize(tcp_ms),
            "ssh_handshake_ms": summarize(ssh_true_ms),
            "ssh_plus_python_coldstart_ms": summarize(ssh_cold_ms),
        }
        print(f"[{label}] TCP mediana={summarize(tcp_ms)['median_ms']:.3f}ms, "
              f"SSH mediana={summarize(ssh_true_ms)['median_ms']:.3f}ms, "
              f"SSH+coldstart mediana={summarize(ssh_cold_ms)['median_ms']:.3f}ms")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Gravado: {args.out}")


if __name__ == "__main__":
    main()

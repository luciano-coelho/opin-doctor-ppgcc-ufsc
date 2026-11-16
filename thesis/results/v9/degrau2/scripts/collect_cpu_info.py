#!/usr/bin/env python3
"""Degrau 2, Etapa 0, item 3: coleta SOMENTE LEITURA de `lscpu` e do
modelo de CPU dos hosts usados nesta campanha suplementar -- preenche a
lacuna que o Degrau 1 (verificacao de hardware/ambiente) ja identificou
como nunca coletada (`/proc/cpuinfo`/`lscpu`/`mpstat` nunca existiam em
nenhum arquivo da campanha oficial).

ESCRITO na Etapa 0 -- NUNCA executado contra a AWS nesta rodada. So
roda na Etapa 1 (sub-etapa separada, autorizada, usuario presente), a
partir do host de controle, via SSH -- reusa `cli.run_ssh()` do proprio
projeto (nunca reimplementa SSH de forma diferente). Comandos rodados
em cada host, todos SOMENTE LEITURA, nenhum estado alterado:
  - `lscpu`
  - `cat /proc/cpuinfo | grep -m1 'model name'` (so a primeira linha,
    nunca o arquivo inteiro -- info publica de hardware, nunca segredo)
  - `nproc`
  - `uname -r` (versao de kernel, mesmo campo ja auditado no Degrau 1
    host_facts.md -- reconfirmado aqui, nao assumido igual)

Nunca le/imprime chave privada nem qualquer outro arquivo sensivel --
so os 4 comandos read-only acima."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "campaign" / "scripts"))
import cli  # noqa: E402 -- reusa cli.run_ssh(), nunca reimplementa SSH


READ_ONLY_COMMANDS = {
    "lscpu": "lscpu",
    "cpu_model_name": "grep -m1 'model name' /proc/cpuinfo || true",
    "nproc": "nproc",
    "kernel": "uname -r",
}


def collect_one_host(host: str, user: str, key_path: str) -> dict:
    out = {}
    for field, cmd in READ_ONLY_COMMANDS.items():
        proc = cli.run_ssh(host, cmd, user=user, key_path=key_path)
        if proc.returncode != 0:
            out[field] = {"error": proc.stderr.strip()}
        else:
            out[field] = proc.stdout.strip()
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, help="JSON com lista de {label, host, user, key_path, role}")
    parser.add_argument("--out", required=True, help="Caminho do JSON/Markdown de saida")
    args = parser.parse_args()

    inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    results = {}
    for entry in inventory:
        label = entry["label"]
        print(f"[{label}] coletando lscpu/cpuinfo/nproc/kernel (somente leitura)...")
        results[label] = {
            "role": entry.get("role", "unknown"),
            **collect_one_host(entry["host"], entry["user"], entry["key_path"]),
        }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Gravado: {args.out}")


if __name__ == "__main__":
    main()

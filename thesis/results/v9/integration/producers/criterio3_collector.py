#!/usr/bin/env python3
"""
v9, piloto, criterio 3 (zero erros na rota mais distante, L325) --
produtor de dados.

So agrega -- nao reimplementa nenhuma medicao. Le um diretorio com um
arquivo JSON por execucao real (`{"profile", "route", "ok"}`, o
MESMO formato que o orquestrador do piloto ja produz por execucao
pra qualquer rota) e monta `criterio3_l325_execucoes.json`, no
formato que `evaluate_criteria.py` espera -- so pras execucoes cuja
`route == "L325"`.

Uso:
  python criterio3_collector.py --execucoes-dir <dir com *.json por execucao> --out criterio3_l325_execucoes.json
"""
import argparse
import glob
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execucoes-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    execucoes = []
    for path in sorted(glob.glob(f"{args.execucoes_dir}/*.json")):
        entry = json.load(open(path, encoding="utf-8"))
        if entry.get("route") == "L325":
            execucoes.append({"profile": entry.get("profile"), "route": "L325", "ok": entry.get("ok")})

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"execucoes": execucoes}, f, indent=2, ensure_ascii=False)
    print(f"{len(execucoes)} execucoes de L325 escritas em {args.out}")


if __name__ == "__main__":
    main()

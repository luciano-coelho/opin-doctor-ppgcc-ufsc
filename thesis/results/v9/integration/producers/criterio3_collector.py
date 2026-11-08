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


def collect_l325_execucoes(execucoes_dir) -> dict:
    """Decisao 85: fatorado de `main()` pra ser reusado -- a MESMA
    agregacao, chamada tanto pela CLI (abaixo) quanto por `dedicated_
    criteria.py` (novo), que adapta `piloto_calls.json` (formato real
    do piloto) pra este formato por-execucao ANTES de chamar esta
    funcao -- nunca reimplementa a agregacao em si."""
    execucoes = []
    for path in sorted(glob.glob(f"{execucoes_dir}/*.json")):
        entry = json.load(open(path, encoding="utf-8"))
        if entry.get("route") == "L325":
            execucoes.append({"profile": entry.get("profile"), "route": "L325", "ok": entry.get("ok")})
    return {"execucoes": execucoes}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execucoes-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    result = collect_l325_execucoes(args.execucoes_dir)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"{len(result['execucoes'])} execucoes de L325 escritas em {args.out}")


if __name__ == "__main__":
    main()

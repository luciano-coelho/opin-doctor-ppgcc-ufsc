#!/usr/bin/env python3
"""Decisao 172 (pedido do Luciano, item 4): remove a chave privada da
campanha do host de controle, com confirmacao de que o arquivo sumiu.

NUNCA roda automaticamente em lugar nenhum do fluxo normal da campanha
-- entra no runbook de FIM de campanha, a ser executado SOMENTE por
ordem explicita do usuario e DEPOIS de os resultados estarem copiados
pra fora do controle (Passo 12/13 do PILOT_RUNBOOK.md). Este script
nao decide nada sobre QUANDO rodar -- so executa a remocao e confirma,
quando chamado.

Preferencia `shred` (sobrescreve o conteudo antes de apagar -- real
anti-forense em disco magnetico; em SSD/NVMe moderno a garantia e
mais fraca por wear-leveling, mas ainda assim estritamente melhor que
`rm` puro, nunca pior) -- se `shred` nao existir no host (ex. imagem
minima sem coreutils completos), cai pra `os.remove` (equivalente a
`rm`), registrando no resultado qual dos dois foi usado de verdade."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def cleanup_campaign_key(key_path: str) -> dict:
    p = Path(key_path)
    if not p.is_file():
        return {"removed": False, "reason": "not_found", "path": str(p)}

    method = None
    shred_bin = shutil.which("shred")
    if shred_bin:
        proc = subprocess.run([shred_bin, "-u", "-z", str(p)], capture_output=True, text=True)
        if proc.returncode == 0:
            method = "shred"
        else:
            # shred existe mas falhou (ex. filesystem sem suporte) --
            # nunca finge sucesso, cai pro rm explicito abaixo.
            method = None

    if method is None:
        try:
            p.unlink()
            method = "rm"
        except OSError as e:
            return {"removed": False, "reason": f"unlink_failed: {e}", "path": str(p)}

    still_there = p.exists()
    return {
        "removed": not still_there,
        "method": method,
        "path": str(p),
        "confirmed_gone": not still_there,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Remove a chave privada da campanha do host de controle (fim de campanha, so por ordem explicita).",
    )
    ap.add_argument("--key-path", required=True,
                     help="Caminho da chave privada da campanha no controle (ex. ~/.ssh/campaign_key).")
    args = ap.parse_args()
    result = cleanup_campaign_key(args.key_path)
    print(json.dumps(result, indent=2))
    return 0 if result["removed"] else 1


if __name__ == "__main__":
    sys.exit(main())

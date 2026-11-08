#!/usr/bin/env python3
"""v9, piloto: coleta com manifesto SHA-256 verificado do diretorio
UNICO que `orchestrator.py run_pilot`/`run_smoke_gate` realmente
produz (`piloto_combined.log`, `piloto_calls.json`,
`criterio6_execucoes.json`, `manifest.json`, `criterio1_capturas/`,
tudo FLAT -- Decisao 75, item 3: a versao anterior deste arquivo
presumia uma estrutura POR PERFIL que `run_pilot` nunca produziu --
achado real, nunca exercitado contra a saida de verdade). Mesma
garantia de sempre (equivalente reduzido ao `campaign_pull.sh` real
da v8): o manifesto e REGENERADO no controle, puxado junto com os
dados, e conferido de novo localmente -- uma transferencia parcial ou
corrompida e pega aqui, nunca so na hora de escrever a tese.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402


def regenerate_manifest_on_control(control_ip, key_path, remote_dir, remote_manifest_path):
    cmd = f"cd {remote_dir} && find . -type f -print0 | xargs -0 sha256sum > {remote_manifest_path}"
    proc = cli.run_ssh(control_ip, cmd, key_path=key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"gerar manifesto no controle falhou: {cli.redact(proc.stderr)}")
    return proc


def pull_dir(control_ip, key_path, remote_dir, remote_manifest_path, local_dest_dir: Path):
    local_dest_dir.mkdir(parents=True, exist_ok=True)
    proc = cli.run_scp(f"ec2-user@{control_ip}:{remote_dir}/.", str(local_dest_dir),
                        key_path=key_path, recursive=True)
    if proc.returncode != 0:
        raise RuntimeError(f"scp -r do diretorio falhou: {cli.redact(proc.stderr)}")
    proc = cli.run_scp(f"ec2-user@{control_ip}:{remote_manifest_path}",
                        str(local_dest_dir / "manifest.sha256"), key_path=key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"scp do manifesto falhou: {cli.redact(proc.stderr)}")


def verify_local_manifest(local_dest_dir: Path) -> list[str]:
    """Confere cada linha do manifesto (formato `sha256sum`: hash,
    2 espacos ou um `*` antes do caminho) contra o arquivo PULADO de
    verdade -- implementacao Python nativa (nao depende do binario
    `sha256sum -c` estar no PATH local, mesma correcao, mais
    portavel). Levanta RuntimeError com a lista de arquivos que nao
    bateram -- nunca aceita silenciosamente uma copia parcial."""
    manifest_path = local_dest_dir / "manifest.sha256"
    if not manifest_path.is_file():
        raise RuntimeError(f"manifesto nao encontrado apos o pull: {manifest_path}")
    mismatches = []
    checked = []
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        expected_hash, rel_path = line.split(None, 1)
        rel_path = rel_path.lstrip("*").strip()
        target = local_dest_dir / rel_path
        if not target.is_file():
            mismatches.append(f"{rel_path}: arquivo ausente apos o pull")
            continue
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            mismatches.append(f"{rel_path}: hash nao bate (esperado {expected_hash}, obtido {actual_hash})")
        else:
            checked.append(rel_path)
    if mismatches:
        raise RuntimeError("manifesto nao confere, nao confie nesta copia:\n" + "\n".join(mismatches))
    return checked


def collect_pilot_data(control_ip, key_path, remote_dir, local_dir: Path) -> dict:
    """Coleta TODO o diretorio de saida de `run_pilot`/`run_smoke_gate`
    (`--out` passado a `orchestrator.py` no controle) num UNICO passo
    -- nunca por perfil, a saida real nunca e dividida assim (Decisao
    75). `.pull-verified` SO depois da verificacao de hash passar
    (mesmo padrao que autoriza um teardown depois, ver Decisao 46/47)."""
    remote_manifest_path = f"{remote_dir}.sha256"
    regenerate_manifest_on_control(control_ip, key_path, remote_dir, remote_manifest_path)
    pull_dir(control_ip, key_path, remote_dir, remote_manifest_path, local_dir)
    checked = verify_local_manifest(local_dir)
    (local_dir / ".pull-verified").write_text(
        f"{len(checked)} arquivos verificados por sha256\n", encoding="utf-8")
    return {"files_verified": len(checked), "dest": str(local_dir)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-ip", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--remote-dir", required=True,
                     help="diretorio UNICO no controle -- o mesmo --out passado a "
                          "orchestrator.py run_pilot/run_smoke_gate")
    ap.add_argument("--local-dir", required=True)
    args = ap.parse_args()

    result = collect_pilot_data(args.control_ip, args.key, args.remote_dir, Path(args.local_dir))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

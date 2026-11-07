#!/usr/bin/env python3
"""v9, piloto: coleta de artefatos com manifesto SHA-256 verificado,
POR BLOCO DE PERFIL -- equivalente reduzido ao `campaign_pull.sh`
real da v8 (mesma ideia: manifesto regenerado no controle, puxado
junto com os dados, conferido de novo localmente -- uma transferencia
parcial/corrompida e pega aqui, nao descoberta so na hora de escrever
a tese). Diferenca da v8: aqui, POR BLOCO (um por perfil, 4 no
piloto), nao um pull unico no fim -- cada bloco pode ser confirmado e
liberado assim que o bloco daquele perfil termina, sem esperar o
piloto inteiro.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402


def regenerate_manifest_on_control(control_ip, key_path, remote_block_dir, remote_manifest_path):
    cmd = f"cd {remote_block_dir} && find . -type f -print0 | xargs -0 sha256sum > {remote_manifest_path}"
    proc = cli.run_ssh(control_ip, cmd, key_path=key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"gerar manifesto no controle falhou: {cli.redact(proc.stderr)}")
    return proc


def pull_block(control_ip, key_path, remote_block_dir, remote_manifest_path, local_dest_dir: Path):
    local_dest_dir.mkdir(parents=True, exist_ok=True)
    proc = cli.run_scp(f"ec2-user@{control_ip}:{remote_block_dir}/.", str(local_dest_dir),
                        key_path=key_path, recursive=True)
    if proc.returncode != 0:
        raise RuntimeError(f"scp -r do bloco falhou: {cli.redact(proc.stderr)}")
    proc = cli.run_scp(f"ec2-user@{control_ip}:{remote_manifest_path}",
                        str(local_dest_dir / "manifest.sha256"), key_path=key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"scp do manifesto falhou: {cli.redact(proc.stderr)}")


def verify_local_manifest(local_dest_dir: Path) -> list[str]:
    """Confere cada linha do manifesto (formato `sha256sum`: hash,
    2 espacos ou um `*` antes do caminho) contra o arquivo PULADO de
    verdade -- implementacao Python nativa (nao depende do binario
    `sha256sum -c` estar no PATH local, mesmo correcao, mais
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


def collect_block(control_ip, key_path, profile, remote_base_dir, local_base_dir: Path) -> dict:
    """Coleta UM bloco de perfil -- `remote_base_dir/<profile>/` no
    controle, `local_base_dir/<profile>/` localmente. Escreve
    `.pull-verified` SO depois da verificacao de hash passar (mesmo
    padrao de campaign_down.sh real: esse marcador e o que autoriza
    um teardown depois, ver Decisao 46/47)."""
    remote_block_dir = f"{remote_base_dir}/{profile}"
    remote_manifest_path = f"{remote_base_dir}/{profile}.sha256"
    local_dest_dir = local_base_dir / profile

    regenerate_manifest_on_control(control_ip, key_path, remote_block_dir, remote_manifest_path)
    pull_block(control_ip, key_path, remote_block_dir, remote_manifest_path, local_dest_dir)
    checked = verify_local_manifest(local_dest_dir)
    (local_dest_dir / ".pull-verified").write_text(
        f"{len(checked)} arquivos verificados por sha256\n", encoding="utf-8")
    return {"profile": profile, "files_verified": len(checked), "dest": str(local_dest_dir)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-ip", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--remote-base-dir", default="/home/ec2-user/campaign-data/v9")
    ap.add_argument("--local-base-dir", required=True)
    ap.add_argument("--profiles", nargs="+", default=["classico", "pqc", "hibrido-v8", "hibrido-and"])
    args = ap.parse_args()

    results = [collect_block(args.control_ip, args.key, p, args.remote_base_dir, Path(args.local_base_dir))
               for p in args.profiles]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

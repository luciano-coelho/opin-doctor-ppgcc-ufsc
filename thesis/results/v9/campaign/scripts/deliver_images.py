#!/usr/bin/env python3
"""v9, piloto: PRIMEIRO salto do modelo de entrega de imagens --
restaura o padrao real da v8 (`deliver_images.sh`: `docker save` em
ARQUIVO, sha256 do `.tar`, checagem de espaco em disco no destino,
scp/rsync), achado real desta rodada (Decisao 59): o CONTROLE nunca
roda `docker` (confirmado em PILOT_READINESS.md -- so `pki_relay.py`/
`collect_artifacts.py`/`cleanup.py` rodam la, nenhum invoca `docker`),
mas `orchestrator.py` (SSHExecutor), que roda DE DENTRO do controle
(Security Group do servidor/clientes so aceita SSH do EIP do PROPRIO
controle -- `main.tf`, `ssh_ingress_cidrs = {"control": ...}`), ate a
Decisao 55 fazia `docker save <imagem> | ssh <host> docker load` --
um pipe que EXIGE Docker na maquina que executa esse comando. Esse
pipe so poderia funcionar de verdade rodando do OPERADOR (onde Docker
existe) -- mas o operador nunca alcanca o host direto, e o controle
(que alcanca) nao tem Docker.

Resolvido em DOIS saltos, cada um rodando na maquina certa:
  1. ESTE script (`deliver_images.py`), na maquina do OPERADOR (onde
     Docker + as imagens localmente construidas existem): `docker
     save <imagem> > <imagem>.tar`, sha256, scp pro CONTROLE (`~/images/`),
     com checagem de espaco em disco no controle ANTES de enviar.
     Pro gateway especificamente, tambem extrai o binario `/gateway`
     (docker create+cp) e confere o sha256 contra PINS.json -- MESMA
     logica que `orchestrator._local_gateway_binary_info` fazia antes
     desta rodada, agora so aqui (onde Docker existe de verdade).
  2. `orchestrator.py` (`SSHExecutor._deliver_image`/`_verify_gateway_
     binary`), rodando DE DENTRO DO CONTROLE: le os arquivos LOCAIS
     ja estagiados por este script, scp pro HOST, `ssh host docker
     load` -- nunca `docker` localmente.

Nunca fala com servidor/cliente nenhum -- so com o controle.
"""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cli  # noqa: E402

PINS_PATH = Path(__file__).resolve().parent.parent / "PINS.json"
GATEWAY_IMAGE = "mockopin-v9-gateway"
TOOLCHAIN_IMAGE = "mockopin-v9-toolchain"
REMOTE_STAGING_DIR = "~/images"
ALL_IMAGE_KEYS = ("gateway", "proxy", "pqc-signer", "measure")


def load_pins():
    if not PINS_PATH.is_file():
        raise RuntimeError(f"load_pins: {PINS_PATH} nao encontrado")
    return json.loads(PINS_PATH.read_text(encoding="utf-8"))


def extract_gateway_binary_info(workdir: Path) -> dict:
    """Mesma extracao que `orchestrator._local_gateway_binary_info`
    fazia (Decisao 54) antes desta rodada -- agora so roda aqui, na
    maquina do OPERADOR, nunca no controle. Fail-closed contra
    PINS.json antes mesmo de empacotar qualquer `.tar`."""
    bin_path = workdir / "gateway"
    container = "v9-gateway-extract-deliver-images"
    cli._run(["docker", "rm", "-f", container], timeout=30)
    create = cli._run(["docker", "create", "--name", container, GATEWAY_IMAGE], timeout=30)
    if create.returncode != 0:
        raise RuntimeError(f"extract_gateway_binary_info: docker create falhou: {create.stderr}")
    try:
        cp = cli._run(["docker", "cp", f"{container}:/gateway", str(bin_path)], timeout=30)
    finally:
        cli._run(["docker", "rm", "-f", container], timeout=30)
    if cp.returncode != 0:
        raise RuntimeError(f"extract_gateway_binary_info: docker cp falhou: {cp.stderr}")

    sha256 = hashlib.sha256(bin_path.read_bytes()).hexdigest()
    gv = cli._run(
        ["docker", "run", "--rm", "-v", f"{workdir}:/verify:ro",
         "--entrypoint", "/go-src/bin/go", TOOLCHAIN_IMAGE, "version", "-m", "/verify/gateway"],
        timeout=30,
    )
    go_version_m = gv.stdout.strip() if gv.returncode == 0 else f"ERRO ({gv.returncode}): {gv.stderr.strip()}"
    first_line = go_version_m.splitlines()[0] if go_version_m else ""
    go_build_version = first_line.split(":", 1)[1].strip() if ":" in first_line else None

    meta_proc = cli._run(["docker", "run", "--rm", "--entrypoint", "cat", TOOLCHAIN_IMAGE, "/build_metadata.json"], timeout=30)
    toolchain_build_metadata = None
    if meta_proc.returncode == 0:
        try:
            toolchain_build_metadata = json.loads(meta_proc.stdout)
        except json.JSONDecodeError:
            toolchain_build_metadata = {"raw": meta_proc.stdout.strip()}

    pins = load_pins()
    pin_sha256 = pins["images"]["gateway"]["binary_sha256"]
    if sha256 != pin_sha256:
        raise RuntimeError(
            f"extract_gateway_binary_info: sha256 do binario do gateway NAO bate com PINS.json -- "
            f"esperado {pin_sha256}, obtido {sha256}. Alterar PINS.json exige Emenda numerada "
            f"explicita em DECISIONS.md, nunca uma atualizacao automatica."
        )
    return {"sha256": sha256, "go_version_m": go_version_m,
            "go_build_version": go_build_version, "toolchain_build_metadata": toolchain_build_metadata}


def save_image_tarball(image_key: str, docker_image: str, out_dir: Path) -> Path:
    """Achado real (execucao real desta rodada): `sh -c "docker save
    ... > <path>"` com um PATH DO WINDOWS (barras invertidas) dentro
    de uma string de shell corrompe o redirecionamento -- `docker
    save` ainda devolvia rc=0 (o comando em si nao falhava), mas o
    arquivo nunca aparecia no caminho esperado. Corrigido: `docker
    save -o <path>` como argv PURO (lista, nunca string de shell) --
    o proprio Docker recebe o caminho, sem nenhum shell no meio pra
    interpretar barra invertida como escape."""
    tar_path = out_dir / f"{image_key}.tar"
    proc = cli._run(["docker", "save", "-o", str(tar_path), docker_image], timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"save_image_tarball({image_key}): docker save falhou: {proc.stderr}")
    if not tar_path.is_file():
        raise RuntimeError(f"save_image_tarball({image_key}): docker save retornou OK mas {tar_path} nao existe")
    return tar_path


def check_control_disk_space(control_ip, operator_key_path, needed_bytes, headroom_factor=2):
    """Decisao 59: o controle e `t4g.micro`, mas com volume `gp3` de
    30GB (confirmado em `modules/campaign_instance/main.tf`,
    `root_block_device`) -- folga enorme pros ~140MB totais das 4
    imagens (medido nesta sessao: gateway ~10MB, proxy ~9MB,
    pqc-signer ~59MB, measure ~58MB). Ainda assim, a checagem roda de
    verdade (nunca assume que cabe) -- `headroom_factor=2` cobre o
    .tar mais o espaco que ele ocupa staged ao mesmo tempo que outra
    copia transita (margem, nao calculo exato)."""
    proc = cli.run_ssh(control_ip, "df --output=avail -k / | tail -1", key_path=operator_key_path)
    if proc.returncode != 0:
        raise RuntimeError(f"check_control_disk_space: df no controle falhou: {cli.redact(proc.stderr)}")
    avail_kb = int(proc.stdout.strip())
    needed_kb = (needed_bytes // 1024) * headroom_factor
    if avail_kb < needed_kb:
        raise RuntimeError(
            f"check_control_disk_space: controle tem {avail_kb}KB livres, precisa de ~{needed_kb}KB "
            f"(com margem de {headroom_factor}x) -- abortando antes de enviar."
        )
    return {"avail_kb": avail_kb, "needed_kb": needed_kb}


def deliver_images(control_ip, operator_key_path, images=ALL_IMAGE_KEYS):
    """Unico salto: operador -> controle. Nunca fala com servidor/
    cliente nenhum (isso e `orchestrator.py._deliver_image`, rodando
    DO controle, depois)."""
    pins = load_pins()
    report = {"images": {}}
    with tempfile.TemporaryDirectory(prefix="v9_deliver_images_") as tmp:
        workdir = Path(tmp)
        tar_paths = {}
        total_bytes = 0
        for key in images:
            docker_image = pins["images"][key]["docker_image"]
            tar_path = save_image_tarball(key, docker_image, workdir)
            tar_paths[key] = tar_path
            total_bytes += tar_path.stat().st_size

        gw_info_path = None
        if "gateway" in images:
            gw_info = extract_gateway_binary_info(workdir)
            gw_info_path = workdir / "gateway_binary_info.json"
            gw_info_path.write_text(json.dumps(gw_info, indent=2), encoding="utf-8")

        report["disk_check"] = check_control_disk_space(control_ip, operator_key_path, total_bytes)

        mkdir_proc = cli.run_ssh(control_ip, f"mkdir -p {REMOTE_STAGING_DIR}", key_path=operator_key_path)
        if mkdir_proc.returncode != 0:
            raise RuntimeError(f"deliver_images: mkdir no controle falhou: {cli.redact(mkdir_proc.stderr)}")

        for key, tar_path in tar_paths.items():
            sha256 = hashlib.sha256(tar_path.read_bytes()).hexdigest()
            sha_path = tar_path.parent / f"{tar_path.name}.sha256"
            sha_path.write_text(f"{sha256}  {tar_path.name}\n", encoding="utf-8")

            scp_proc = cli.run_scp(str(tar_path), f"ec2-user@{control_ip}:{REMOTE_STAGING_DIR}/{tar_path.name}", key_path=operator_key_path)
            if scp_proc.returncode != 0:
                raise RuntimeError(f"deliver_images({key}): scp do tar pro controle falhou: {cli.redact(scp_proc.stderr)}")
            cli.run_scp(str(sha_path), f"ec2-user@{control_ip}:{REMOTE_STAGING_DIR}/{sha_path.name}", key_path=operator_key_path)

            verify_proc = cli.run_ssh(control_ip, f"cd {REMOTE_STAGING_DIR} && sha256sum -c {sha_path.name}", key_path=operator_key_path)
            ok = verify_proc.returncode == 0
            report["images"][key] = {"tar_bytes": tar_path.stat().st_size, "sha256_ok": ok}
            if not ok:
                raise RuntimeError(f"deliver_images({key}): sha256sum -c falhou no controle: {cli.redact(verify_proc.stderr)}")

        if gw_info_path is not None:
            raw_bin_path = workdir / "gateway"
            info_scp = cli.run_scp(str(gw_info_path), f"ec2-user@{control_ip}:{REMOTE_STAGING_DIR}/gateway_binary_info.json", key_path=operator_key_path)
            if info_scp.returncode != 0:
                raise RuntimeError(f"deliver_images: scp de gateway_binary_info.json falhou: {cli.redact(info_scp.stderr)}")
            bin_scp = cli.run_scp(str(raw_bin_path), f"ec2-user@{control_ip}:{REMOTE_STAGING_DIR}/gateway", key_path=operator_key_path)
            if bin_scp.returncode != 0:
                raise RuntimeError(f"deliver_images: scp do binario gateway falhou: {cli.redact(bin_scp.stderr)}")
            report["gateway_binary_info_delivered"] = True

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--control-ip", required=True)
    ap.add_argument("--operator-key", required=True)
    ap.add_argument("--images", nargs="+", default=list(ALL_IMAGE_KEYS))
    args = ap.parse_args()
    report = deliver_images(args.control_ip, args.operator_key, images=args.images)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Testes da coleta de artefatos com SHA-256 -- scp/ssh stubados
(cli.run_scp/cli.run_ssh monkeypatchados), nenhuma rede real. O stub
de scp simula o efeito real (copiar arquivo) a partir de um
diretorio "remoto" fake local, pra exercitar a verificacao de hash de
verdade, nao so a orquestracao de chamadas."""
import hashlib
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402
import collect_artifacts as ca  # noqa: E402


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _setup_fake_remote(tmp_path, profile, contents):
    remote_root = tmp_path / "fake_remote"
    block_dir = remote_root / profile
    block_dir.mkdir(parents=True)
    for name, data in contents.items():
        (block_dir / name).write_bytes(data)
    manifest_lines = []
    for name, data in contents.items():
        h = hashlib.sha256(data).hexdigest()
        manifest_lines.append(f"{h}  ./{name}")
    (remote_root / f"{profile}.sha256").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return remote_root, block_dir


def _patch_scp_ssh(monkeypatch, remote_root: Path):
    def fake_run_ssh(host, remote_cmd, **kwargs):
        return FakeProc(returncode=0)  # "gerar manifesto" ja esta pronto no fixture

    def fake_run_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        # src e algo como "ec2-user@IP:<remote_path>[/.]" -- <remote_path>
        # e sempre um caminho real em disco nestes testes (remote_base_dir
        # foi passado como str(remote_root)), so precisa do que vem
        # depois do PRIMEIRO ":".
        remote_path_str = src.split(":", 1)[1]
        if remote_path_str.endswith("/."):
            remote_path_str = remote_path_str[:-2]
        source = Path(remote_path_str)
        if recursive:
            dest_dir = Path(dst)
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in source.glob("*"):
                if f.is_file():
                    shutil.copy(f, dest_dir / f.name)
        else:
            shutil.copy(source, Path(dst))
        return FakeProc(returncode=0)

    monkeypatch.setattr(ca.cli, "run_ssh", fake_run_ssh)
    monkeypatch.setattr(ca.cli, "run_scp", fake_run_scp)


def test_coleta_um_bloco_com_hash_correto(tmp_path, monkeypatch):
    remote_root, _ = _setup_fake_remote(tmp_path, "classico", {
        "run01.json": b'{"ok": true}', "run02.json": b'{"ok": true}',
    })
    _patch_scp_ssh(monkeypatch, remote_root)

    local_base = tmp_path / "local"
    result = ca.collect_block("203.0.113.5", "/fake/key", "classico",
                               remote_base_dir=str(remote_root), local_base_dir=local_base)
    assert result["files_verified"] == 2
    assert (local_base / "classico" / ".pull-verified").is_file()


def test_arquivo_corrompido_na_transferencia_e_detectado(tmp_path, monkeypatch):
    remote_root, block_dir = _setup_fake_remote(tmp_path, "pqc", {"run01.json": b'{"ok": true}'})
    _patch_scp_ssh(monkeypatch, remote_root)

    # Corrompe o arquivo remoto DEPOIS do manifesto ja ter sido
    # calculado sobre o conteudo original -- simula uma transferencia
    # que mudou o byte no meio do caminho.
    (block_dir / "run01.json").write_bytes(b'{"ok": false}')

    local_base = tmp_path / "local"
    with pytest.raises(RuntimeError, match="nao bate"):
        ca.collect_block("203.0.113.5", "/fake/key", "pqc",
                          remote_base_dir=str(remote_root), local_base_dir=local_base)
    assert not (local_base / "pqc" / ".pull-verified").exists(), "nunca deveria marcar como verificado apos um hash incorreto"


def test_arquivo_ausente_apos_pull_e_detectado(tmp_path, monkeypatch):
    remote_root, block_dir = _setup_fake_remote(tmp_path, "hibrido-v8", {"run01.json": b"x", "run02.json": b"y"})
    _patch_scp_ssh(monkeypatch, remote_root)
    local_base = tmp_path / "local"

    # Mutante: simula uma transferencia parcial -- apaga run02.json
    # do lado remoto DEPOIS do pull ter copiado so o que existia na
    # hora (aqui simulamos removendo do destino local apos o pull).
    original_pull_block = ca.pull_block

    def partial_pull(control_ip, key_path, remote_block_dir, remote_manifest_path, local_dest_dir):
        original_pull_block(control_ip, key_path, remote_block_dir, remote_manifest_path, local_dest_dir)
        (local_dest_dir / "run02.json").unlink()

    monkeypatch.setattr(ca, "pull_block", partial_pull)
    with pytest.raises(RuntimeError, match="ausente"):
        ca.collect_block("203.0.113.5", "/fake/key", "hibrido-v8",
                          remote_base_dir=str(remote_root), local_base_dir=local_base)


def test_mutante_verificacao_desligada_e_pega_pelo_teste_de_corrupcao(monkeypatch, tmp_path):
    """Mutacao: verify_local_manifest() sempre retorna sem checar nada
    -- os dois testes de corrupcao/ausencia acima tem que reprovar
    com essa mutacao, provando que dependem de verdade da verificacao."""
    monkeypatch.setattr(ca, "verify_local_manifest", lambda local_dest_dir: [])
    remote_root, block_dir = _setup_fake_remote(tmp_path, "pqc", {"run01.json": b'{"ok": true}'})
    _patch_scp_ssh_local = _patch_scp_ssh
    _patch_scp_ssh_local(monkeypatch, remote_root)
    (block_dir / "run01.json").write_bytes(b'{"ok": false}')  # corrompido
    local_base = tmp_path / "local"
    # com a mutacao, NAO levanta mais -- confirma que o teste real
    # (acima) de fato dependia da verificacao real, nao passava por
    # acidente.
    result = ca.collect_block("203.0.113.5", "/fake/key", "pqc",
                               remote_base_dir=str(remote_root), local_base_dir=local_base)
    assert result["files_verified"] == 0

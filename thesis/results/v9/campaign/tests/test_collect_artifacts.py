"""Testes da coleta de artefatos com SHA-256 -- scp/ssh stubados
(cli.run_scp/cli.run_ssh monkeypatchados), nenhuma rede real. O stub
de scp simula o efeito real (copiar arquivo) a partir de um
diretorio "remoto" fake local, pra exercitar a verificacao de hash de
verdade, nao so a orquestracao de chamadas.

Decisao 75, item 3: o diretorio remoto fake aqui e FLAT (mesmo
formato que `orchestrator.py run_pilot` realmente produz --
piloto_combined.log, piloto_calls.json, criterio1_capturas/*.log,
etc., tudo num unico diretorio) -- nunca mais dividido por perfil,
que nunca foi o formato real."""
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


def _setup_fake_remote(tmp_path, contents):
    """Monta um diretorio remoto FAKE, flat -- igual ao que run_pilot
    produz de verdade (alguns arquivos na raiz, alguns num
    subdiretorio como criterio1_capturas/, mas NUNCA um subdiretorio
    por perfil)."""
    remote_dir = tmp_path / "fake_remote" / "piloto"
    remote_dir.mkdir(parents=True)
    for name, data in contents.items():
        dest = remote_dir / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    manifest_lines = []
    for name, data in contents.items():
        h = hashlib.sha256(data).hexdigest()
        manifest_lines.append(f"{h}  ./{name}")
    manifest_path = remote_dir.parent / "piloto.sha256"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    return remote_dir, manifest_path


def _patch_scp_ssh(monkeypatch, remote_dir: Path, manifest_path: Path):
    def fake_run_ssh(host, remote_cmd, **kwargs):
        return FakeProc(returncode=0)  # "gerar manifesto" ja esta pronto no fixture

    def fake_run_scp(src, dst, key_path=None, port=22, connect_timeout=20, recursive=False):
        # src e algo como "ec2-user@IP:<remote_path>[/.]" -- <remote_path>
        # e sempre um caminho real em disco nestes testes, so precisa do
        # que vem depois do PRIMEIRO ":".
        remote_path_str = src.split(":", 1)[1]
        if remote_path_str.endswith("/."):
            remote_path_str = remote_path_str[:-2]
        source = Path(remote_path_str)
        if recursive:
            dest_dir = Path(dst)
            dest_dir.mkdir(parents=True, exist_ok=True)
            for f in source.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(source)
                    out = dest_dir / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(f, out)
        else:
            shutil.copy(source, Path(dst))
        return FakeProc(returncode=0)

    monkeypatch.setattr(ca.cli, "run_ssh", fake_run_ssh)
    monkeypatch.setattr(ca.cli, "run_scp", fake_run_scp)


def test_coleta_diretorio_flat_com_hash_correto(tmp_path, monkeypatch):
    remote_dir, manifest_path = _setup_fake_remote(tmp_path, {
        "piloto_combined.log": b"log de verdade\n",
        "piloto_calls.json": b'[{"ok": true}]',
        "manifest.json": b'{"smoke": false}',
        "criterio1_capturas/classico_L0.log": b"captura 1",
    })
    _patch_scp_ssh(monkeypatch, remote_dir, manifest_path)

    local_dir = tmp_path / "local"
    result = ca.collect_pilot_data("203.0.113.5", "/fake/key",
                                    remote_dir=str(remote_dir), local_dir=local_dir)
    assert result["files_verified"] == 4
    assert (local_dir / ".pull-verified").is_file()
    assert (local_dir / "criterio1_capturas" / "classico_L0.log").is_file()


def test_arquivo_corrompido_na_transferencia_e_detectado(tmp_path, monkeypatch):
    remote_dir, manifest_path = _setup_fake_remote(tmp_path, {"piloto_combined.log": b"original"})
    _patch_scp_ssh(monkeypatch, remote_dir, manifest_path)

    # Corrompe o arquivo remoto DEPOIS do manifesto ja ter sido
    # calculado sobre o conteudo original -- simula uma transferencia
    # que mudou o byte no meio do caminho.
    (remote_dir / "piloto_combined.log").write_bytes(b"corrompido")

    local_dir = tmp_path / "local"
    with pytest.raises(RuntimeError, match="nao bate"):
        ca.collect_pilot_data("203.0.113.5", "/fake/key", remote_dir=str(remote_dir), local_dir=local_dir)
    assert not (local_dir / ".pull-verified").exists(), "nunca deveria marcar como verificado apos um hash incorreto"


def test_arquivo_ausente_apos_pull_e_detectado(tmp_path, monkeypatch):
    remote_dir, manifest_path = _setup_fake_remote(
        tmp_path, {"piloto_combined.log": b"x", "piloto_calls.json": b"y"})
    _patch_scp_ssh(monkeypatch, remote_dir, manifest_path)
    local_dir = tmp_path / "local"

    # Mutante: simula uma transferencia parcial -- o pull copiou os
    # dois arquivos, mas um deles some do destino local depois.
    original_pull_dir = ca.pull_dir

    def partial_pull(control_ip, key_path, remote_dir_, remote_manifest_path, local_dest_dir):
        original_pull_dir(control_ip, key_path, remote_dir_, remote_manifest_path, local_dest_dir)
        (local_dest_dir / "piloto_calls.json").unlink()

    monkeypatch.setattr(ca, "pull_dir", partial_pull)
    with pytest.raises(RuntimeError, match="ausente"):
        ca.collect_pilot_data("203.0.113.5", "/fake/key", remote_dir=str(remote_dir), local_dir=local_dir)


def test_mutante_verificacao_desligada_e_pega_pelo_teste_de_corrupcao(monkeypatch, tmp_path):
    """Mutacao: verify_local_manifest() sempre retorna sem checar nada
    -- os dois testes de corrupcao/ausencia acima tem que reprovar
    com essa mutacao, provando que dependem de verdade da verificacao."""
    monkeypatch.setattr(ca, "verify_local_manifest", lambda local_dest_dir: [])
    remote_dir, manifest_path = _setup_fake_remote(tmp_path, {"piloto_combined.log": b"original"})
    _patch_scp_ssh(monkeypatch, remote_dir, manifest_path)
    (remote_dir / "piloto_combined.log").write_bytes(b"corrompido")
    local_dir = tmp_path / "local"
    # com a mutacao, NAO levanta mais -- confirma que o teste real
    # (acima) de fato dependia da verificacao real, nao passava por
    # acidente.
    result = ca.collect_pilot_data("203.0.113.5", "/fake/key", remote_dir=str(remote_dir), local_dir=local_dir)
    assert result["files_verified"] == 0

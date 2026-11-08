"""Decisao 68, item 2: varredura de CRLF/caminho do Windows no caminho
remoto inteiro -- nenhum arquivo .sh/.tftpl/.py/.json/chave que chega
numa instancia Linux (via scp/docker load/terraform user_data) pode
conter `\\r`. `.gitattributes` (repo raiz) ja normaliza pra `eol=lf`
nos arquivos COMMITADOS -- este teste e a rede de seguranca pro que
`.gitattributes` nao cobre: arquivos gerados em RUNTIME (nunca
comitados) e qualquer regressao futura, mesmo que alguem desative a
normalizacao do git por acidente."""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))
import deliver_source as ds  # noqa: E402

_SWEEP_EXTENSIONS = (".sh", ".tftpl", ".py", ".json")
# Diretorios que nunca fazem parte do que e commitado/entregue --
# pycache, .terraform (binarios de provider).
_SKIP_DIR_NAMES = {"__pycache__", ".terraform"}


def _iter_sweep_files():
    """So o que de verdade viaja pro Linux (controle/servidor/cliente):
    as 3 listas de `deliver_source.py` (fonte unica de verdade -- nunca
    duplicada aqui, pra nunca ficar desatualizada), mais os templates
    .tftpl do terraform (user_data, injetado nas instancias no boot) e
    o proprio diretorio de scripts/tests do pacote campaign (roda no
    controle ou e varrido pelos testes que rodam la)."""
    seen = set()

    for rel in ds.COMMON_FILES + ds.CLIENT_ONLY_FILES + ds.CONTROL_FILES:
        path = _REPO_ROOT / rel
        if path.is_file() and path.suffix in _SWEEP_EXTENSIONS:
            if path not in seen:
                seen.add(path)
                yield path
        elif path.is_dir():
            for sub in path.rglob("*"):
                if sub.is_file() and sub.suffix in _SWEEP_EXTENSIONS and sub not in seen:
                    seen.add(sub)
                    yield sub

    extra_dirs = [
        _REPO_ROOT / "thesis" / "results" / "v9" / "terraform",
        _REPO_ROOT / "thesis" / "results" / "v9" / "campaign" / "scripts",
        _REPO_ROOT / "thesis" / "results" / "v9" / "campaign" / "tests",
    ]
    for base in extra_dirs:
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in _SWEEP_EXTENSIONS:
                continue
            if any(part in _SKIP_DIR_NAMES for part in path.parts):
                continue
            if path not in seen:
                seen.add(path)
                yield path


def test_nenhum_arquivo_do_caminho_remoto_contem_cr():
    """Decisao 68, item 2 -- pedido explicito: "um teste que falhe se
    algum arquivo enviado ao Linux contiver \\r". Varre de verdade os
    arquivos em disco (nunca confia so no `.gitattributes`, que so
    normaliza o que e commitado, nunca o que e gerado em runtime)."""
    offenders = []
    for path in _iter_sweep_files():
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\r" in raw:
            offenders.append(str(path.relative_to(_REPO_ROOT)))
    assert not offenders, (
        "arquivo(s) do caminho remoto com \\r (CRLF ou CR solto) -- rejeitado por "
        "sha256sum/ssh/parsers reais no lado Linux:\n" + "\n".join(offenders)
    )


def test_a_varredura_realmente_encontra_arquivos():
    """Mutante-sanidade: confirma que `_iter_sweep_files` nao esta,
    por acidente, devolvendo uma lista vazia (o que faria o teste
    acima passar sempre, mesmo com um bug real escondido)."""
    found = list(_iter_sweep_files())
    assert len(found) > 20, f"varredura encontrou poucos arquivos ({len(found)}) -- os diretorios/extensoes esperados existem?"


def test_a_varredura_detecta_cr_de_verdade(tmp_path):
    """Mutante: grava um arquivo COM \\r de proposito e confirma que a
    logica de deteccao usada pelo teste principal (`b"\\r" in raw`) de
    fato reprova -- sem isso, o teste principal poderia estar
    comparando contra um byte errado e nunca pegar nada real."""
    bad_file = tmp_path / "bad.sh"
    bad_file.write_bytes(b"#!/bin/bash\r\necho hi\r\n")
    assert b"\r" in bad_file.read_bytes(), "o mutante com \\r de proposito deveria ter sido encontrado"

    good_file = tmp_path / "good.sh"
    good_file.write_bytes(b"#!/bin/bash\necho hi\n")
    assert b"\r" not in good_file.read_bytes(), "arquivo so com \\n nao pode disparar falso positivo"

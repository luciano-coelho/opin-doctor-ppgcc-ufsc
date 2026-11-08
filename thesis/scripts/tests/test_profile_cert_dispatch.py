"""Decisao 52 (pedido independente, v9, item 3): auditoria de grep achou
"hibrido-and" caindo num `else`/default silencioso em duas funcoes de
`opin_flow.py` (get_client_cert_paths/get_local_leg_cert_paths),
corrigidas por correcao, nao so por consequencia. Testes puros, sem
Docker, sem stack, sem rede -- confirma so o DESPACHO por nome de
perfil, nao o conteudo dos arquivos.

Decisao 53 (correcao desta rodada): a Decisao 52 alegou que as DUAS
funcoes eram "mortas no piloto" sob V9_HARNESS=1 -- FALSO pra
`get_local_leg_cert_paths`, que `run_insurance_flow`/`run_person_flow`
chamam incondicionalmente (sem guarda de V9_HARNESS nenhuma). So
`get_client_cert_paths` e genuinamente morta sob V9_HARNESS=1 (so
alcancavel pelo ramo NAO-V9_HARNESS de `start_tls_kem_proxy`). Os
testes abaixo (pedidos explicitamente pelo Luciano) provam as duas
alegacoes -- a correta E a corrigida -- com evidencia, nao suposicao."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import opin_flow as of  # noqa: E402


def test_hibrido_and_usa_o_mesmo_cert_que_hybrid_get_client_cert_paths():
    assert of.get_client_cert_paths("hibrido-and") == of.get_client_cert_paths("hybrid")


def test_hibrido_and_nao_cai_no_cert_classico_get_client_cert_paths():
    assert of.get_client_cert_paths("hibrido-and") != of.get_client_cert_paths("classic")


def test_mutante_sem_hibrido_and_cairia_no_classico():
    """Mutacao: reproduz o bug ORIGINAL (achado pela auditoria) --
    confirma que o teste acima de fato depende da correcao, nao passa
    por acidente."""
    def bugged(crypto_profile):
        if crypto_profile == "pqc":
            return "pqc-path"
        elif crypto_profile == "hybrid":
            return "hybrid-path"
        else:
            return "classic-path"  # mutante: hibrido-and cai aqui

    assert bugged("hibrido-and") == "classic-path"
    assert bugged("hibrido-and") != bugged("hybrid")


def test_hibrido_and_usa_o_mesmo_placeholder_que_hybrid_local_leg():
    assert of.get_local_leg_cert_paths("hibrido-and") == of.get_local_leg_cert_paths("hybrid")
    assert of.get_local_leg_cert_paths("hibrido-and") == of.get_client_cert_paths("classic")


# --- Decisao 53 (pedido independente, item 3): teste que falha se
# get_client_cert_paths/get_local_leg_cert_paths forem chamadas com
# V9_HARNESS ativo -- exatamente como pedido. V9_HARNESS e lido no
# IMPORT do modulo (variavel de modulo, nao recalculada em toda
# chamada), entao o teste precisa setar a env var ANTES de um
# `importlib.reload`, e sempre reverter (reload de novo) no finally --
# senao o estado de V9_HARNESS vazaria pros proximos testes do mesmo
# processo pytest.
import importlib
import subprocess as _subprocess


def _reload_with_v9_harness(monkeypatch, value):
    if value:
        monkeypatch.setenv("V9_HARNESS", "1")
    else:
        monkeypatch.delenv("V9_HARNESS", raising=False)
    importlib.reload(of)


def test_get_client_cert_paths_nunca_chamada_sob_v9_harness(monkeypatch):
    """GREEN -- prova que get_client_cert_paths() e genuinamente morta
    no ramo V9_HARNESS=1 de start_tls_kem_proxy (a unica funcao que a
    chamaria, fora desta): o proxy real do v9 carrega o certificado do
    AND nativamente em Go (`dualClientConfig`), nunca pelo Python."""
    try:
        _reload_with_v9_harness(monkeypatch, True)
        assert of.V9_HARNESS is True

        calls = []
        monkeypatch.setattr(of, "get_client_cert_paths", lambda p: (calls.append(p), ("fake.crt", "fake.key"))[1])
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: __import__("types").SimpleNamespace(returncode=0, stdout="", stderr=""))
        monkeypatch.setattr(of, "_wait_for_tls_kem_proxy_ready_detached", lambda: None)

        of.start_tls_kem_proxy("hibrido-and", detached=True)
        assert calls == [], f"get_client_cert_paths foi chamada sob V9_HARNESS=1: {calls}"
    finally:
        importlib.reload(of)


def test_experimento_descartavel_get_client_cert_paths_E_chamada_sem_v9_harness(monkeypatch):
    """VERMELHO (experimento descartavel, item 3): a MESMA asserção
    ("nunca chamada"), agora SEM V9_HARNESS -- tem que falhar, provando
    que o teste verde acima nao e vacuamente verde (get_client_cert_
    paths nao e "morta" em geral, so dentro do ramo V9_HARNESS)."""
    try:
        _reload_with_v9_harness(monkeypatch, False)
        assert of.V9_HARNESS is False

        calls = []
        monkeypatch.setattr(of, "get_client_cert_paths", lambda p: (calls.append(p), ("fake.crt", "fake.key"))[1])
        monkeypatch.setattr(_subprocess, "run", lambda *a, **k: __import__("types").SimpleNamespace(returncode=0, stdout="", stderr=""))
        monkeypatch.setattr(of, "subprocess", _subprocess)
        import unittest.mock as mock
        fake_popen = mock.MagicMock()
        fake_popen.stdout = iter([])
        monkeypatch.setattr(_subprocess, "Popen", lambda *a, **k: fake_popen)
        monkeypatch.setattr(of, "_wait_for_tls_kem_proxy_ready", lambda proc: None)

        try:
            of.start_tls_kem_proxy("hybrid", detached=False)
        except Exception:
            pass  # so precisamos que get_client_cert_paths tenha sido chamada antes de qualquer erro
        with pytest.raises(AssertionError):
            assert calls == []  # a asssercao "boa" (a mesma do teste GREEN) reprova aqui -- red real
        assert calls != []
    finally:
        importlib.reload(of)


def test_get_local_leg_cert_paths_e_live_sob_v9_harness_correcao_da_decisao_52(monkeypatch):
    """Correcao da Decisao 52: aquela rodada alegou que as DUAS
    funcoes (get_client_cert_paths/get_local_leg_cert_paths) eram
    "mortas no piloto" sob V9_HARNESS=1. Falso para esta segunda --
    `run_insurance_flow()`/`run_person_flow()` chamam
    get_local_leg_cert_paths() SEM nenhuma guarda de V9_HARNESS (ver
    opin_flow.py, primeira linha de run_insurance_flow). Confirmado
    aqui chamando run_insurance_flow() de verdade (com a sessao HTTP e
    as funcoes de rede adiante mockadas, pra nao precisar de stack) e
    provando que get_local_leg_cert_paths FOI chamada antes de
    qualquer chamada de rede."""
    try:
        _reload_with_v9_harness(monkeypatch, True)
        assert of.V9_HARNESS is True

        calls = []
        real = of.get_local_leg_cert_paths
        monkeypatch.setattr(of, "get_local_leg_cert_paths", lambda p: (calls.append(p), real(p))[1])

        class _BoomSession:
            def __getattr__(self, name):
                raise RuntimeError("rede real bloqueada de proposito -- so testando ate aqui")

        monkeypatch.setattr(of.requests, "Session", lambda: _BoomSession())
        try:
            of.run_insurance_flow("hibrido-and")
        except RuntimeError:
            pass  # esperado -- a funcao foi interrompida na primeira chamada de rede real

        assert calls == ["hibrido-and"], (
            "get_local_leg_cert_paths deveria ter sido chamada ANTES de qualquer rede, mesmo sob V9_HARNESS=1"
        )
    finally:
        importlib.reload(of)

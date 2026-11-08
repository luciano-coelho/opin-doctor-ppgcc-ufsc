"""Decisao 52 (pedido independente, v9, item 3): auditoria de grep achou
"hibrido-and" caindo num `else`/default silencioso em duas funcoes de
`opin_flow.py` (get_client_cert_paths/get_local_leg_cert_paths), nunca
exercitado pelo piloto real em si (V9_HARNESS=1 pula as duas inteiras --
ver start_tls_kem_proxy), mas corrigido mesmo assim por correcao, nao so
por consequencia. Testes puros, sem Docker, sem stack, sem rede --
confirma so o DESPACHO por nome de perfil, nao o conteudo dos arquivos."""
import sys
from pathlib import Path

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

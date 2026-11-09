"""Testes de campaign_topology.py (generalizacao do orquestrador pra N
servidores, pedido do Luciano) -- em particular, o teste que PROVA que
CAMPAIGN_REGIONS nunca diverge do Terraform real da campanha oficial
(item 2 do pedido: "um unico source -- precisa de um teste automatico
que FALHE se essa fonte divergir das regioes declaradas em
terraform_campanha_oficial/")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import campaign_topology as ct  # noqa: E402


def test_campaign_regions_bate_com_terraform_real():
    """O teste fail-closed pedido explicitamente: se alguem editar
    terraform_campanha_oficial/providers.tf (adicionar/remover uma
    regiao) sem atualizar CAMPAIGN_REGIONS aqui, este teste PRECISA
    reprovar -- nunca os dois ficarem dessincronizados silenciosamente
    (a mesma classe de risco que a Decisao 96 ja fechou pro piloto)."""
    real = sorted(ct.regions_from_terraform())
    assert real == sorted(ct.CAMPAIGN_REGIONS), (
        f"CAMPAIGN_REGIONS diverge do Terraform real: terraform tem {real}, "
        f"CAMPAIGN_REGIONS tem {sorted(ct.CAMPAIGN_REGIONS)}"
    )


def test_mutante_campaign_regions_desatualizada_e_pega():
    """Mutante: simula CAMPAIGN_REGIONS esquecida de atualizar (uma
    regiao a menos) -- confirma que o teste real acima de fato
    reprovaria essa divergencia, nunca passa por acidente."""
    real = sorted(ct.regions_from_terraform())
    mutant_regions = sorted(ct.CAMPAIGN_REGIONS)[:-1]  # esquece a ultima
    assert real != mutant_regions


def test_todas_as_rotas_tem_servidor_e_rtt_nominal():
    for route in ct.CAMPAIGN_ROUTES:
        assert route in ct.CAMPAIGN_ROUTE_SERVER, route
        assert ct.CAMPAIGN_ROUTE_SERVER[route] in ct.CAMPAIGN_SERVERS, route
        assert route in ct.CAMPAIGN_NOMINAL_RTT_MS, route


def test_8_rotas_3_servidores_sem_duplicata():
    assert len(ct.CAMPAIGN_ROUTES) == 8
    assert len(set(ct.CAMPAIGN_ROUTES)) == 8  # nenhuma colisao de rotulo
    assert len(ct.CAMPAIGN_SERVERS) == 3
    assert len(set(ct.CAMPAIGN_SERVERS)) == 3


def test_cada_servidor_tem_exatamente_1_rota_l0_colocada():
    """As 3 variantes L0 (uma por servidor) -- exatamente 1 rota
    colocalizada por servidor, nunca 0 nem 2."""
    for server in ct.CAMPAIGN_SERVERS:
        l0_routes = [r for r, s in ct.CAMPAIGN_ROUTE_SERVER.items() if s == server and r.startswith("L0-")]
        assert len(l0_routes) == 1, (server, l0_routes)
    assert sorted(r for r in ct.CAMPAIGN_ROUTES if r.startswith("L0-")) == [
        "L0-ap-northeast-1", "L0-sa-east-1", "L0-us-east-1",
    ]


def test_scenario_table_cobre_as_8_rotas_sem_duplicata():
    rotas_na_tabela = [row["rota"] for row in ct.CAMPAIGN_SCENARIO_TABLE]
    assert sorted(rotas_na_tabela) == sorted(ct.CAMPAIGN_ROUTES)
    assert len(rotas_na_tabela) == len(set(rotas_na_tabela))
    for row in ct.CAMPAIGN_SCENARIO_TABLE:
        assert row["servidor"] == ct.CAMPAIGN_ROUTE_SERVER[row["rota"]]
        assert row["nominal_rtt_ms"] == ct.CAMPAIGN_NOMINAL_RTT_MS[row["rota"]]
        assert row["colocalizado"] == row["rota"].startswith("L0-")

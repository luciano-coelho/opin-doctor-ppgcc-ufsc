#!/usr/bin/env python3
"""v9, campanha oficial: configuracao de topologia -- UNICA fonte de
verdade pras 7 regioes / 3 servidores / 8 rotas da campanha oficial
(Decisao -- generalizacao do orquestrador pra N servidores, pedido do
Luciano apos a adaptacao do Terraform multi-regiao).

NUNCA usado pelo piloto, que continua com suas proprias constantes
(orchestrator.PROFILES/ROUTES, evaluate_criteria.PILOT_ROUTES/
NOMINAL_RTT_MS, cleanup.REGIONS etc.) -- regra de compatibilidade
explicita do Luciano, item 1: "o piloto mantem a configuracao atual
exatamente como esta".

Rotulos de rota: as 8 rotas reais da v8 (DECISIONS.md linha ~2626,
cross-conferidas nesta rodada contra v8/campaign/terraform/{providers,
main}.tf -- client_ca_central_1_a/b sao DUAS instancias SEPARADAS,
cada client_l0*/_us_east_1/_ap_northeast_1 e um L0 co-localizado com
seu PROPRIO servidor). As 3 variantes L0 (uma por servidor) precisam
de rotulo DISTINTO desde a origem -- senao colidiriam em todo dict/
nome de arquivo hoje indexado so por `route` (nomes de captura,
NOMINAL_RTT_MS, criterio7_rtt_por_rota.json etc.). As outras 5 rotas
(L123/L219/L325/L14/L30) ja sao unicas globalmente -- mesmo nome que
a v8 real e o piloto ja usam, nunca renomeadas.
"""
from __future__ import annotations

import re
from pathlib import Path

# As 7 regioes reais (confirmadas identicas a campanha real da v8,
# v8/campaign/terraform/providers.tf, e a `terraform_campanha_
# oficial/providers.tf` desta v9 -- ver _regions_from_terraform()
# abaixo, que prova isso automaticamente em teste).
CAMPAIGN_REGIONS = [
    "sa-east-1", "us-east-1", "ap-northeast-1",
    "ca-central-1", "eu-north-1", "ap-southeast-1", "ap-northeast-2",
]

# As 3 regioes que hospedam um SERVIDOR (subconjunto de CAMPAIGN_REGIONS).
CAMPAIGN_SERVERS = ["sa-east-1", "us-east-1", "ap-northeast-1"]

# rota -> servidor que a atende. L0-<regiao> = co-localizado com o
# PROPRIO servidor daquela regiao (3 instancias distintas); as outras
# 5 sao cross-region, cada uma servida por UM servidor so.
CAMPAIGN_ROUTE_SERVER = {
    "L0-sa-east-1": "sa-east-1", "L123": "sa-east-1", "L219": "sa-east-1", "L325": "sa-east-1",
    "L0-us-east-1": "us-east-1", "L14": "us-east-1",
    "L0-ap-northeast-1": "ap-northeast-1", "L30": "ap-northeast-1",
}

CAMPAIGN_ROUTES = list(CAMPAIGN_ROUTE_SERVER.keys())

# Tabela de equivalencia rotulo <-> cenario, pra tese (pedido
# explicito do Luciano, item 3) -- RTT NOMINAL (ms) por rota. Os
# numeros medidos reais (nao so o nominal) estao documentados em
# DECISIONS.md linha ~3699-3705 (L123~122.9ms, L219~219.9ms,
# L325~330.3ms, L14~15.4ms, L30~32.3ms -- "distancia geografica
# real"; L0-* ~0.14-0.18ms -- "co-localizacao real").
CAMPAIGN_NOMINAL_RTT_MS = {
    "L0-sa-east-1": 0, "L123": 123, "L219": 219, "L325": 325,
    "L0-us-east-1": 0, "L14": 14,
    "L0-ap-northeast-1": 0, "L30": 30,
}

# Tabela de equivalencia completa rotulo -> (servidor, regiao do
# cliente, RTT nominal, colocalizado) -- a mesma informacao acima,
# montada num unico lugar legivel/exportavel pra documentacao da tese
# (item 3 do pedido do Luciano: "uma tabela de verdade, nao so
# implicita no codigo").
CAMPAIGN_SCENARIO_TABLE = [
    {"rota": "L0-sa-east-1", "servidor": "sa-east-1", "regiao_cliente": "sa-east-1", "nominal_rtt_ms": 0, "colocalizado": True},
    {"rota": "L123", "servidor": "sa-east-1", "regiao_cliente": "ca-central-1", "nominal_rtt_ms": 123, "colocalizado": False},
    {"rota": "L219", "servidor": "sa-east-1", "regiao_cliente": "eu-north-1", "nominal_rtt_ms": 219, "colocalizado": False},
    {"rota": "L325", "servidor": "sa-east-1", "regiao_cliente": "ap-southeast-1", "nominal_rtt_ms": 325, "colocalizado": False},
    {"rota": "L0-us-east-1", "servidor": "us-east-1", "regiao_cliente": "us-east-1", "nominal_rtt_ms": 0, "colocalizado": True},
    {"rota": "L14", "servidor": "us-east-1", "regiao_cliente": "ca-central-1", "nominal_rtt_ms": 14, "colocalizado": False},
    {"rota": "L0-ap-northeast-1", "servidor": "ap-northeast-1", "regiao_cliente": "ap-northeast-1", "nominal_rtt_ms": 0, "colocalizado": True},
    {"rota": "L30", "servidor": "ap-northeast-1", "regiao_cliente": "ap-northeast-2", "nominal_rtt_ms": 30, "colocalizado": False},
]

_TERRAFORM_CAMPANHA_DIR = Path(__file__).resolve().parents[2] / "terraform_campanha_oficial"


def regions_from_terraform(tf_dir: Path | str | None = None) -> list[str]:
    """Extrai as regioes REAIS declaradas em terraform_campanha_
    oficial/providers.tf (uma por bloco `provider "aws" { region =
    "..." }`) -- usado pelo teste que prova que CAMPAIGN_REGIONS
    nunca diverge do Terraform de verdade (pedido do Luciano, item 2:
    fecha o gap fail-closed da Decisao 96 pras 7 regioes reais)."""
    tf_dir = Path(tf_dir) if tf_dir else _TERRAFORM_CAMPANHA_DIR
    providers_path = tf_dir / "providers.tf"
    text = providers_path.read_text(encoding="utf-8")
    return re.findall(r'region\s*=\s*"([a-z0-9-]+)"', text)

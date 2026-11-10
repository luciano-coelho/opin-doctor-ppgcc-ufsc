"""Achado real ao preparar o ensaio de 64 execucoes: o formato do
`terraform output -json inventory` real (terraform_campanha_oficial/
outputs.tf, rotulo de cliente "{servidor}/{rota}") nunca batia com o
formato FLAT que `orchestrator.py SSHExecutor` espera (chave = rotulo
global da rota, "L0-sa-east-1"/"L123"/...) -- escrito pelo BLOCO A em
isolamento, nunca cross-conferido. Este teste fixa o contrato exato
contra os dados REAIS de `outputs.tf` (copiados aqui byte a byte, nao
reinventados)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import campanha_inventory_adapter as adapter  # noqa: E402
import campaign_topology as ct  # noqa: E402

# Mesma estrutura EXATA de terraform_campanha_oficial/outputs.tf
# (output "inventory"), so com IPs ficticios -- campos reais presentes
# (role/region/routes extras, que o adapter tem que ignorar sem erro).
_TF_INVENTORY = {
    "control": {"role": "control", "public_ip": "1.1.1.1", "private_ip": "10.0.0.1"},
    "servers": {
        "sa-east-1": {"region": "sa-east-1", "public_ip": "2.2.2.1", "private_ip": "10.0.1.1",
                       "routes": ["L0", "L123", "L219", "L325"]},
        "us-east-1": {"region": "us-east-1", "public_ip": "2.2.2.2", "private_ip": "10.0.1.2",
                       "routes": ["L0", "L14"]},
        "ap-northeast-1": {"region": "ap-northeast-1", "public_ip": "2.2.2.3", "private_ip": "10.0.1.3",
                             "routes": ["L0", "L30"]},
    },
    "clients": {
        "sa-east-1/L0": {"server": "sa-east-1", "colocated": True, "public_ip": "3.3.3.1", "private_ip": "10.0.2.1"},
        "sa-east-1/L123": {"server": "sa-east-1", "colocated": False, "region": "ca-central-1",
                             "public_ip": "3.3.3.2", "private_ip": "10.0.2.2"},
        "sa-east-1/L219": {"server": "sa-east-1", "colocated": False, "region": "eu-north-1",
                             "public_ip": "3.3.3.3", "private_ip": "10.0.2.3"},
        "sa-east-1/L325": {"server": "sa-east-1", "colocated": False, "region": "ap-southeast-1",
                             "public_ip": "3.3.3.4", "private_ip": "10.0.2.4"},
        "us-east-1/L0": {"server": "us-east-1", "colocated": True, "public_ip": "3.3.3.5", "private_ip": "10.0.2.5"},
        "us-east-1/L14": {"server": "us-east-1", "colocated": False, "region": "ca-central-1",
                            "public_ip": "3.3.3.6", "private_ip": "10.0.2.6"},
        "ap-northeast-1/L0": {"server": "ap-northeast-1", "colocated": True, "public_ip": "3.3.3.7", "private_ip": "10.0.2.7"},
        "ap-northeast-1/L30": {"server": "ap-northeast-1", "colocated": False, "region": "ap-northeast-2",
                                 "public_ip": "3.3.3.8", "private_ip": "10.0.2.8"},
    },
}


def test_adapt_produz_as_8_chaves_globais_da_campaign_topology():
    result = adapter.adapt(_TF_INVENTORY)
    assert set(result["clients"].keys()) == set(ct.CAMPAIGN_ROUTES)


def test_adapt_preserva_ips_e_colocated_corretos():
    result = adapter.adapt(_TF_INVENTORY)
    assert result["clients"]["L0-sa-east-1"] == {"public_ip": "3.3.3.1", "private_ip": "10.0.2.1", "colocated": True}
    assert result["clients"]["L123"] == {"public_ip": "3.3.3.2", "private_ip": "10.0.2.2", "colocated": False}
    assert result["clients"]["L0-us-east-1"]["colocated"] is True
    assert result["clients"]["L30"]["public_ip"] == "3.3.3.8"


def test_adapt_servidores_e_controle():
    result = adapter.adapt(_TF_INVENTORY)
    assert set(result["servers"].keys()) == set(ct.CAMPAIGN_SERVERS)
    assert result["servers"]["sa-east-1"] == {"public_ip": "2.2.2.1", "private_ip": "10.0.1.1"}
    assert result["control"] == {"public_ip": "1.1.1.1", "private_ip": "10.0.0.1"}


def test_mutante_chave_errada_do_terraform_e_pego():
    """Mutante: usasse o rotulo da campaign_topology direto como chave
    do terraform (sem a formula servidor/rota) -- nunca bateria com o
    formato real, tem que levantar RuntimeError, nunca silenciar."""
    quebrado = dict(_TF_INVENTORY)
    quebrado["clients"] = dict(_TF_INVENTORY["clients"])
    del quebrado["clients"]["sa-east-1/L123"]  # simula o formato errado faltando
    try:
        adapter.adapt(quebrado)
        assert False, "deveria levantar RuntimeError com a chave L123/sa-east-1-L123 ausente"
    except RuntimeError as e:
        assert "sa-east-1/L123" in str(e)

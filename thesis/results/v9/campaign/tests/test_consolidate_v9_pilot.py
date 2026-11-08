"""Testes da consolidacao final do piloto (Decisao 75, item 3/4) --
usa a saida REAL de `orchestrator.run_pilot(LocalExecutor(), ...)`
como fixture (nunca dados fake construidos a mao), pra exercitar
`evaluate_criteria.py` contra um caminho de dados de verdade, so sem
rede/SSH."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import orchestrator as orch  # noqa: E402
import consolidate_v9_pilot as cvp  # noqa: E402


@pytest.fixture
def collected_dir(tmp_path):
    """Roda run_pilot local de verdade (grade oficial completa, 60
    execucoes + 12 capturas dedicadas) e devolve o diretorio de
    saida, exatamente como `collect_artifacts.py` teria entregue
    apos um pull real (aqui, sem rede nenhuma -- o LocalExecutor ja
    escreve direto em disco)."""
    out_dir = tmp_path / "coletado"
    orch.run_pilot(orch.LocalExecutor(), seed=1, out_dir=out_dir)
    return out_dir


def test_run_evaluate_criteria_reaproveita_as_7_chamadas_reais(collected_dir):
    results = cvp.run_evaluate_criteria(collected_dir)
    assert [r["criterion"] for r in results] == [1, 2, 3, 4, 5, 6, 7]
    # criterios 2/3/7 nunca tem arquivo dedicado neste piloto local --
    # tem que reprovar com nota clara, nunca quebrar.
    c2 = next(r for r in results if r["criterion"] == 2)
    assert c2["pass"] is False
    assert "nao encontrado" in c2["note"] or "aws-dir" in c2["note"]


def test_consolidate_escreve_raw_json_e_markdown(collected_dir, tmp_path):
    out_dir = tmp_path / "dados_oficiais" / "smoke-teste"
    result = cvp.consolidate(collected_dir, out_dir, run_label="smoke-teste")

    assert (out_dir / "raw" / "manifest.json").is_file()
    assert (out_dir / "raw" / "piloto_combined.log").is_file()
    assert (out_dir / "criteria_evaluation.json").is_file()
    assert (out_dir / "RELATORIO_PILOTO.md").is_file()

    saved = json.loads((out_dir / "criteria_evaluation.json").read_text(encoding="utf-8"))
    assert saved == result["criteria_results"]

    report_text = (out_dir / "RELATORIO_PILOTO.md").read_text(encoding="utf-8")
    assert "smoke-teste" in report_text
    assert "| 1 |" in report_text and "| 4 |" in report_text  # tabela dos 7 criterios
    assert "Criterio 2 (initcwnd real): arquivo nao encontrado" in report_text  # secao de reprovados


def test_consolidate_falha_alto_se_combined_log_ausente(tmp_path):
    collected_dir = tmp_path / "vazio"
    collected_dir.mkdir()
    with pytest.raises(RuntimeError, match="nao encontrado"):
        cvp.consolidate(collected_dir, tmp_path / "out", run_label="x")


def test_consolidate_resultado_geral_reflete_all_pass(collected_dir, tmp_path):
    result = cvp.consolidate(collected_dir, tmp_path / "out", run_label="smoke-teste")
    # smoke gate local: criterios 1/4/5/6 devem passar (dados locais
    # coerentes); 2/3/7 nunca tem arquivo dedicado aqui -- entao o
    # resultado geral tem que ser False (nunca omite a ausencia).
    assert result["all_criteria_pass"] is False
    passing = {r["criterion"] for r in result["criteria_results"] if r["pass"]}
    assert {1, 4, 5, 6} <= passing

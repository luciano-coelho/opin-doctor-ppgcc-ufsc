"""Regressao OBRIGATORIA (pedido do Luciano -- piloto assimetrico da
conta nova, item 3 da autorizacao): a edicao que acrescenta `cells` a
`run_pilot`/`--cells` a CLI tem que ser PROVADA, nunca so afirmada,
em dois sentidos:

  (a) SEM `cells` (ou SEM `--cells`), o comportamento e byte a byte
      IDENTICO ao codigo ANTERIOR a esta mudanca -- comparado por
      DIFF de verdade contra `_orchestrator_pre_cells_baseline.py`
      (copia congelada de `orchestrator.py` extraida de
      `git show 3c92fbb6:...` -- o commit imediatamente anterior a
      esta edicao -- nunca editada depois, mesmo padrao ja
      estabelecido por `_orchestrator_pre_generalization_baseline.py`/
      `test_pilot_regression_n_servidores.py`), nunca so "parece
      igual".

  (b) COM `cells`, gera EXATAMENTE o subconjunto pedido (as 6 celulas
      do piloto assimetrico: 4 perfis em L0-sa-east-1, classico e
      hibrido-and em L14) x `n_per_profile` execucoes -- nunca um
      produto cartesiano simetrico de profiles x routes.

Ambos usam `LocalExecutor` (sem SSH, sem AWS, sem Docker -- mesmo
padrao hermetico dos outros 374+ testes de `run_pilot` da suite) e
`out_dir` num `tmp_path` proprio por teste."""
import importlib.util
import json
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_baseline_module():
    """Carrega a copia congelada (pre-`cells`) sob um nome de modulo
    PROPRIO -- nunca colide com `orchestrator` atual nem com
    `orchestrator_baseline` (a baseline pre-generalizacao, de uma
    regressao anterior e nao relacionada)."""
    baseline_path = Path(__file__).resolve().parent / "_orchestrator_pre_cells_baseline.py"
    spec = importlib.util.spec_from_file_location("orchestrator_pre_cells", baseline_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["orchestrator_pre_cells"] = module
    spec.loader.exec_module(module)
    return module


_BASELINE = _load_baseline_module()
import orchestrator as _CURRENT  # noqa: E402 -- o modulo atual, com `cells`


# Grade pequena e deterministica so pra esta regressao -- nao precisa
# ser a grade real da campanha (8 x 4) pra provar equivalencia da
# MECANICA de filtragem; usa nomes de rota/perfil REAIS (nunca
# inventados) pra qualquer assert incidental (ex. CurveID por perfil)
# continuar valido nos dois modulos.
_EQUIV_ROUTES = ["L0-sa-east-1", "L14"]
_EQUIV_PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
_EQUIV_SEED = 20261115
_EQUIV_N_PER_PROFILE = 1


def _run_no_filter(module, out_dir):
    executor = module.LocalExecutor()
    return module.run_pilot(
        executor, _EQUIV_SEED, out_dir, n_per_profile=_EQUIV_N_PER_PROFILE,
        routes=list(_EQUIV_ROUTES), profiles=list(_EQUIV_PROFILES),
        skip_dedicated_captures=True,
    )


def _strip_volatile(manifest):
    """Remove campos que variam por natureza entre duas chamadas
    (timestamps reais de `datetime.now()`) -- tudo que importa pra
    provar equivalencia de ORQUESTRACAO (cardinalidade/ordem/rotas/
    perfis) fica."""
    m = dict(manifest)
    for key in ("generated_at_utc", "window_start_utc", "window_end_utc",
                "combined_log", "calls_json", "criterio6_json", "capturas_dir",
                "runs_raw_dir", "aquecimento_log", "aquecimento_calls_json"):
        m.pop(key, None)
    return m


def test_sem_filtro_e_byte_a_byte_identico_ao_codigo_anterior(tmp_path):
    """Prova o item (a): nenhuma linha nova de `cells` e exercitada
    quando `cells` nao e passado -- o modulo ATUAL (que tem o
    parametro novo, mas chamado sem ele) produz o MESMO manifesto que
    o modulo ANTERIOR (que nem tem o parametro)."""
    out_old = tmp_path / "old"
    out_new = tmp_path / "new"
    old_manifest = _strip_volatile(_run_no_filter(_BASELINE, out_old))
    new_manifest = _strip_volatile(_run_no_filter(_CURRENT, out_new))

    # `cells_filter` e um campo NOVO que o modulo antigo nem escreve --
    # comparado separadamente (tem que ser None no atual, ausente no
    # antigo), removido antes do diff do resto pra nao mascarar uma
    # DIFERENCA REAL em qualquer outro campo.
    assert "cells_filter" not in old_manifest
    assert new_manifest.pop("cells_filter") is None
    assert old_manifest == new_manifest, (
        "manifesto SEM --cells divergiu do codigo anterior -- a edicao "
        "alterou comportamento default, nao so adicionou um caminho novo"
    )

    # route_orders (ordem aleatoria por rota) e a prova mais direta de
    # que o consumo do `rng` nao mudou: mesma seed, mesma ordem.
    assert old_manifest["route_orders"] == new_manifest["route_orders"]
    assert old_manifest["total_execucoes"] == new_manifest["total_execucoes"] \
        == len(_EQUIV_ROUTES) * len(_EQUIV_PROFILES) * _EQUIV_N_PER_PROFILE
    assert old_manifest["expected_total"] == new_manifest["expected_total"]

    old_calls = json.loads((out_old / "piloto_calls.json").read_text(encoding="utf-8"))
    new_calls = json.loads((out_new / "piloto_calls.json").read_text(encoding="utf-8"))
    old_pairs = [(c["profile"], c["route"], c["run"]) for c in old_calls]
    new_pairs = [(c["profile"], c["route"], c["run"]) for c in new_calls]
    assert old_pairs == new_pairs, "ordem/cardinalidade de (profile, route, run) divergiu"


# As 6 celulas REAIS do piloto assimetrico da conta nova (Decisao do
# Luciano): 4 perfis em L0-sa-east-1, so classico e hibrido-and em
# L14 -- NUNCA um produto cartesiano simetrico (profiles x routes
# daria 8, nao 6).
_PILOT_CELLS = [
    ("classico", "L0-sa-east-1"), ("pqc", "L0-sa-east-1"),
    ("hibrido-v8", "L0-sa-east-1"), ("hibrido-and", "L0-sa-east-1"),
    ("classico", "L14"), ("hibrido-and", "L14"),
]
_PILOT_N_PER_CELL = 3


def test_com_filtro_gera_exatamente_as_6_celulas_do_piloto(tmp_path):
    """Prova o item (b): passando `cells` com as 6 celulas reais e
    `profiles`/`routes` COMPLETOS (como `main()` --campaign sempre
    passa, independente de --cells), o resultado e EXATAMENTE 6 x 3 =
    18 execucoes, nunca 8 x 3 = 24 (produto cartesiano completo) nem
    qualquer outro numero."""
    out_dir = tmp_path / "piloto_assimetrico"
    executor = _CURRENT.LocalExecutor()
    manifest = _CURRENT.run_pilot(
        executor, _EQUIV_SEED, out_dir, n_per_profile=_PILOT_N_PER_CELL,
        routes=list(_EQUIV_ROUTES) + ["L123", "L219", "L30", "L325", "L0-us-east-1", "L0-ap-northeast-1"],
        profiles=list(_EQUIV_PROFILES), skip_dedicated_captures=True,
        cells=list(_PILOT_CELLS),
    )

    assert manifest["total_execucoes"] == 18
    assert manifest["expected_total"] == 18
    assert manifest["total_capturas"] == 6
    assert manifest["cells_filter"] == sorted(f"{p}:{r}" for (p, r) in _PILOT_CELLS)

    calls = json.loads((out_dir / "piloto_calls.json").read_text(encoding="utf-8"))
    assert len(calls) == 18
    seen_cells = {}
    for c in calls:
        key = (c["profile"], c["route"])
        seen_cells[key] = seen_cells.get(key, 0) + 1
    assert seen_cells == {cell: _PILOT_N_PER_CELL for cell in _PILOT_CELLS}
    # Nenhuma rota fora das 2 que aparecem em `cells` foi tocada --
    # prova que o filtro de `routes` (no topo de run_pilot) funcionou,
    # nao so o skip dentro do laco.
    assert set(manifest["route_orders"].keys()) == {"L0-sa-east-1", "L14"}


def test_cells_invalido_nao_produz_execucoes_fantasmas(tmp_path):
    """Uma celula com rota que nunca aparece em `routes` simplesmente
    nunca roda (routes e o universo; cells so FILTRA dentro dele) --
    nenhuma excecao, nenhuma execucao fantasma fora do universo
    passado. Documenta o comportamento real, nao uma validacao nova."""
    out_dir = tmp_path / "cells_fora_do_universo"
    executor = _CURRENT.LocalExecutor()
    manifest = _CURRENT.run_pilot(
        executor, _EQUIV_SEED, out_dir, n_per_profile=1,
        routes=["L0-sa-east-1"], profiles=list(_EQUIV_PROFILES),
        skip_dedicated_captures=True,
        cells=[("classico", "L0-sa-east-1"), ("classico", "L14")],
    )
    assert manifest["total_execucoes"] == 1
    assert set(manifest["route_orders"].keys()) == {"L0-sa-east-1"}

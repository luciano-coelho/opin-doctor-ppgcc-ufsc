"""
Generates three separate box-and-whisker plots (matplotlib/seaborn) of
T_fluxo across the v5 latency batch -- one PNG per profile (Classic, PQC,
Hybrid), each with that profile's 6 scenario boxes, with the 10
individual raw values overlaid as jittered points per box.

Revision 3 -- superseding both the single 18-box panel (cluttered) and
the three-subplots-in-one-file layout: the user wants three fully
independent image files instead, sharing one color per profile so the
three read as a set when viewed side by side, but with no other coupling
(no shared axis object, no shared figure/canvas).

Reads ONLY the raw per-run JSONs (runs/run01..10.json) -- never
median_metrics.json -- per this project's own JSON=source/MD=derived
convention (thesis/results/v5/latency/DECISIONS.md, Decision 5): this
script, and therefore every figure, is fully regenerable from the raw
data alone, with no new flow execution and no dependency on any already-
aggregated file. The warmup run (run00_warmup.json) is intentionally
excluded, matching the batch's own median calculation (Decision 2).

Box statistics (min/Q1/median/Q3/max, whiskers, outliers) are computed by
matplotlib's own boxplot() using the standard 1.5x IQR convention --
nothing here recomputes or overrides that.

Color: first three slots of the dataviz skill's validated categorical
palette (blue/orange/aqua, light mode) -- these three specifically
validate as an all-pairs-safe set (CVD Delta E >= 8, normal-vision >= 15)
per references/palette.md, not an arbitrary choice, and stay fixed
per-profile across all three files so the set reads consistently even
though each PNG is opened independently. The aqua slot (Hybrid) sits
below the 3:1 contrast floor against a white surface on its own (a
documented WARN, not a fail) -- satisfied here by a dark edge on every
box/point plus the title naming the profile in plain text, so identity
never depends on the fill color's contrast alone.

Usage:
  python plot_latency_boxplot.py
Output:
  thesis/results/v5/latency/boxplot_classico_v5.png
  thesis/results/v5/latency/boxplot_pqc_v5.png
  thesis/results/v5/latency/boxplot_hibrido_v5.png
  (all 300 DPI)
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent.parent
LATENCY_DIR = BASE_DIR / "thesis" / "results" / "v5" / "latency"

SCENARIOS = ["0ms", "14ms", "30ms", "140ms", "225ms", "320ms"]

# folder, display label, output filename, color (first three slots of the
# dataviz skill's validated categorical palette, references/palette.md,
# light mode -- fixed order, never cycled/reassigned).
PROFILES = [
    ("experiment1 - Classic", "Clássico", "boxplot_classico_v5.png", "#2a78d6"),
    ("experiment2 - PQC", "PQC", "boxplot_pqc_v5.png", "#eb6834"),
    ("experiment3 - Hybrid", "Híbrido", "boxplot_hibrido_v5.png", "#1baf7a"),
]
EDGE_COLOR = "#33322f"  # dark neutral edge -- the "relief" for the aqua slot's contrast WARN
YTICKS = [4, 5, 6, 8, 10, 15, 20, 30, 40, 50, 65]


def load_profile_data(folder: str) -> pd.DataFrame:
    """Loads the 10 official t_fluxo_seconds values per scenario for one
    profile, directly from runs/run01.json..run10.json --
    run00_warmup.json is skipped on purpose, exactly like
    median_automation.py's own median excludes it."""
    rows = []
    for scenario in SCENARIOS:
        runs_dir = LATENCY_DIR / folder / scenario / "runs"
        for i in range(1, 11):
            run_path = runs_dir / f"run{i:02d}.json"
            data = json.loads(run_path.read_text(encoding="utf-8"))
            rows.append({"scenario": scenario, "t_fluxo_seconds": data["t_fluxo_seconds"]})
    df = pd.DataFrame(rows)
    expected_rows = len(SCENARIOS) * 10
    assert len(df) == expected_rows, f"expected {expected_rows} raw values, got {len(df)}"
    return df


def build_figure(df: pd.DataFrame, profile_label: str, color: str):
    sns.set_theme(style="white", font_scale=1.0)
    fig, ax = plt.subplots(figsize=(8, 6))

    sns.boxplot(
        data=df, x="scenario", y="t_fluxo_seconds",
        order=SCENARIOS, color=color,
        width=0.55, fliersize=0, linewidth=1.1,
        boxprops=dict(edgecolor=EDGE_COLOR, facecolor=color, alpha=0.55),
        medianprops=dict(color=EDGE_COLOR, linewidth=1.8),
        whiskerprops=dict(color=EDGE_COLOR, linewidth=1.1),
        capprops=dict(color=EDGE_COLOR, linewidth=1.1),
        ax=ax,
    )

    # Individual points, small horizontal jitter for display only --
    # jitter never touches the plotted y-value (T_fluxo) or any
    # statistic; it only spreads otherwise-overlapping markers sideways
    # so all 10 per box stay visible.
    sns.stripplot(
        data=df, x="scenario", y="t_fluxo_seconds",
        order=SCENARIOS, color=color,
        jitter=0.22, size=5, alpha=0.9,
        edgecolor=EDGE_COLOR, linewidth=0.5,
        ax=ax,
    )

    ax.set_yscale("log")
    ax.set_yticks(YTICKS)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_locator(mticker.NullLocator())

    ax.set_xlabel("Cenário de latência de rede injetada", fontsize=11, labelpad=8)
    ax.set_ylabel("T_fluxo (segundos)", fontsize=11, labelpad=8)
    ax.set_title(
        f"Distribuição de T_fluxo — Perfil {profile_label} (v5, 10 execuções por caixa)",
        fontsize=13, fontweight="bold", pad=12, color=EDGE_COLOR,
    )

    ax.grid(axis="y", which="major", color="#d9d8d3", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#8a8880")

    fig.text(
        0.5, 0.01,
        f"Fonte: thesis/results/v5/latency/{{profile}}/*/runs/run01..10.json "
        "(10 valores brutos de T_fluxo por caixa; execução de warmup excluída). "
        "Caixa: mín/Q1/mediana/Q3/máx + outliers (1,5× IQR).",
        ha="center", fontsize=8, color="#6b6a64",
    )

    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def main():
    LATENCY_DIR.mkdir(parents=True, exist_ok=True)
    for folder, label, filename, color in PROFILES:
        df = load_profile_data(folder)
        fig = build_figure(df, label, color)
        out_path = LATENCY_DIR / filename
        fig.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

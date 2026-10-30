"""Closes one of the two go/no-go FAILs (Decision 103, item 5): derives
report_data_v8.json and a markdown table report AUTOMATICALLY from
consolidate_v8.py's own output (consolidated.json) -- never from the
raw run*.json directly (that is consolidate_v8.py's own job, already
tested end to end against real pilot-3 data). This is the v8
counterpart to thesis/scripts/compute_v7_report_data.py, intentionally
narrower in scope for a first version: it reports what consolidate_v8.py
already computes (T_fluxo, OPINsize, handshake fraction, byte terms),
not a re-derivation from scratch.

Usage: python generate_report_data.py <path to consolidated.json's dir>
Writes <that dir>/report_data_v8.json and <that dir>/REPORT_TABLES.md.
"""
import json
import sys
from pathlib import Path


def load(root):
    return json.loads((root / "consolidated.json").read_text(encoding="utf-8"))


def derive_report_data(consolidated):
    """One row per (profile, installation, scenario) cell -- the flat
    shape a paper table/figure actually wants, instead of the nested
    profile->installation->scenario dict consolidate_v8.py keeps for
    its own JSON structure."""
    rows = []
    for profile, by_installation in consolidated["profiles"].items():
        for installation, by_scenario in by_installation.items():
            for scenario, cell in by_scenario.items():
                tf = cell.get("t_fluxo_seconds") or {}
                op = cell.get("opinsize") or {}
                hs = cell.get("mtls_handshake_fraction_of_t_fluxo_pct") or {}
                hs_stats = hs.get("stats") or {}
                rows.append({
                    "profile": profile, "installation": installation, "scenario": scenario,
                    "n": tf.get("n"), "t_fluxo_median_s": tf.get("median"), "t_fluxo_mean_s": tf.get("mean"),
                    "t_fluxo_stdev_s": tf.get("stdev"),
                    "t_fluxo_ci95": tf.get("bootstrap_median_ci95"),
                    "opinsize_bytes": op.get("value_bytes"),
                    "handshake_fraction_pct": hs_stats.get("median"),
                })
    rows.sort(key=lambda r: (r["profile"], r["installation"], r["scenario"]))
    return {
        "source": "consolidated.json (consolidate_v8.py's own output, never re-derived from raw runs here)",
        "rows": rows,
        "cross_profile_t_fluxo_comparisons": consolidated.get("cross_profile_t_fluxo_comparisons"),
    }


def render_markdown_table(report_data):
    lines = ["# Tabelas do artigo (v8) -- geradas automaticamente, não escritas à mão",
             "", "Gerado por `generate_report_data.py` a partir de `consolidated.json`.", "",
             "| perfil | instalação | cenário | n | T_fluxo mediana (s) | IC95% | OPINsize (B) | handshake (%) |",
             "|---|---|---|---|---|---|---|---|"]
    for r in report_data["rows"]:
        ci = r["t_fluxo_ci95"]
        ci_str = f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "n/a"
        med = f"{r['t_fluxo_median_s']:.4f}" if r["t_fluxo_median_s"] is not None else "n/a"
        op = f"{r['opinsize_bytes']:.0f}" if isinstance(r['opinsize_bytes'], (int, float)) else "n/a"
        hs = f"{r['handshake_fraction_pct']:.2f}" if isinstance(r['handshake_fraction_pct'], (int, float)) else "n/a"
        lines.append(f"| {r['profile']} | {r['installation']} | {r['scenario']} | {r['n']} | {med} | {ci_str} | {op} | {hs} |")
    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: generate_report_data.py <dir containing consolidated.json>")
    root = Path(sys.argv[1])
    consolidated = load(root)
    report_data = derive_report_data(consolidated)
    (root / "report_data_v8.json").write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    (root / "REPORT_TABLES.md").write_text(render_markdown_table(report_data), encoding="utf-8")
    print(f"Wrote {root / 'report_data_v8.json'} ({len(report_data['rows'])} rows) and {root / 'REPORT_TABLES.md'}")


if __name__ == "__main__":
    main()

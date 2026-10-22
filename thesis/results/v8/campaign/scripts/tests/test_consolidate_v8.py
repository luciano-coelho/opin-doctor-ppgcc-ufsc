"""End-to-end test of consolidate_v8.py (Item 2 of the 2026-10-21 light
flow check): builds a real campaign-shaped `runs/run{NN}.json` +
`runs/run{NN}.calls.jsonl` tree from the light flow check's own real
per-profile captures (tests/fixtures/light_flow_check_2026-10-21/), runs
the generator against it, and checks the numbers it produces against
v7's own report_data_v7.json -- the same cross-check METRICS_COVERAGE.md
already did by hand.

The one field the real captures cannot supply (mTLS handshake bytes --
no pcap extractor exists yet) is injected ONLY for the classic/L0 run,
as an explicitly tagged `_FIXTURE` value, so the "complete OPINsize"
code path gets exercised once without claiming pqc/hybrid have that
data too.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import consolidate_v8 as cv8

FIXTURES = Path(__file__).parent / "fixtures" / "light_flow_check_2026-10-21"
PROFILE_FIXTURE_FILE = {
    "classic": "classic_real_local_flow.json",
    "pqc": "pqc_real_local_flow.json",
    "hybrid": "hybrid_real_local_flow.json",
}
# v7's own report_data_v7.json figures (read directly in this session) --
# the ground truth every "covered" row in METRICS_COVERAGE.md was checked
# against.
V7_TERM_JWT = {"classic": 37263, "pqc": 151321, "hybrid": 200567}
V7_TERM_JWK = {"classic": 512, "pqc": 3904, "hybrid": 4416}
V7_TERM_PKI = {"classic": 8440, "pqc": 32028, "hybrid": 37356}
V7_OPINSIZE = {"classic": 76929, "pqc": 322895, "hybrid": 350477}
V7_HANDSHAKE_P50 = {"classic": 5119, "pqc": 22607, "hybrid": 18023}  # used only as the classic fixture


def _write_run(scenario_dir, run_name, flow_json, inject_fixture_handshake=False):
    data = json.loads(flow_json.read_text(encoding="utf-8"))
    calls = data.pop("calls")
    result = data  # everything else (t_fluxo_seconds, call_count, retries, ...) IS the result dict
    if inject_fixture_handshake:
        result["gateway_metrics"] = {
            "handshake_bytes": {
                "p50_bytes": V7_HANDSHAKE_P50["classic"],
                "count": 6,
                "_FIXTURE": ("synthetic placeholder -- no pcap extractor exists yet for v8 "
                             "(METRICS_COVERAGE.md); value copied from v7's own classic figure "
                             "ONLY to exercise consolidate_v8.py's complete-OPINsize arithmetic "
                             "in this test, never a real v8 measurement."),
            }
        }
    runs_dir = scenario_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{run_name}.json").write_text(json.dumps({
        "started_at_utc": result.get("generated_at"),
        "window": 1, "window_local_run_index": 1,
        "server": "sa-east-1", "client": "sa-east-1",
        "result": result,
    }, indent=2), encoding="utf-8")
    with open(runs_dir / f"{run_name}.calls.jsonl", "w", encoding="utf-8") as f:
        for call in calls:
            f.write(json.dumps(call) + "\n")


def _build_tree(root):
    for profile, fname in PROFILE_FIXTURE_FILE.items():
        exp_dir = root / cv8.PROFILE_TO_EXPERIMENT_DIR[profile]
        scenario_dir = exp_dir / "sa-east-1" / "L0"
        _write_run(scenario_dir, "run01", FIXTURES / fname,
                   inject_fixture_handshake=(profile == "classic"))


def test_consolidate_v8_end_to_end(tmp_path):
    v8_latency_root = tmp_path / "v8" / "latency"
    _build_tree(v8_latency_root)

    data = cv8.build_consolidated(v8_latency_root)

    for profile in ("classic", "pqc", "hybrid"):
        m = data["profiles"][profile]["sa-east-1"]["L0"]

        assert m["call_count"] == [42], f"{profile}: call_count mismatch"
        assert m["n_jwt"] == [28], f"{profile}: n_jwt mismatch"
        assert m["n_jwk"] == [2], f"{profile}: n_jwk mismatch"
        assert m["n_pki"] == [4], f"{profile}: n_pki mismatch"

        assert m["term_jwt"]["median"] == V7_TERM_JWT[profile], (
            f"{profile}: term_jwt {m['term_jwt']['median']} != v7's {V7_TERM_JWT[profile]}")
        assert m["term_jwk"]["median"] == V7_TERM_JWK[profile], (
            f"{profile}: term_jwk {m['term_jwk']['median']} != v7's {V7_TERM_JWK[profile]}")
        assert m["term_pki"]["median"] == V7_TERM_PKI[profile], (
            f"{profile}: term_pki {m['term_pki']['median']} != v7's {V7_TERM_PKI[profile]}")

    classic = data["profiles"]["classic"]["sa-east-1"]["L0"]
    assert classic["opinsize"]["status"] == "complete"
    assert classic["opinsize"]["value_bytes"] == V7_OPINSIZE["classic"], (
        f"classic OPINsize (with fixture handshake term) "
        f"{classic['opinsize']['value_bytes']} != v7's {V7_OPINSIZE['classic']}")

    for profile in ("pqc", "hybrid"):
        m = data["profiles"][profile]["sa-east-1"]["L0"]
        assert m["opinsize"]["status"] == "incomplete_missing_term_handshake"
        expected_partial = V7_TERM_JWT[profile] + V7_TERM_JWK[profile] + V7_TERM_PKI[profile]
        assert m["opinsize"]["partial_value_bytes_excl_handshake"] == expected_partial, (
            f"{profile}: partial OPINsize {m['opinsize']['partial_value_bytes_excl_handshake']} "
            f"!= expected {expected_partial}")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "consolidated.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    report = cv8.render_report(data)
    (out_dir / "CONSOLIDATED_REPORT.md").write_text(report, encoding="utf-8")

    assert "OPINsize: 76929 bytes" in report.replace(".0 bytes", " bytes") or "76929" in report
    assert "INCOMPLETE" in report  # pqc/hybrid's own missing-handshake note must surface in the human report
    assert (out_dir / "consolidated.json").stat().st_size > 0

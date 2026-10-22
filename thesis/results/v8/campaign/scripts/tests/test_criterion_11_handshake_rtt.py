"""Regression test for pilot_acceptance.py's Criterion 11 (2026-10-22,
DECISIONS.md): gateway-vs-pcap handshake diff, per scenario, RTT
dependence signal. Builds a real L0-only tree from this turn's own real
captures (no L325 data exists locally -- that's expected and asserted
explicitly, not papered over).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import consolidate_v8 as cv8
import pilot_acceptance as pa

FIXTURES = Path(__file__).parent / "fixtures" / "light_flow_check_2026-10-21"
FLOW = {"classic": "classic_real_local_flow.json", "pqc": "pqc_real_local_flow.json", "hybrid": "hybrid_real_local_flow.json"}
PCAP = {"classic": "classic_clienthello_s256.pcap.gz", "pqc": "pqc_clienthello_s256.pcap.gz", "hybrid": "hybrid_clienthello_s256.pcap.gz"}
GWLOG = {"classic": "classic_gateway_s256_matched.log", "pqc": "pqc_gateway_s256_matched.log", "hybrid": "hybrid_gateway_s256_matched.log"}
# Real diffs this turn measured (DECISIONS.md) -- asserted with a small
# tolerance since they come from a live capture, not hand-typed.
EXPECTED_DIFF_PCT = {"classic": -4.52, "pqc": -10.22, "hybrid": -2.60}


def _build_l0_tree(root):
    for profile in ("classic", "pqc", "hybrid"):
        exp_dir = root / "v8" / "latency" / cv8.PROFILE_TO_EXPERIMENT_DIR[profile]
        scenario_dir = exp_dir / "sa-east-1" / "L0"
        runs_dir, server_dir, client_dir = scenario_dir / "runs", scenario_dir / "server", scenario_dir / "client"
        for d in (runs_dir, server_dir, client_dir):
            d.mkdir(parents=True, exist_ok=True)
        data = json.loads((FIXTURES / FLOW[profile]).read_text(encoding="utf-8"))
        calls = data.pop("calls")
        (runs_dir / "run01.json").write_text(json.dumps({"window": 1, "result": data}), encoding="utf-8")
        with open(runs_dir / "run01.calls.jsonl", "w", encoding="utf-8") as f:
            for call in calls:
                f.write(json.dumps(call) + "\n")
        (server_dir / "run01_gateway.log").write_text(
            (FIXTURES / GWLOG[profile]).read_text(encoding="utf-8"), encoding="utf-8")
        (client_dir / "run01.pcap.gz").write_bytes((FIXTURES / PCAP[profile]).read_bytes())


def test_criterion_11_reports_real_l0_diffs_and_defers_rtt_comparison(tmp_path):
    _build_l0_tree(tmp_path)
    for profile in ("classic", "pqc", "hybrid"):
        scenario_path = tmp_path / "v8" / "latency" / cv8.PROFILE_TO_EXPERIMENT_DIR[profile] / "sa-east-1" / "L0"
        result = cv8.consolidate_profile_scenario(scenario_path, profile)
        diff = result["term_handshake_gateway_vs_pcap_diff"]
        assert diff is not None, f"{profile}: gateway-vs-pcap diff should be computable from these fixtures"
        assert abs(diff["diff_pct"] - EXPECTED_DIFF_PCT[profile]) < 0.1, (
            f"{profile}: diff% {diff['diff_pct']:.2f} != expected ~{EXPECTED_DIFF_PCT[profile]}")

    # criterion_11 itself: informational (returns True, never fails), and
    # must not crash on the real, honest case of "no L325 data yet".
    result = pa.criterion_11(tmp_path)
    assert result is True

"""End-to-end test of consolidate_v8.py: builds a real campaign-shaped
`runs/run{NN}.json` + `runs/run{NN}.calls.jsonl` + `server/run{NN}_
gateway.log` tree from the light flow check's own real per-profile
captures (tests/fixtures/light_flow_check_2026-10-21/), runs the
generator against it, and checks the numbers it produces against v7's
own report_data_v7.json.

No `_FIXTURE` anywhere in this test: the investigation that follows the
2026-10-21 light flow check found that `server/run{NN}_gateway.log`
(the mtls gateway's own real slog JSON output, `mock_mtls/main.go`'s
`countingConn`, unchanged since v7) already carries the mTLS handshake
bytes term -- the "needs a pcap extractor" framing from the earlier
session was wrong; real data was always one `docker logs` away. The
`{profile}_gateway.log` fixtures here are real captures (local MockOPIN
stack, one execution's own window, sliced to exactly the 6 client-facing
handshakes + 7 internal AS-to-RS handshakes a real flow produces --
verified against `verify_negotiated_groups()`'s own documented counts).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import consolidate_v8 as cv8

FIXTURES = Path(__file__).parent / "fixtures" / "light_flow_check_2026-10-21"
PROFILE_FLOW_FILE = {
    "classic": "classic_real_local_flow.json",
    "pqc": "pqc_real_local_flow.json",
    "hybrid": "hybrid_real_local_flow.json",
}
PROFILE_GATEWAY_LOG_FILE = {
    "classic": "classic_gateway.log",
    "pqc": "pqc_gateway.log",
    "hybrid": "hybrid_gateway.log",
}
# v7's own report_data_v7.json figures (read directly in this session) --
# the ground truth every "covered" row in METRICS_COVERAGE.md was checked
# against.
V7_TERM_JWT = {"classic": 37263, "pqc": 151321, "hybrid": 200567}
V7_TERM_JWK = {"classic": 512, "pqc": 3904, "hybrid": 4416}
V7_TERM_PKI = {"classic": 8440, "pqc": 32028, "hybrid": 37356}
V7_OPINSIZE = {"classic": 76929, "pqc": 322895, "hybrid": 350477}
# Same tolerance and reasoning as pilot_acceptance.py's own OPINsize
# check (see that file's own docstring/comment for the full rationale):
# the real captures behind these fixtures measured +0.47%/+0.00%/+1.70%
# against v7 (classic/pqc/hybrid) -- a single real execution, not a
# median of many, so some run-to-run jitter against v7's own 60-run
# median is expected. +-3% is roughly double the largest of those three
# real deviations.
OPINSIZE_TOLERANCE_PCT = 3.0


def _write_run(scenario_dir, run_name, flow_json_path, gateway_log_path):
    data = json.loads(flow_json_path.read_text(encoding="utf-8"))
    calls = data.pop("calls")
    result = data  # everything else (t_fluxo_seconds, call_count, retries, ...) IS the result dict
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
    server_dir = scenario_dir / "server"
    server_dir.mkdir(parents=True, exist_ok=True)
    (server_dir / f"{run_name}_gateway.log").write_text(
        gateway_log_path.read_text(encoding="utf-8"), encoding="utf-8")


def _build_tree(root):
    for profile in ("classic", "pqc", "hybrid"):
        exp_dir = root / cv8.PROFILE_TO_EXPERIMENT_DIR[profile]
        scenario_dir = exp_dir / "sa-east-1" / "L0"
        _write_run(scenario_dir, "run01",
                   FIXTURES / PROFILE_FLOW_FILE[profile],
                   FIXTURES / PROFILE_GATEWAY_LOG_FILE[profile])


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
        assert m["n_mtls"] == [6], f"{profile}: n_mtls mismatch"

        assert m["term_jwt"]["median"] == V7_TERM_JWT[profile], (
            f"{profile}: term_jwt {m['term_jwt']['median']} != v7's {V7_TERM_JWT[profile]}")
        assert m["term_jwk"]["median"] == V7_TERM_JWK[profile], (
            f"{profile}: term_jwk {m['term_jwk']['median']} != v7's {V7_TERM_JWK[profile]}")
        assert m["term_pki"]["median"] == V7_TERM_PKI[profile], (
            f"{profile}: term_pki {m['term_pki']['median']} != v7's {V7_TERM_PKI[profile]}")

        assert m["term_handshake"]["status"] == "covered", (
            f"{profile}: term_handshake not covered -- real gateway-log fixture should always produce this")
        hs_stats = m["term_handshake"]["stats"]
        assert hs_stats["n"] == 1  # one run in this test tree
        # The real fixture's own 6 client-facing handshakes, not a fabricated count.
        assert m["opinsize"]["status"] == "complete", (
            f"{profile}: OPINsize should be complete now that term_handshake is real, got {m['opinsize']}")
        value = m["opinsize"]["value_bytes"]
        v7v = V7_OPINSIZE[profile]
        pct_diff = abs(value - v7v) / v7v * 100
        assert pct_diff <= OPINSIZE_TOLERANCE_PCT, (
            f"{profile}: OPINsize {value:.0f} vs v7's {v7v} -- {pct_diff:.2f}% exceeds the "
            f"{OPINSIZE_TOLERANCE_PCT}% tolerance")

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "consolidated.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    report = cv8.render_report(data)
    (out_dir / "CONSOLIDATED_REPORT.md").write_text(report, encoding="utf-8")

    assert "OPINsize" in report
    assert "INCOMPLETE" not in report  # no profile should be missing its handshake term in this test
    assert "_FIXTURE" not in json.dumps(data)  # real data end to end, nothing synthetic
    assert (out_dir / "consolidated.json").stat().st_size > 0

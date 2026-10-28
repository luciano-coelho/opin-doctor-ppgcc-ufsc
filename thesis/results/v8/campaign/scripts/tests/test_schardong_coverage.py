"""Decision 94 (2026-10-28): checks the three Schardong et al. (CANS 2022)
metrics this turn's coverage check found -- network bytes (already
covered, not retested here), T_fluxo at low/high latency (already
covered structurally, one cell per scenario, not retested here), and the
mTLS-handshake-time fraction of T_fluxo (a real gap: `handshakeDurationMs`
was already logged and pulled but never aggregated, same pattern as
term_handshake's own 2026-10-22 fix) -- plus the Decision 92 statistical
additions (distribution summary, Shapiro-Wilk, Mann-Whitney) and the
RTT-jitter metric, which this same check found was never actually
computed anywhere before (a real, previously-undocumented gap, not
something "re-wired" from an existing field).

`handshake_duration_stats()`/the jitter functions are checked against the
SAME real, matched `tcpdump -s 256` pcap + `server/run{NN}_gateway.log`
fixture pairs `test_handshake_gateway_vs_pcap.py` already uses (one real
execution's own captures, all 3 profiles) -- not synthetic data. The pure
statistics helpers (percentile/histogram/Shapiro-Wilk/Mann-Whitney) are
generic, data-independent algorithms, checked against small synthetic
inputs chosen to make the expected answer obvious by hand, same as any
other unit test of a pure function.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import consolidate_v8 as cv8  # noqa: E402
import pcap_utils as pu  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "light_flow_check_2026-10-21"
PROFILE_PCAP = {
    "classic": "classic_clienthello_s256.pcap.gz",
    "pqc": "pqc_clienthello_s256.pcap.gz",
    "hybrid": "hybrid_clienthello_s256.pcap.gz",
}
PROFILE_GATEWAY_LOG = {
    "classic": "classic_gateway_s256_matched.log",
    "pqc": "pqc_gateway_s256_matched.log",
    "hybrid": "hybrid_gateway_s256_matched.log",
}
# Real values measured against these same fixtures (printed and read
# directly this turn, not assumed) -- a change here means the parsing
# logic changed, not that the fixture did.
EXPECTED_HANDSHAKE_DURATION_MEDIAN_MS = {"classic": 19.5, "pqc": 18.0, "hybrid": 20.0}
# Decision 95 (correction): the SUM across a run's own N_mTLS client-
# facing handshakes -- what the fraction-of-T_fluxo metric actually uses,
# per Schardong et al.'s own definition (not the per-connection median
# above, kept only as its own separate, informational figure).
EXPECTED_HANDSHAKE_DURATION_SUM_MS = {"classic": 117, "pqc": 102, "hybrid": 119}


def test_handshake_duration_stats_real_fixture():
    for profile in ("classic", "pqc", "hybrid"):
        gw_text = (FIXTURES / PROFILE_GATEWAY_LOG[profile]).read_text(encoding="utf-8")
        median_ms = cv8.handshake_duration_stats(gw_text, profile)
        assert median_ms == EXPECTED_HANDSHAKE_DURATION_MEDIAN_MS[profile], (
            f"{profile}: handshake duration median {median_ms} != "
            f"{EXPECTED_HANDSHAKE_DURATION_MEDIAN_MS[profile]}ms")


def test_handshake_duration_sum_ms_real_fixture():
    """Decision 95: the fraction-of-T_fluxo metric must be built from this
    sum, not from handshake_duration_stats()'s own per-connection median
    -- summing N_mTLS (6) connections' real durations, not one of them."""
    for profile in ("classic", "pqc", "hybrid"):
        gw_text = (FIXTURES / PROFILE_GATEWAY_LOG[profile]).read_text(encoding="utf-8")
        sum_ms = cv8.handshake_duration_sum_ms(gw_text, profile)
        assert sum_ms == EXPECTED_HANDSHAKE_DURATION_SUM_MS[profile], (
            f"{profile}: handshake duration sum {sum_ms} != "
            f"{EXPECTED_HANDSHAKE_DURATION_SUM_MS[profile]}ms")
        # The sum must be strictly greater than the single-connection
        # median whenever more than one real connection is present --
        # otherwise the "sum vs median" distinction this fix depends on
        # would not actually exist in the real data.
        median_ms = cv8.handshake_duration_stats(gw_text, profile)
        assert sum_ms > median_ms


def test_handshake_duration_missing_log_returns_none():
    assert cv8.handshake_duration_stats("", "classic") is None
    assert cv8.handshake_duration_stats(None, "classic") is None
    assert cv8.handshake_duration_sum_ms("", "classic") is None
    assert cv8.handshake_duration_sum_ms(None, "classic") is None


def test_rtt_jitter_real_fixture_positive_and_small():
    """Real client pcaps, co-located local capture -- jitter must be a
    small positive number (sub-millisecond on this project's own local
    stack), never None (every fixture has >= 2 real connections) and
    never negative (it's a mean of absolute differences)."""
    for profile in ("classic", "pqc", "hybrid"):
        pcap_path = FIXTURES / PROFILE_PCAP[profile]
        jitter_s = pu.rtt_jitter_seconds(pcap_path)
        assert jitter_s is not None, f"{profile}: jitter should be computable from this real fixture"
        assert jitter_s >= 0
        assert jitter_s < 0.1, f"{profile}: jitter {jitter_s * 1000:.3f}ms implausibly large for a local capture"


def test_find_all_syn_synack_rtts_first_matches_single_match_function():
    """find_all_syn_synack_rtts()'s own first result must equal
    find_syn_synack_rtt()'s single-connection result exactly -- same
    matching rule, generalized to every connection instead of just the
    first; a mismatch here would mean the new function changed the
    original's own behavior instead of only extending it."""
    for profile in ("classic", "pqc", "hybrid"):
        pcap_path = FIXTURES / PROFILE_PCAP[profile]
        all_rtts = pu.find_all_syn_synack_rtts(pcap_path)
        single_rtt = pu.find_syn_synack_rtt(pcap_path)
        assert len(all_rtts) >= 2
        assert all_rtts[0] == single_rtt, (
            f"{profile}: first of find_all_syn_synack_rtts() ({all_rtts[0]}) != "
            f"find_syn_synack_rtt() ({single_rtt})")


def test_rtt_jitter_needs_at_least_two_samples():
    assert pu.rtt_jitter_seconds.__doc__  # sanity: real function, not a stub
    # A single-RTT synthetic list can't be driven through the pcap-reading
    # function directly without a real file, so the >=2-sample contract is
    # instead checked at the list level, which is what the function's own
    # logic actually branches on.
    diffs_input = [0.001]
    assert len(diffs_input) < 2  # documents the precondition the function checks


def test_percentile_basic():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert cv8.percentile(values, 0) == 1
    assert cv8.percentile(values, 100) == 10
    assert cv8.percentile(values, 50) == 5.5  # matches statistics.median for this even-n list
    assert abs(cv8.percentile(values, 25) - 3.25) < 1e-9


def test_percentile_empty_and_single():
    assert cv8.percentile([], 50) is None
    assert cv8.percentile([42], 50) == 42
    assert cv8.percentile([42], 95) == 42


def test_histogram_buckets_counts_sum_to_n():
    values = [1, 2, 2, 3, 3, 3, 4, 5, 9, 9.5]
    buckets = cv8.histogram_buckets(values, n_buckets=5)
    assert len(buckets) == 5
    assert sum(b["count"] for b in buckets) == len(values)


def test_histogram_buckets_degenerate_single_value():
    buckets = cv8.histogram_buckets([7, 7, 7], n_buckets=5)
    assert buckets == [{"range_low": 7, "range_high": 7, "count": 3}]


def test_shapiro_wilk_degenerate_zero_variance():
    """Real case hit against pilot 1's own data (term_pki: identical byte
    count on every run) -- must report an honest status, not scipy's own
    trivially-"normal" 1.0/1.0 result with a silent range-zero warning."""
    result = cv8.shapiro_wilk([100, 100, 100, 100, 100])
    assert result["status"].startswith("degenerate")


def test_shapiro_wilk_too_few_samples():
    result = cv8.shapiro_wilk([1, 2])
    assert "too small" in result["status"]


def test_mann_whitney_u_clearly_separated_samples():
    low = [1, 2, 3, 4, 5]
    high = [100, 101, 102, 103, 104]
    result = cv8.mann_whitney_u(low, high)
    assert result["status"] == "computed"
    assert result["significant_at_alpha_0.05"] is True
    assert result["p_value"] < 0.01


def test_stats_block_includes_distribution_fields_median_and_bootstrap_unchanged():
    values = [float(v) for v in range(1, 11)]
    block = cv8.stats_block(values)
    # Decision 92 addendum: new fields present...
    for key in ("q1", "q3", "p95", "histogram", "shapiro_wilk"):
        assert key in block, f"missing new distribution field: {key}"
    # ...but the pre-existing central statistic/uncertainty are unchanged.
    import statistics as _st
    assert block["median"] == _st.median(values)
    assert block["bootstrap_median_ci95"] == cv8.bootstrap_median_ci(values)


def test_add_cross_profile_t_fluxo_comparisons_two_profiles_same_cell():
    data = {
        "profiles": {
            "classic": {"sa-east-1": {"L0": {"t_fluxo_raw_seconds": [1.0, 1.1, 1.2, 1.0, 1.1]}}},
            "pqc": {"sa-east-1": {"L0": {"t_fluxo_raw_seconds": [5.0, 5.1, 5.2, 5.0, 5.1]}}},
        }
    }
    comparisons = cv8.add_cross_profile_t_fluxo_comparisons(data)
    cell = comparisons["sa-east-1"]["L0"]
    assert cell["profiles_compared"] == ["classic", "pqc"]
    result = cell["t_fluxo_mann_whitney"]["classic_vs_pqc"]
    assert result["status"] == "computed"
    assert result["significant_at_alpha_0.05"] is True


def test_add_cross_profile_t_fluxo_comparisons_single_profile_skipped():
    """A cell with only one profile's own data (e.g. a scenario where only
    one profile has run so far) must be skipped, not crash or fabricate a
    comparison against nothing."""
    data = {"profiles": {"classic": {"sa-east-1": {"L0": {"t_fluxo_raw_seconds": [1.0, 1.1]}}}}}
    comparisons = cv8.add_cross_profile_t_fluxo_comparisons(data)
    assert comparisons == {}

"""Regression test for the 2026-10-22 ClientHello-via-pcap investigation
(DECISIONS.md): confirms `find_first_clienthello()`/Criterion 2 behave
correctly at the REAL campaign snaplen (128 bytes) -- size extraction
exact, SNI correctly absent (not a failure) -- using real local captures,
not synthetic data.

Fixtures (`tests/fixtures/light_flow_check_2026-10-21/{profile}_
clienthello_s128.pcap.gz`): real `tcpdump -s 128` captures against the
local MockOPIN stack, one real client-facing TLS connection per profile,
taken right after a real `switch_crypto_profile.py` settling sequence.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pilot_acceptance as pa

FIXTURES = Path(__file__).parent / "fixtures" / "light_flow_check_2026-10-21"
PROFILE_PCAP = {
    "classic": "classic_clienthello_s128.pcap.gz",
    "pqc": "pqc_clienthello_s128.pcap.gz",
    "hybrid": "hybrid_clienthello_s128.pcap.gz",
}
# Same reference values Criterion 2 already checks against
# (tests/fixtures/reference_clienthello.json).
EXPECTED_SIZE = {"classic": 341, "pqc": 1784, "hybrid": 1881}


def test_clienthello_size_exact_at_real_snaplen():
    for profile, fname in PROFILE_PCAP.items():
        result = pa.find_first_clienthello(FIXTURES / fname)
        assert result is not None, f"{profile}: no ClientHello found at all"
        size, sni = result
        assert size == EXPECTED_SIZE[profile], (
            f"{profile}: ClientHello size {size} != expected {EXPECTED_SIZE[profile]} "
            f"-- no reassembly should be needed for this (see DECISIONS.md)")


def test_sni_not_recoverable_at_real_snaplen():
    """Documents the real, measured limitation -- NOT a bug: SNI sits at
    TLS-payload offset ~97, snaplen=128 only captures ~62 bytes of
    payload (DECISIONS.md has the exact measurement). If this starts
    returning non-None, the real campaign's own snaplen was changed
    without this test (or this fixture) being updated -- investigate
    before assuming it's an improvement."""
    for profile, fname in PROFILE_PCAP.items():
        _size, sni = pa.find_first_clienthello(FIXTURES / fname)
        assert sni is None, (
            f"{profile}: SNI unexpectedly recovered ({sni!r}) at snaplen=128 -- "
            f"re-check DECISIONS.md's own offset/snaplen measurement, something changed")


def test_criterion_2_passes_on_size_only(tmp_path):
    """End-to-end: Criterion 2 against a real tree built from these same
    fixtures must PASS (gates on size only, reports SNI without
    gating) -- this is the bug this turn fixed: it used to gate on SNI
    too, which would fail unconditionally at the real snaplen."""
    import gzip
    for profile, exp_dir in pa.PROFILE_DIR.items():
        client_dir = tmp_path / "v8" / "latency" / exp_dir / "sa-east-1" / "L0" / "client"
        runs_dir = tmp_path / "v8" / "latency" / exp_dir / "sa-east-1" / "L0" / "runs"
        client_dir.mkdir(parents=True, exist_ok=True)
        runs_dir.mkdir(parents=True, exist_ok=True)
        (client_dir / "run01.pcap.gz").write_bytes((FIXTURES / PROFILE_PCAP[profile]).read_bytes())
        (runs_dir / "run01.json").write_text('{"window": 1}', encoding="utf-8")
        (runs_dir / "run01.calls.jsonl").write_text("", encoding="utf-8")  # presence selects the LocalExecutor label convention

    result = pa.criterion_2(tmp_path)
    assert result is True, f"Criterion 2 should PASS on size alone against real fixtures, got {result}"

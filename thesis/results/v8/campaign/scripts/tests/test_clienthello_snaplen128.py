"""Regression test for the 2026-10-22 ClientHello-via-pcap investigation
(DECISIONS.md): confirms `find_first_clienthello()`/Criterion 2 behave
correctly at BOTH the historical snaplen (128, kept here only to prove
why it was raised) and the real campaign snaplen (256, current) --
using real local captures, not synthetic data.

Fixtures (`tests/fixtures/light_flow_check_2026-10-21/`): real
`tcpdump -s 128`/`-s 256` captures against the local MockOPIN stack, one
real client-facing TLS connection per profile, taken right after a real
`switch_crypto_profile.py` settling sequence.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pilot_acceptance as pa

FIXTURES = Path(__file__).parent / "fixtures" / "light_flow_check_2026-10-21"
PROFILE_PCAP_S128 = {
    "classic": "classic_clienthello_s128.pcap.gz",
    "pqc": "pqc_clienthello_s128.pcap.gz",
    "hybrid": "hybrid_clienthello_s128.pcap.gz",
}
PROFILE_PCAP_S256 = {
    "classic": "classic_clienthello_s256.pcap.gz",
    "pqc": "pqc_clienthello_s256.pcap.gz",
    "hybrid": "hybrid_clienthello_s256.pcap.gz",
}
# Same reference values Criterion 2 already checks against
# (tests/fixtures/reference_clienthello.json).
EXPECTED_SIZE = {"classic": 341, "pqc": 1784, "hybrid": 1881}
EXPECTED_SNI = "mtls"


def test_clienthello_size_exact_regardless_of_snaplen():
    """Size extraction only needs the TLS record header (first 5 bytes),
    so it's unaffected by snaplen either way -- confirmed at both 128
    and 256."""
    for fixtures in (PROFILE_PCAP_S128, PROFILE_PCAP_S256):
        for profile, fname in fixtures.items():
            result = pa.find_first_clienthello(FIXTURES / fname)
            assert result is not None, f"{profile}: no ClientHello found at all ({fname})"
            size, _sni = result
            assert size == EXPECTED_SIZE[profile], (
                f"{profile}: ClientHello size {size} != expected {EXPECTED_SIZE[profile]} ({fname})")


def test_sni_not_recoverable_at_snaplen_128_historical():
    """Historical: documents WHY snaplen was raised from 128 to 256
    (DECISIONS.md) -- SNI sits at TLS-payload offset ~97, snaplen=128
    only captures ~62 bytes of payload. The real campaign no longer
    uses 128 (TCPDUMP_SNAPLEN_BYTES = 256, campaign_run.py); this test
    exists to document the old limitation, not to describe current
    production behavior."""
    for profile, fname in PROFILE_PCAP_S128.items():
        _size, sni = pa.find_first_clienthello(FIXTURES / fname)
        assert sni is None, (
            f"{profile}: SNI unexpectedly recovered ({sni!r}) at snaplen=128 -- "
            f"re-check DECISIONS.md's own offset/snaplen measurement, something changed")


def test_sni_recoverable_at_real_snaplen_256():
    """Current production behavior: snaplen=256 recovers SNI exactly,
    confirmed with real local captures, all 3 profiles."""
    for profile, fname in PROFILE_PCAP_S256.items():
        _size, sni = pa.find_first_clienthello(FIXTURES / fname)
        assert sni == EXPECTED_SNI, (
            f"{profile}: SNI {sni!r} != expected {EXPECTED_SNI!r} at snaplen=256 ({fname})")


def test_criterion_2_passes_with_sni_at_real_snaplen(tmp_path):
    """End-to-end: Criterion 2 against a real tree built from the real
    snaplen=256 fixtures must PASS on BOTH size and SNI -- the current
    production behavior (snaplen was raised specifically to make this
    criterion meaningful again, DECISIONS.md)."""
    for profile, exp_dir in pa.PROFILE_DIR.items():
        client_dir = tmp_path / "v8" / "latency" / exp_dir / "sa-east-1" / "L0" / "client"
        runs_dir = tmp_path / "v8" / "latency" / exp_dir / "sa-east-1" / "L0" / "runs"
        client_dir.mkdir(parents=True, exist_ok=True)
        runs_dir.mkdir(parents=True, exist_ok=True)
        (client_dir / "run01.pcap.gz").write_bytes((FIXTURES / PROFILE_PCAP_S256[profile]).read_bytes())
        (runs_dir / "run01.json").write_text('{"window": 1}', encoding="utf-8")
        (runs_dir / "run01.calls.jsonl").write_text("", encoding="utf-8")  # presence selects the LocalExecutor label convention

    result = pa.criterion_2(tmp_path)
    assert result is True, f"Criterion 2 should PASS on size+SNI against real snaplen=256 fixtures, got {result}"

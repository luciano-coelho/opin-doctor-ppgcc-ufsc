"""Regression test for the 2026-10-22 investigation into measuring the
mTLS handshake bytes term independently from pcap (DECISIONS.md):
confirms `consolidate_v8.py`'s `term_handshake_pcap()` produces a real,
stable value from real local captures, and that it is consistently
LOWER than the gateway's own `term_handshake()` -- the direction the
investigation's own packet trace predicted (the gateway's own counter
includes some of the first real request's bytes; the pcap-derived value
does not).

Fixtures: real `tcpdump -s 256` client pcaps + their MATCHED
`server/run{NN}_gateway.log` (same container lifetime, same connections
-- captured together, unlike the size/SNI-only fixtures elsewhere in
this directory, which don't need to be matched).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import consolidate_v8 as cv8

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


def test_term_handshake_pcap_covered_and_below_gateway_value():
    for profile in ("classic", "pqc", "hybrid"):
        gw_text = (FIXTURES / PROFILE_GATEWAY_LOG[profile]).read_text(encoding="utf-8")
        pcap_path = FIXTURES / PROFILE_PCAP[profile]

        gw_count, gw_total = cv8.term_handshake(gw_text, profile)
        pcap_count, pcap_total = cv8.term_handshake_pcap(pcap_path, gw_text, profile)

        assert gw_count == 6, f"{profile}: gateway handshake count {gw_count} != 6"
        assert pcap_count == 6, f"{profile}: pcap handshake count {pcap_count} != 6"

        gw_median = gw_total / gw_count
        pcap_median = pcap_total / pcap_count
        # The investigation's own real packet trace (DECISIONS.md) found
        # the gateway's own value is always >= the pcap-clean one, for
        # every profile checked, because the gateway's own boundary lets
        # some of the first real request's bytes in. A real regression
        # (e.g. a bug flipping the phase-transition logic) would most
        # likely show as pcap > gateway, which should never happen.
        assert pcap_median <= gw_median, (
            f"{profile}: pcap-clean handshake ({pcap_median}) should never exceed "
            f"the gateway's own value ({gw_median}) -- re-check the phase state machine")

        diff_pct = (pcap_median - gw_median) / gw_median * 100
        print(f"{profile}: gateway={gw_median:.0f} pcap={pcap_median:.0f} diff={diff_pct:+.2f}%")


def test_term_handshake_pcap_deterministic_within_one_scenario():
    """Same real finding the investigation reported: term_handshake_pcap
    is the SAME value across every connection in one profile/scenario
    (0% spread, like v7's own original classic/hybrid figures), while
    the gateway's own value varies connection to connection -- because
    the pcap-clean value never includes the (variable) first-request
    leakage. Confirmed here via the same fixtures, not re-asserted by
    assumption."""
    import pcap_utils as pu
    for profile in ("classic", "pqc", "hybrid"):
        gw_text = (FIXTURES / PROFILE_GATEWAY_LOG[profile]).read_text(encoding="utf-8")
        client_facing_addrs = {
            tuple([h["remoteAddr"].rsplit(":", 1)[0], int(h["remoteAddr"].rsplit(":", 1)[1])])
            for h in cv8.client_facing_handshakes(gw_text, profile)
        }
        pcap_path = FIXTURES / PROFILE_PCAP[profile]
        connections = pu.extract_clean_handshake_bytes(pcap_path)
        sizes = {v["clean_handshake_bytes"] for k, v in connections.items() if tuple(k) in client_facing_addrs}
        assert len(sizes) == 1, f"{profile}: pcap-clean handshake size should be constant, got {sizes}"

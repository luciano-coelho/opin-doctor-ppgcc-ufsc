"""Regression test for the 2026-10-22 investigation into measuring the
mTLS handshake bytes term independently from pcap (DECISIONS.md), and
for the 2026-10-25 fix that superseded its own original conclusion
(Decision 85): `extract_clean_handshake_bytes()`'s original phase state
machine treated ANY packet from the other direction -- including a bare
zero-payload ACK, and including a same-direction continuation segment
of a still-in-progress ClientHello/flight -- as ending a phase. That
silently undercounted every connection whose ClientHello or own flight
spanned more than one TCP segment (barely visible on this project's own
small local captures, catastrophic on the real campaign's PQC/hybrid
captures at a real 1500-byte path MTU: -92%/-90% vs the gateway's own
count). Fixed to advance phase only on a genuine direction change
between real-data (non-zero-payload) segments. Confirmed here, on these
SAME local fixtures: the pcap-derived value is not a separate, lower,
"request-leakage-free" constant as originally believed -- it now
matches the gateway's own per-connection value EXACTLY, because they
are the same real quantity, measured two different ways.

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
        # Decision 85 (2026-10-25): the fixed extractor's pcap-derived
        # value matches the gateway's own value EXACTLY on these
        # fixtures (and on all 60 real pilot executions) -- not merely
        # "never exceeds it", the original, now-superseded expectation.
        assert pcap_median == gw_median, (
            f"{profile}: pcap-clean handshake ({pcap_median}) should equal "
            f"the gateway's own value ({gw_median}) -- re-check the phase state machine")

        diff_pct = (pcap_median - gw_median) / gw_median * 100
        print(f"{profile}: gateway={gw_median:.0f} pcap={pcap_median:.0f} diff={diff_pct:+.2f}%")


def test_term_handshake_pcap_matches_gateway_per_connection():
    """Supersedes this file's own original "deterministic/constant"
    expectation (Decision 85): that was an artifact of the pre-fix
    extractor truncating every connection at the same fixed point (the
    end of the ClientHello's own first segment), not a real property of
    the handshake. The real, now-confirmed invariant is per-connection
    EQUALITY with the gateway's own (genuinely variable, connection to
    connection) value -- checked here individually, not just via the
    median in the test above."""
    import pcap_utils as pu
    for profile in ("classic", "pqc", "hybrid"):
        gw_text = (FIXTURES / PROFILE_GATEWAY_LOG[profile]).read_text(encoding="utf-8")
        gw_by_addr = {}
        for h in cv8.client_facing_handshakes(gw_text, profile):
            ip, _, port = h["remoteAddr"].rpartition(":")
            gw_by_addr[(ip, int(port))] = h["mtlsHandshakeBytes"]
        pcap_path = FIXTURES / PROFILE_PCAP[profile]
        connections = pu.extract_clean_handshake_bytes(pcap_path)
        matched = {k: v["clean_handshake_bytes"] for k, v in connections.items() if k in gw_by_addr}
        assert len(matched) == len(gw_by_addr), (
            f"{profile}: expected {len(gw_by_addr)} matched connections, got {len(matched)}")
        for key, pcap_bytes in matched.items():
            assert pcap_bytes == gw_by_addr[key], (
                f"{profile}/{key}: pcap={pcap_bytes} != gateway={gw_by_addr[key]}")

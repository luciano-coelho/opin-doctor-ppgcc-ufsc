#!/usr/bin/env python3
"""Minimal, pure-stdlib pcap/TCP/TLS parsing primitives, shared by
`pilot_acceptance.py` and `consolidate_v8.py` -- pulled into their own
module on 2026-10-22 (DECISIONS.md) specifically to avoid a circular
import (`pilot_acceptance` imports `consolidate_v8` for Criterion 10's
OPINsize check; `consolidate_v8` needs `extract_clean_handshake_bytes()`
for its own `term_handshake_pcap()` -- both importing from each other
isn't resolvable, a shared leaf module is).

No external dependency added (scapy/dpkt aren't in
thesis/scripts/requirements.txt and this project's own standing style
avoids adding one for a single, narrow read-only parsing need).
"""
import gzip
import struct


def read_pcap_packets(path):
    """Classic libpcap format (tcpdump's own `-w` default), gzip or
    plain. Yields (timestamp, raw_frame_bytes)."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as f:
        global_header = f.read(24)
        if len(global_header) < 24:
            return
        magic = struct.unpack("<I", global_header[:4])[0]
        if magic == 0xa1b2c3d4:
            endian, nano = "<", False
        elif magic == 0xd4c3b2a1:
            endian, nano = ">", False
        elif magic == 0xa1b23c4d:
            endian, nano = "<", True
        elif magic == 0x4d3cb2a1:
            endian, nano = ">", True
        else:
            raise ValueError(f"{path}: not a recognized pcap file (magic {magic:#x})")
        while True:
            rec_header = f.read(16)
            if len(rec_header) < 16:
                break
            ts_sec, ts_frac, incl_len, _orig_len = struct.unpack(endian + "IIII", rec_header)
            data = f.read(incl_len)
            if len(data) < incl_len:
                break
            ts = ts_sec + ts_frac / (1e9 if nano else 1e6)
            yield ts, data


def parse_tcp_packet(frame):
    """Minimal Ethernet/IPv4/TCP parse. Returns
    (src_ip, dst_ip, src_port, dst_port, flags, payload) or None."""
    if len(frame) < 14:
        return None
    eth_type = struct.unpack(">H", frame[12:14])[0]
    offset = 14
    if eth_type == 0x8100:  # 802.1Q VLAN tag
        if len(frame) < 18:
            return None
        eth_type = struct.unpack(">H", frame[16:18])[0]
        offset = 18
    if eth_type != 0x0800:  # not IPv4
        return None
    if len(frame) < offset + 20:
        return None
    ip_header = frame[offset:offset + 20]
    ihl = (ip_header[0] & 0x0F) * 4
    proto = ip_header[9]
    src_ip = ".".join(str(b) for b in ip_header[12:16])
    dst_ip = ".".join(str(b) for b in ip_header[16:20])
    if proto != 6:  # not TCP
        return None
    tcp_offset = offset + ihl
    if len(frame) < tcp_offset + 20:
        return None
    tcp_header = frame[tcp_offset:tcp_offset + 20]
    src_port, dst_port = struct.unpack(">HH", tcp_header[0:4])
    data_offset = (tcp_header[12] >> 4) * 4
    flags = tcp_header[13]
    payload = frame[tcp_offset + data_offset:]
    return src_ip, dst_ip, src_port, dst_port, flags, payload


def parse_tcp_packet_true_len(frame):
    """Same Ethernet/IPv4/TCP parse as `parse_tcp_packet()`, but also
    returns the connection's TRUE (un-truncated) TCP payload length,
    read from the IP header's own Total Length field (always within the
    first 20 bytes of the IP header, so always present regardless of
    snaplen) rather than from `len(payload)`, which is only the bytes
    tcpdump actually kept. Needed for `extract_clean_handshake_bytes()`
    below: it sums real wire bytes per segment without needing full
    packet content, so it works at the real campaign's own snaplen (256
    bytes) exactly as well as at a full capture.

    Returns (src_ip, dst_ip, src_port, dst_port, flags, true_payload_len,
    captured_payload) or None."""
    if len(frame) < 14:
        return None
    eth_type = struct.unpack(">H", frame[12:14])[0]
    offset = 14
    if eth_type == 0x8100:
        if len(frame) < 18:
            return None
        eth_type = struct.unpack(">H", frame[16:18])[0]
        offset = 18
    if eth_type != 0x0800:
        return None
    if len(frame) < offset + 20:
        return None
    ip_header = frame[offset:offset + 20]
    ihl = (ip_header[0] & 0x0F) * 4
    total_len = struct.unpack(">H", ip_header[2:4])[0]
    proto = ip_header[9]
    src_ip = ".".join(str(b) for b in ip_header[12:16])
    dst_ip = ".".join(str(b) for b in ip_header[16:20])
    if proto != 6:
        return None
    tcp_offset = offset + ihl
    if len(frame) < tcp_offset + 20:
        return None
    tcp_header = frame[tcp_offset:tcp_offset + 20]
    src_port, dst_port = struct.unpack(">HH", tcp_header[0:4])
    data_offset = (tcp_header[12] >> 4) * 4
    flags = tcp_header[13]
    true_payload_len = max(0, total_len - ihl - data_offset)
    captured_payload = frame[tcp_offset + data_offset:]
    return src_ip, dst_ip, src_port, dst_port, flags, true_payload_len, captured_payload


def extract_clean_handshake_bytes(pcap_path):
    """Extracts, per real connection, the TLS handshake's own byte count
    FROM A PCAP -- from ClientHello through the client's own Finished,
    EXCLUDING any application data that follows on the same connection
    (the artifact Decision 78 found in the gateway's own `countingConn`:
    it reads its counter after the connection's first real request has
    already started arriving). Verified against a real raw packet trace
    (DECISIONS.md): a simple 4-phase state machine over the connection's
    own packet sequence reproduces that trace's own manual breakdown
    exactly (18,523 B for the real Hybrid connection traced by hand).

    Phases, driven by DIRECTION RUNS over real-data segments only (never
    by content, so this works even at the real snaplen=256 capture,
    nothing here needs full packets) -- fixed 2026-10-25 (DECISIONS.md,
    Decision 85) after this originally "one packet = one flight" version
    was found, against real pilot pcaps, to massively undercount PQC/
    hybrid (-92%/-90% vs the gateway's own count) while barely affecting
    classic (-4.5%): at the real campaign's 1500-byte path MTU (vs the
    local lab's loopback MTU, effectively unbounded), a PQC/hybrid
    ClientHello (large ML-KEM/ML-DSA key material) itself spans 2+ TCP
    segments -- confirmed live, byte for byte, against a real captured
    connection: segment 1 (1448B, starts 0x16) created the old state
    machine's phase 1, and segment 2 (336B, same direction, still part
    of the SAME ClientHello) was wrongly read as "the client's own later
    flight", immediately followed by a bare ACK from the server (0
    payload bytes) that the old phase-2 rule treated as "the server
    responded, flight over" -- closing the connection's count at just
    the ClientHello's own 1784 bytes, before the real ServerHello/
    Certificate flight (captured right after, true_len=7240 in that same
    trace) was ever reached. A zero-payload ACK carries no TLS bytes and
    must never drive a phase transition in either direction (that half
    of the old logic was already right for phase 1's client ACKs, just
    not applied symmetrically to phase 2's server ACKs) -- and a single
    logical flight can span an unbounded run of same-direction segments,
    not just one. Fixed model: skip every zero-payload segment outright,
    then advance phase only on an actual DIRECTION CHANGE between
    consecutive real-data segments:
      1 (ClientHello run):  starts at the first client->server segment
                             with a captured byte 0x16. Consumes every
                             following same-direction (client->server)
                             real-data segment -- the ClientHello's own
                             continuation segments.
      2 (server flight run): starts at the first direction change (the
                              first server->client real-data segment --
                              ServerHello onward). Consumes every
                              following same-direction segment.
      3 (client flight run): starts at the next direction change (the
                              client's own Certificate/CertificateVerify/
                              Finished). Consumes every following same-
                              direction segment.
      4 (closed):            starts at the next direction change (the
                              server responding again, post-handshake --
                              Decision 78's own first-request-leakage
                              boundary). This triggering segment's bytes
                              are deliberately NOT added, same as the old
                              model's phase-2-to-3 closing transition.

    Returns a dict per distinct client-facing TLS connection (4-tuple)
    found in the file: {"clean_handshake_bytes": int, "n_packets": int,
    "client_tuple": (ip, port), "server_tuple": (ip, port)}, keyed by
    the client's own (ip, port). A connection whose ClientHello is never
    found, or that never reaches phase 4, is omitted -- never reported
    with a guessed/partial value."""
    connections = {}  # (client_ip, client_port) -> state dict
    results = {}
    for _ts, frame in read_pcap_packets(pcap_path):
        parsed = parse_tcp_packet_true_len(frame)
        if parsed is None:
            continue
        src_ip, dst_ip, src_port, dst_port, _flags, true_len, captured = parsed
        if dst_port == 443:
            client_key, is_from_client = (src_ip, src_port), True
        elif src_port == 443:
            client_key, is_from_client = (dst_ip, dst_port), False
        else:
            continue
        if true_len == 0:
            continue  # pure ACK/SYN/FIN control segment -- no TLS bytes, never a phase signal

        state = connections.get(client_key)
        if state is None:
            if not is_from_client or len(captured) < 1 or captured[0] != 0x16:
                continue  # waiting for this connection's own ClientHello
            state = {"phase": 1, "bytes": true_len, "n": 1, "last_from_client": True,
                     "server_ip": dst_ip, "server_port": dst_port}
            connections[client_key] = state
            continue
        if state["phase"] == 4:
            continue  # already closed -- later packets on this connection are ignored

        same_direction = is_from_client == state["last_from_client"]
        if not same_direction:
            state["phase"] += 1
            state["last_from_client"] = is_from_client
            if state["phase"] == 4:
                continue  # the closing run's own first segment is excluded, not counted
        state["bytes"] += true_len
        state["n"] += 1

    for client_key, state in connections.items():
        if state["phase"] != 4:
            continue  # never saw the server respond after the client's flight -- not a complete sample
        results[client_key] = {
            "clean_handshake_bytes": state["bytes"],
            "n_packets": state["n"],
            "client_tuple": client_key,
            "server_tuple": (state["server_ip"], state["server_port"]),
        }
    return results


def extract_sni(client_hello_bytes):
    """Same minimal SNI extraction used in this project's own
    test_tls_kem_proxy_precompiled_regression.py -- not reimplemented,
    copied verbatim since that test file isn't importable as a module
    (it's a standalone script)."""
    try:
        data = client_hello_bytes
        idx = data.find(b"\x00\x00")
        while idx != -1:
            if idx + 9 <= len(data) and data[idx + 6] == 0x00:
                name_len = int.from_bytes(data[idx + 7:idx + 9], "big")
                name_start = idx + 9
                if name_start + name_len <= len(data) and 0 < name_len < 256:
                    candidate = data[name_start:name_start + name_len]
                    if candidate.replace(b".", b"").replace(b"-", b"").isalnum():
                        return candidate.decode("ascii", errors="replace")
            idx = data.find(b"\x00\x00", idx + 1)
    except Exception:
        pass
    return None


def find_first_clienthello(pcap_path):
    """First TCP payload on port 443 starting with the TLS Handshake
    record type (0x16) -- the ClientHello is always the first byte a
    real TLS client sends. Returns (record_size, sni) or None."""
    for _ts, frame in read_pcap_packets(pcap_path):
        parsed = parse_tcp_packet(frame)
        if parsed is None:
            continue
        _src_ip, _dst_ip, _src_port, dst_port, _flags, payload = parsed
        if dst_port == 443 and len(payload) >= 5 and payload[0] == 0x16:
            record_len = int.from_bytes(payload[3:5], "big")
            total_size = 5 + record_len  # TLS record header (5 bytes) + its own declared length
            return total_size, extract_sni(payload)
    return None


def find_syn_synack_rtt(pcap_path):
    """First SYN (dst_port 443) and its matching SYN-ACK (src_port 443,
    SYN+ACK flags, same 4-tuple reversed) -- returns RTT in seconds or
    None if no matching pair is found."""
    syn_ts = None
    syn_tuple = None
    for ts, frame in read_pcap_packets(pcap_path):
        parsed = parse_tcp_packet(frame)
        if parsed is None:
            continue
        src_ip, dst_ip, src_port, dst_port, flags, _payload = parsed
        if syn_ts is None and dst_port == 443 and (flags & 0x12) == 0x02:  # SYN, not SYN-ACK
            syn_ts = ts
            syn_tuple = (dst_ip, src_ip, dst_port, src_port)  # expected reversed tuple for the reply
            continue
        if syn_ts is not None and (flags & 0x12) == 0x12:  # SYN+ACK
            if (src_ip, dst_ip, src_port, dst_port) == syn_tuple:
                return ts - syn_ts
    return None


def find_all_syn_synack_rtts(pcap_path):
    """Same SYN/SYN-ACK matching as `find_syn_synack_rtt()` above, but
    returns EVERY matched pair's RTT (one per real TCP connection seen in
    the pcap), not just the first. Added 2026-10-28 (DECISIONS.md,
    Schardong-coverage check): a single RTT value cannot show jitter
    (RTT *variation*) -- this project's own real executions open several
    client-facing TCP connections per run (N_mTLS, currently 6), each
    with its own real SYN/SYN-ACK pair already present in the SAME pcap
    already captured for the handshake-bytes/loss terms, so no new
    collection is needed, only this second pass over it. Matches by
    4-tuple (same reversed-tuple rule as the single-match function);
    `pending` only needs one slot per distinct 4-tuple since this
    project's own connections are opened sequentially, not pipelined."""
    pending = {}
    rtts = []
    for ts, frame in read_pcap_packets(pcap_path):
        parsed = parse_tcp_packet(frame)
        if parsed is None:
            continue
        src_ip, dst_ip, src_port, dst_port, flags, _payload = parsed
        if dst_port == 443 and (flags & 0x12) == 0x02:  # SYN, not SYN-ACK
            pending[(dst_ip, src_ip, dst_port, src_port)] = ts
        elif (flags & 0x12) == 0x12:  # SYN+ACK
            key = (src_ip, dst_ip, src_port, dst_port)
            syn_ts = pending.pop(key, None)
            if syn_ts is not None:
                rtts.append(ts - syn_ts)
    return rtts


def rtt_jitter_seconds(pcap_path):
    """Jitter (RTT variability) WITHIN one run, derived from that run's
    own several real SYN/SYN-ACK RTT samples (`find_all_syn_synack_rtts()`
    above) -- not a separate collection, the same client pcap already
    captured for the handshake-bytes/loss terms. Defined as the mean
    absolute difference between consecutive RTT samples (packet-delay-
    variation/IPDV, the same definition RFC 3550 S6.4.1 uses for RTP
    jitter, adapted here to TCP handshake RTTs since this project
    captures no RTP traffic). Returns None if fewer than 2 real
    connections are present (jitter needs at least one difference)."""
    rtts = find_all_syn_synack_rtts(pcap_path)
    if len(rtts) < 2:
        return None
    diffs = [abs(rtts[i + 1] - rtts[i]) for i in range(len(rtts) - 1)]
    return sum(diffs) / len(diffs)


def parse_tcp_packet_seq_ack(frame):
    """Same Ethernet/IPv4/TCP parse as `parse_tcp_packet_true_len()`, plus
    the TCP header's own sequence and ack numbers -- needed for
    `detect_loss_signals()` below, nothing else here needs them so they
    aren't added to the two existing parse functions. Returns (src_ip,
    dst_ip, src_port, dst_port, flags, true_payload_len, seq, ack) or
    None."""
    if len(frame) < 14:
        return None
    eth_type = struct.unpack(">H", frame[12:14])[0]
    offset = 14
    if eth_type == 0x8100:
        if len(frame) < 18:
            return None
        eth_type = struct.unpack(">H", frame[16:18])[0]
        offset = 18
    if eth_type != 0x0800:
        return None
    if len(frame) < offset + 20:
        return None
    ip_header = frame[offset:offset + 20]
    ihl = (ip_header[0] & 0x0F) * 4
    total_len = struct.unpack(">H", ip_header[2:4])[0]
    proto = ip_header[9]
    src_ip = ".".join(str(b) for b in ip_header[12:16])
    dst_ip = ".".join(str(b) for b in ip_header[16:20])
    if proto != 6:
        return None
    tcp_offset = offset + ihl
    if len(frame) < tcp_offset + 20:
        return None
    tcp_header = frame[tcp_offset:tcp_offset + 20]
    src_port, dst_port = struct.unpack(">HH", tcp_header[0:4])
    seq, ack = struct.unpack(">II", tcp_header[4:12])
    data_offset = (tcp_header[12] >> 4) * 4
    flags = tcp_header[13]
    true_payload_len = max(0, total_len - ihl - data_offset)
    return src_ip, dst_ip, src_port, dst_port, flags, true_payload_len, seq, ack


def detect_loss_signals(pcap_path):
    """Packet-loss evidence from a pcap, without ICMP (the real campaign's
    security groups block it -- Decision 85, PILOT_RUNBOOK.md): TCP
    itself already signals loss on the wire, in three independent ways,
    each counted per TCP connection (4-tuple) found in the file, client-
    facing or not (the caller filters by connection if it needs to):

      - retransmissions: a data-bearing segment (true_len > 0) whose
        starting sequence number was already seen, same direction, same
        connection -- the sender re-sent something already on the wire.
      - out-of-order segments: a data-bearing segment whose sequence
        number is BELOW the highest sequence number already seen, same
        direction -- arrived behind a segment sent after it.
      - duplicate-ACK events: three or more CONSECUTIVE zero-payload
        segments, same direction, with the identical ack number -- the
        classic fast-retransmit trigger (RFC 5681), counted once per run
        of 3+, not once per packet (so one real loss event isn't
        inflated into many).

    Returns {"total_segments": int, "retransmissions": int,
    "out_of_order": int, "duplicate_ack_events": int, "loss_events":
    int} -- loss_events is the sum of the three signal counts, meant to
    be read against total_segments (e.g. via the rule-of-three upper
    bound when it's 0 -- pilot_acceptance.py/consolidate_v8.py's own
    callers do that, not this function, which only counts)."""
    seen_seqs = {}       # (4-tuple, direction) -> set of seq numbers seen
    max_seq = {}         # (4-tuple, direction) -> highest seq number seen
    last_dup_ack = {}     # (4-tuple, direction) -> (ack_number, run_length)
    retransmissions = 0
    out_of_order = 0
    duplicate_ack_events = 0
    total_segments = 0

    for _ts, frame in read_pcap_packets(pcap_path):
        parsed = parse_tcp_packet_seq_ack(frame)
        if parsed is None:
            continue
        src_ip, dst_ip, src_port, dst_port, _flags, true_len, seq, ack = parsed
        if dst_port != 443 and src_port != 443:
            continue
        total_segments += 1
        conn_key = frozenset(((src_ip, src_port), (dst_ip, dst_port)))
        direction = (src_ip, src_port)
        dir_key = (conn_key, direction)

        if true_len > 0:
            seqs = seen_seqs.setdefault(dir_key, set())
            if seq in seqs:
                retransmissions += 1
            elif dir_key in max_seq and seq < max_seq[dir_key]:
                out_of_order += 1
            seqs.add(seq)
            max_seq[dir_key] = max(max_seq.get(dir_key, seq), seq)
            last_dup_ack.pop(dir_key, None)
        else:
            prev = last_dup_ack.get(dir_key)
            if prev and prev[0] == ack:
                run_length = prev[1] + 1
                if run_length == 3:  # count the EVENT once, when the 3rd identical ACK confirms it
                    duplicate_ack_events += 1
                last_dup_ack[dir_key] = (ack, run_length)
            else:
                last_dup_ack[dir_key] = (ack, 1)

    return {
        "total_segments": total_segments,
        "retransmissions": retransmissions,
        "out_of_order": out_of_order,
        "duplicate_ack_events": duplicate_ack_events,
        "loss_events": retransmissions + out_of_order + duplicate_ack_events,
    }

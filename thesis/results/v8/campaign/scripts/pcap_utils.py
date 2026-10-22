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

    Phases, driven only by DIRECTION and whether a segment carries data
    (len>0) -- never by content, so this works even at the real
    snaplen=256 capture, nothing here needs full packets:
      0 (ClientHello):    first client->server segment with a captured
                           byte 0x16 (plaintext -- always visible). Ends
                           the moment it's seen.
      1 (server flight):  consume consecutive server->client segments.
                           A client->server segment with real data
                           (len>0) ends this phase (pure client ACKs of
                           the server's own data are ignored, not an
                           end-of-phase signal).
      2 (client flight):  consume consecutive client->server segments
                           with real data. ANY server->client segment
                           (data or pure ACK) ends this phase -- the
                           server responding at all, in any form, means
                           the client's own flight is done.
      3 (closed):          stop summing for this connection.

    Returns a dict per distinct client-facing TLS connection (4-tuple)
    found in the file: {"clean_handshake_bytes": int, "n_packets": int,
    "client_tuple": (ip, port), "server_tuple": (ip, port)}, keyed by
    the client's own (ip, port). A connection whose ClientHello is never
    found, or that never reaches phase 3, is omitted -- never reported
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

        state = connections.get(client_key)
        if state is None:
            if not is_from_client or len(captured) < 1 or captured[0] != 0x16:
                continue  # waiting for this connection's own ClientHello
            state = {"phase": 1, "bytes": true_len, "n": 1,
                     "server_ip": dst_ip if is_from_client else src_ip,
                     "server_port": dst_port if is_from_client else src_port}
            connections[client_key] = state
            continue
        if state["phase"] == 3:
            continue  # already closed -- later packets on this connection are ignored

        if state["phase"] == 1:
            if is_from_client and true_len > 0:
                state["phase"] = 2
                state["bytes"] += true_len
                state["n"] += 1
            elif not is_from_client:
                state["bytes"] += true_len
                state["n"] += 1
            # a client pure-ACK during phase 1 contributes 0 bytes either way -- skip silently
        elif state["phase"] == 2:
            if is_from_client and true_len > 0:
                state["bytes"] += true_len
                state["n"] += 1
            elif not is_from_client:
                state["phase"] = 3  # any server response at all closes the client's own flight
            # a client pure-ACK during phase 2: ignore, same reasoning as phase 1

    for client_key, state in connections.items():
        if state["phase"] != 3:
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

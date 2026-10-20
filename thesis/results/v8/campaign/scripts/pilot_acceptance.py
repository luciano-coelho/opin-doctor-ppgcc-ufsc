#!/usr/bin/env python3
"""Pilot acceptance criteria (PILOT_RUNBOOK.md) -- computes every
criterion FROM THE RAW DATA a pilot run actually produced (the tree
`campaign_pull.sh` pulls, Decision 53's own repository-mirroring
layout), prints PASS/FAIL per criterion, never fabricates a value it
can't derive from a real file. Reuses campaign_run.py's own
verify_negotiated_groups()/_CLIENT_EXPECTED_CURVE/_parse_chrony_tracking_text
rather than reimplementing the negotiated-group/clock logic a second
time.

Usage: python pilot_acceptance.py <pulled-data-root>
  (the directory campaign_pull.sh wrote into, e.g. ./pilot-data-pulled --
   this script looks for <root>/v8/latency/... underneath it, exactly
   the layout campaign_pull.sh's own rsync produces.)

Criteria, in the order PILOT_RUNBOOK.md lists them:
  1. total_bytes_exchanged per execution == the local-lab regression
     baseline (125,485 classic / 275,800 pqc / 331,639 hybrid).
  2. Client-side pcap's ClientHello: same SIZE and SNI as the local lab
     reference fixture (tests/fixtures/reference_clienthello.json --
     captured live against the local stack + netshoot, this turn, not
     hand-typed; see that file's own "_method" field).
  3. Negotiated group: client channel matches the profile's own curve,
     internal channel always CurveP256 (verify_negotiated_groups()).
  4. steal < 5% in every execution; max CPU/memory reported.
  5. RTT per scenario from the pcap (SYN -> SYN-ACK) vs. the reference
     ping.
  6. Bootstrap CI width of the per-cell median, relative to the median
     (+/-5% target) -- with a recommendation on run count if not met.
  7. T_fluxo with vs. without tcpdump (CAMPAIGN_TCPDUMP_AB_TEST, the
     pilot's own alternating A/B toggle) -- reports the difference if both groups
     exist in the data, or says so plainly if they don't.
  8. pcap + disk volume per execution, extrapolated to 720 executions,
     with a Git-LFS-vs-external-storage recommendation.
  9. campaign_pull.sh's own hash-manifest cycle, re-verified here too
     (not just trusted because `.pull-verified` exists).
"""
import gzip
import json
import math
import random
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import campaign_run as cr  # noqa: E402 -- reuse verify_negotiated_groups etc., not reimplement

BASELINE_BYTES = {"classic": 125_485, "pqc": 275_800, "hybrid": 331_639}
# Item 3 (this turn): no longer hand-typed constants -- read from a
# fixture captured live against the local lab stack (see that file's
# own "_method" field for exactly how), so a future re-capture is a
# file regeneration, not a source-code edit.
_CLIENTHELLO_FIXTURE_PATH = Path(__file__).resolve().parent / "tests" / "fixtures" / "reference_clienthello.json"


def _load_baseline_clienthello():
    data = json.loads(_CLIENTHELLO_FIXTURE_PATH.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}


BASELINE_CLIENTHELLO = _load_baseline_clienthello()
PROFILE_DIR = {"classic": "experiment1 - Classic", "pqc": "experiment2 - PQC", "hybrid": "experiment3 - Hybrid"}
STEAL_THRESHOLD_PCT = 5.0
BOOTSTRAP_CI_TARGET_PCT = 5.0
BOOTSTRAP_RESAMPLES = 2000


def find_scenario_dirs(root):
    """Yields (profile, scenario, path) for every scenario directory
    actually present under <root>/v8/latency/ -- does not assume which
    scenarios exist, reads the tree."""
    latency_root = Path(root) / "v8" / "latency"
    for profile, exp_dir in PROFILE_DIR.items():
        base = latency_root / exp_dir
        if not base.is_dir():
            continue
        for installation_dir in base.iterdir():
            if not installation_dir.is_dir():
                continue
            for scenario_dir in installation_dir.iterdir():
                if (scenario_dir / "runs").is_dir():
                    yield profile, f"{installation_dir.name}/{scenario_dir.name}", scenario_dir


_RUN_FILENAME_RE = re.compile(r"^run(\d+)\.json$")


def load_runs(scenario_path):
    """Loads every runs/run*.json, sorted by run number. Also computes
    each execution's real label -- the run dict itself has NO "label"
    key (campaign_client_runner.py/run_once_timed() never add one, see
    latency_automation.py). The two executors name their per-execution
    files DIFFERENTLY, confirmed by actually running both and looking
    at what landed on disk (item 4, this turn's own real LocalExecutor
    run against the local stack): SSHExecutor uses
    "w{window:02d}_run{run_index:02d}" (campaign_run.py's own real-AWS
    run_one_execution()), while LocalExecutor uses the bare
    "run{run_index:02d}" (no window prefix at all) for the SAME files
    (.pcap.gz/_cpu.jsonl/_gateway.log/_ping.json/.calls.jsonl) -- NOT a
    hypothetical, this was caught live: a first version of this
    function always assumed the SSHExecutor form and silently reported
    N/A for every criterion on real LocalExecutor output, because
    "w01_run01.calls.jsonl" doesn't exist when LocalExecutor actually
    wrote "run01.calls.jsonl". Resolved by checking which one is
    actually ON DISK (via the one file every execution always writes,
    calls.jsonl) rather than assuming either convention; defaults to
    the SSHExecutor form if neither is found (the real pilot/campaign
    only ever uses SSHExecutor, so that's the right default for data
    that doesn't exist yet to probe).
    Returns a list of (path, run_dict, run_index, label)."""
    runs = []
    for p in sorted((scenario_path / "runs").glob("run*.json")):
        m = _RUN_FILENAME_RE.match(p.name)
        if not m:
            continue  # e.g. a *.calls.jsonl sibling never matches run\d+\.json
        run_index = int(m.group(1))
        run = json.loads(p.read_text())
        window = run.get("window")
        label = None
        if window is not None:
            ssh_label = f"w{window:02d}_run{run_index:02d}"
            local_label = f"run{run_index:02d}"
            if (scenario_path / "runs" / f"{local_label}.calls.jsonl").exists() and \
                    not (scenario_path / "runs" / f"{ssh_label}.calls.jsonl").exists():
                label = local_label
            else:
                label = ssh_label
        runs.append((p, run, run_index, label))
    return runs


# ---------------------------------------------------------------------------
# Criterion 1: total_bytes_exchanged
# ---------------------------------------------------------------------------
def criterion_1(root):
    print("=== Criterion 1: total_bytes_exchanged == local-lab baseline ===")
    all_ok = True
    any_found = False
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        for run_path, run, run_index, label in load_runs(scenario_path):
            calls_path = scenario_path / "runs" / f"{label}.calls.jsonl" if label else None
            if not calls_path or not calls_path.exists():
                print(f"  SKIP {profile}/{scenario}/{run_path.name}: no calls.jsonl found")
                continue
            total = 0
            for line in calls_path.read_text().splitlines():
                if not line.strip():
                    continue
                call = json.loads(line)
                total += call.get("request_bytes", 0) + call.get("response_bytes", 0)
            any_found = True
            baseline = BASELINE_BYTES[profile]
            ok = total == baseline
            all_ok = all_ok and ok
            print(f"  {'PASS' if ok else 'FAIL'} {profile}/{scenario}/{run_path.name}: "
                  f"{total} (expected {baseline})")
    if not any_found:
        print("  N/A -- no calls.jsonl files found under this data root")
        return None
    return all_ok


# ---------------------------------------------------------------------------
# Minimal pure-stdlib pcap reader -- classic libpcap format (tcpdump's
# own `-w` default), gzip or plain. No external dependency added for
# this (scapy/dpkt aren't in thesis/scripts/requirements.txt and this
# project's own standing style avoids adding one for a single, narrow
# read-only parsing need).
# ---------------------------------------------------------------------------
def read_pcap_packets(path):
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


def parse_reference_ping_rtt(ping_json_path):
    """Parses `ping`'s own summary line
    ("rtt min/avg/max/mdev = a/b/c/d ms") out of the raw text this
    project's own run_one_execution() already stores -- real ping
    output, not reimplemented/estimated."""
    if not ping_json_path.exists():
        return None
    raw = json.loads(ping_json_path.read_text()).get("raw_ping_output")
    if not raw:
        return None
    m = re.search(r"rtt [\w/]+ = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", raw)
    if not m:
        return None
    return {"min_ms": float(m.group(1)), "avg_ms": float(m.group(2)), "max_ms": float(m.group(3))}


# ---------------------------------------------------------------------------
# Criterion 2: ClientHello size + SNI
# ---------------------------------------------------------------------------
def criterion_2(root):
    print("=== Criterion 2: client pcap ClientHello size+SNI == local lab ===")
    print(f"  reference fixture ({_CLIENTHELLO_FIXTURE_PATH.name}): "
          + ", ".join(f"{p}={v['size']}B/sni={v['sni']!r}" for p, v in BASELINE_CLIENTHELLO.items()))
    all_ok = True
    any_found = False
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        for run_path, run, run_index, label in load_runs(scenario_path):
            if not label:
                continue
            pcap_path = scenario_path / "client" / f"{label}.pcap.gz"
            if not pcap_path.exists():
                continue
            any_found = True
            found = find_first_clienthello(pcap_path)
            baseline = BASELINE_CLIENTHELLO[profile]
            if found is None:
                print(f"  FAIL {profile}/{scenario}/{label}: no ClientHello found in pcap")
                all_ok = False
                continue
            size, sni = found
            ok = size == baseline["size"] and sni == baseline["sni"]
            all_ok = all_ok and ok
            print(f"  {'PASS' if ok else 'FAIL'} {profile}/{scenario}/{label}: "
                  f"size={size} (expected {baseline['size']}), sni={sni!r} (expected {baseline['sni']!r})")
    if not any_found:
        print("  N/A -- no client pcaps found under this data root")
        return None
    return all_ok


# ---------------------------------------------------------------------------
# Criterion 3: negotiated group (reuses campaign_run.py's own function)
# ---------------------------------------------------------------------------
def criterion_3(root):
    print("=== Criterion 3: negotiated group -- client channel correct, internal always P-256 ===")
    all_ok = True
    any_found = False
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        for run_path, run, run_index, label in load_runs(scenario_path):
            if not label:
                continue
            gw_log_path = scenario_path / "server" / f"{label}_gateway.log"
            if not gw_log_path.exists():
                continue
            any_found = True
            text = gw_log_path.read_text()
            verification = cr.verify_negotiated_groups(text, cr._CLIENT_EXPECTED_CURVE[profile])
            all_ok = all_ok and verification["ok"]
            status = "PASS" if verification["ok"] else "FAIL"
            print(f"  {status} {profile}/{scenario}/{label}: client={verification['client_curves']}, "
                  f"internal={verification['internal_curves']}")
            if not verification["ok"]:
                for p in verification["problems"]:
                    print(f"      - {p}")
    if not any_found:
        print("  N/A -- no gateway logs found under this data root")
        return None
    return all_ok


# ---------------------------------------------------------------------------
# Criterion 4: steal < 5%, max CPU/memory
# ---------------------------------------------------------------------------
def _parse_proc_stat_line(line):
    fields = [int(x) for x in line.split()[1:]]
    while len(fields) < 8:
        fields.append(0)
    user, nice, system, idle, iowait, irq, softirq, steal = fields[:8]
    return {"total": sum(fields), "idle": idle, "steal": steal}


def _parse_proc_meminfo_raw(raw):
    meminfo = {}
    for line in raw.splitlines():
        key, _, rest = line.partition(":")
        meminfo[key.strip()] = rest.strip()
    return meminfo


def _normalize_cpu_mem_sample(sample):
    """Returns (stat_dict_or_None, mem_available_kb_or_None), regardless
    of which executor produced the sample -- caught live (item 4, this
    turn): SSHExecutor's sampler writes RAW /proc/stat and /proc/meminfo
    TEXT under "proc_stat_line"/"proc_meminfo_raw"; LocalExecutor's own
    _sample_cpu_mem_steal() writes ALREADY-PARSED dicts under "cpu"/
    "mem" instead -- a different schema, not a variant of the same one.
    Both schemas can legitimately carry None (SSHExecutor's text would
    be empty/missing; LocalExecutor's own dicts are None outright on a
    non-Linux host, e.g. this project's Windows dev machine, which has
    no /proc at all -- confirmed live, not assumed)."""
    if "proc_stat_line" in sample or "proc_meminfo_raw" in sample:
        stat = _parse_proc_stat_line(sample["proc_stat_line"]) if sample.get("proc_stat_line") else None
        mem = _parse_proc_meminfo_raw(sample["proc_meminfo_raw"]) if sample.get("proc_meminfo_raw") else {}
        avail_str = mem.get("MemAvailable", "").split()[0] if mem.get("MemAvailable") else None
        avail_kb = int(avail_str) if avail_str and avail_str.isdigit() else None
        return stat, avail_kb
    cpu, mem = sample.get("cpu"), sample.get("mem")
    stat = {"total": cpu["total"], "idle": cpu["idle"], "steal": cpu["steal"]} if cpu else None
    avail_kb = None
    if mem and mem.get("MemAvailable"):
        avail_str = mem["MemAvailable"].split()[0]
        avail_kb = int(avail_str) if avail_str.isdigit() else None
    return stat, avail_kb


def criterion_4(root):
    print("=== Criterion 4: steal < 5% every execution; max CPU/memory ===")
    all_ok = True
    any_found = False
    overall_max_cpu_pct = 0.0
    overall_min_mem_available_kb = None
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        for run_path, run, run_index, label in load_runs(scenario_path):
            if not label:
                continue
            cpu_path = scenario_path / "server" / f"{label}_cpu.jsonl"
            if not cpu_path.exists() or cpu_path.stat().st_size == 0:
                continue
            samples = [json.loads(l) for l in cpu_path.read_text().splitlines() if l.strip()]
            if len(samples) < 2:
                print(f"  SKIP {profile}/{scenario}/{label}: fewer than 2 CPU samples -- "
                      f"can't compute a steal/CPU DELTA from a single snapshot")
                continue
            max_steal_pct = 0.0
            max_cpu_pct = 0.0
            min_mem_available_kb = None
            usable_pairs = 0
            for a, b in zip(samples, samples[1:]):
                stat_a, _ = _normalize_cpu_mem_sample(a)
                stat_b, avail_kb = _normalize_cpu_mem_sample(b)
                if stat_a is None or stat_b is None:
                    continue  # no /proc on this host (e.g. LocalExecutor on Windows) -- not fabricated
                total_delta = stat_b["total"] - stat_a["total"]
                if total_delta <= 0:
                    continue
                usable_pairs += 1
                steal_pct = (stat_b["steal"] - stat_a["steal"]) / total_delta * 100
                busy_pct = 100 - (stat_b["idle"] - stat_a["idle"]) / total_delta * 100
                max_steal_pct = max(max_steal_pct, steal_pct)
                max_cpu_pct = max(max_cpu_pct, busy_pct)
                if avail_kb is not None:
                    min_mem_available_kb = avail_kb if min_mem_available_kb is None else min(min_mem_available_kb, avail_kb)
            if usable_pairs == 0:
                print(f"  SKIP {profile}/{scenario}/{label}: no /proc data in any sample pair "
                      f"(expected on a non-Linux executor host, e.g. LocalExecutor on Windows -- "
                      f"not computable there, not a fabricated 0%)")
                continue
            any_found = True
            ok = max_steal_pct < STEAL_THRESHOLD_PCT
            all_ok = all_ok and ok
            overall_max_cpu_pct = max(overall_max_cpu_pct, max_cpu_pct)
            if min_mem_available_kb is not None:
                overall_min_mem_available_kb = (
                    min_mem_available_kb if overall_min_mem_available_kb is None
                    else min(overall_min_mem_available_kb, min_mem_available_kb)
                )
            print(f"  {'PASS' if ok else 'FAIL'} {profile}/{scenario}/{label}: "
                  f"max steal={max_steal_pct:.2f}%, max CPU busy={max_cpu_pct:.2f}%")
    if not any_found:
        print("  N/A -- no multi-sample CPU/mem data found (needs >=2 samples/execution)")
        return None
    print(f"  Overall max CPU busy observed: {overall_max_cpu_pct:.2f}%")
    if overall_min_mem_available_kb is not None:
        print(f"  Overall minimum MemAvailable observed: {overall_min_mem_available_kb / 1024:.1f} MiB")
    return all_ok


# ---------------------------------------------------------------------------
# Criterion 5: RTT from pcap vs. reference ping
# ---------------------------------------------------------------------------
def criterion_5(root):
    print("=== Criterion 5: RTT from pcap (SYN->SYN-ACK) vs. reference ping ===")
    any_found = False
    by_scenario = {}
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        for run_path, run, run_index, label in load_runs(scenario_path):
            if not label:
                continue
            pcap_path = scenario_path / "client" / f"{label}.pcap.gz"
            ping_path = scenario_path / "client" / f"{label}_ping.json"
            if not pcap_path.exists():
                continue
            rtt = find_syn_synack_rtt(pcap_path)
            ping_rtt = parse_reference_ping_rtt(ping_path) if ping_path.exists() else None
            if rtt is None:
                continue
            any_found = True
            by_scenario.setdefault(scenario, []).append((rtt * 1000, ping_rtt))
    if not any_found:
        print("  N/A -- no pcap with a complete SYN/SYN-ACK pair found")
        return None
    for scenario, pairs in by_scenario.items():
        pcap_rtts = [p[0] for p in pairs]
        avg_pcap_rtt = sum(pcap_rtts) / len(pcap_rtts)
        ping_avgs = [p[1]["avg_ms"] for p in pairs if p[1]]
        if ping_avgs:
            avg_ping_rtt = sum(ping_avgs) / len(ping_avgs)
            diff_pct = abs(avg_pcap_rtt - avg_ping_rtt) / avg_ping_rtt * 100 if avg_ping_rtt else float("inf")
            print(f"  {scenario}: pcap SYN->SYN-ACK avg={avg_pcap_rtt:.2f}ms, "
                  f"reference ping avg={avg_ping_rtt:.2f}ms, diff={diff_pct:.1f}%")
        else:
            print(f"  {scenario}: pcap SYN->SYN-ACK avg={avg_pcap_rtt:.2f}ms, no reference ping data available")
    print("  (informational -- this criterion reports the comparison, it does not itself gate pass/fail;"
        " PILOT_RUNBOOK.md's own abort criteria cover a materially wrong RTT via the first-contact checklist.)")
    return True


# ---------------------------------------------------------------------------
# Criterion 6: bootstrap CI width of the median, per cell
# ---------------------------------------------------------------------------
def bootstrap_median_ci(values, resamples=BOOTSTRAP_RESAMPLES, seed=0):
    rng = random.Random(seed)
    n = len(values)
    medians = []
    for _ in range(resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        medians.append(sorted(sample)[n // 2] if n % 2 else
                        (sorted(sample)[n // 2 - 1] + sorted(sample)[n // 2]) / 2)
    medians.sort()
    lo = medians[int(0.025 * resamples)]
    hi = medians[int(0.975 * resamples) - 1]
    return lo, hi


def criterion_6(root):
    print("=== Criterion 6: bootstrap CI width of the per-cell median (target +/-5%) ===")
    any_found = False
    all_ok = True
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        durations = []
        for run_path, run, run_index, label in load_runs(scenario_path):
            d = (run.get("result") or {}).get("t_fluxo_seconds")
            if d is not None:
                durations.append(d)
        if len(durations) < 3:
            continue
        any_found = True
        median = sorted(durations)[len(durations) // 2]
        lo, hi = bootstrap_median_ci(durations)
        width_pct = (hi - lo) / median * 100 if median else float("inf")
        ok = width_pct <= BOOTSTRAP_CI_TARGET_PCT
        all_ok = all_ok and ok
        print(f"  {'PASS' if ok else 'FAIL'} {profile}/{scenario}: n={len(durations)}, "
              f"median={median:.3f}s, 95% CI=[{lo:.3f}, {hi:.3f}], width={width_pct:.1f}% of median")
        if not ok:
            # CI half-width scales roughly as 1/sqrt(n) -- so
            # n_needed ~= n_current * (current_width / target_width)^2.
            n_needed = math.ceil(len(durations) * (width_pct / BOOTSTRAP_CI_TARGET_PCT) ** 2)
            print(f"      recommendation: roughly {n_needed} runs/cell to reach the +/-5% target "
                  f"(currently {len(durations)}) -- a rough 1/sqrt(n) scaling estimate, not a guarantee")
    if not any_found:
        print("  N/A -- fewer than 3 durations in every cell found")
        return None
    return all_ok


# ---------------------------------------------------------------------------
# Criterion 7: T_fluxo with vs. without tcpdump
# ---------------------------------------------------------------------------
def criterion_7(root):
    print("=== Criterion 7: T_fluxo with vs. without tcpdump ===")
    with_tcpdump, without_tcpdump = [], []
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        for run_path, run, run_index, label in load_runs(scenario_path):
            result = run.get("result") or {}
            d = result.get("t_fluxo_seconds")
            if d is None:
                continue
            # tcpdump_enabled is True (capture) unless the pilot's own
            # A/B test (CAMPAIGN_TCPDUMP_AB_TEST) was explicitly on for
            # this run; missing entirely (data predating this field)
            # defaults to True, matching the always-capture default.
            enabled = result.get("tcpdump_enabled", True)
            if enabled:
                with_tcpdump.append(d)
            else:
                without_tcpdump.append(d)
    if not without_tcpdump:
        print("  N/A -- no executions found with tcpdump deliberately disabled "
              "(set CAMPAIGN_TCPDUMP_AB_TEST=1 before the pilot so capture alternates "
              "on/off one by one and produces a comparison group)")
        return None
    avg_with = sum(with_tcpdump) / len(with_tcpdump) if with_tcpdump else None
    avg_without = sum(without_tcpdump) / len(without_tcpdump)
    print(f"  with tcpdump (n={len(with_tcpdump)}): avg T_fluxo = {avg_with:.3f}s" if avg_with else
          "  with tcpdump: no comparison data")
    print(f"  without tcpdump (n={len(without_tcpdump)}): avg T_fluxo = {avg_without:.3f}s")
    if avg_with:
        overhead_pct = (avg_with - avg_without) / avg_without * 100 if avg_without else float("inf")
        print(f"  tcpdump overhead: {overhead_pct:+.1f}%")
    print("  (informational -- reports the real measured difference, does not itself gate pass/fail.)")
    return True


# ---------------------------------------------------------------------------
# Criterion 8: pcap/disk volume, extrapolated to 720 executions
# ---------------------------------------------------------------------------
def criterion_8(root):
    print("=== Criterion 8: pcap + disk volume per execution, extrapolated to 720 ===")
    total_bytes = 0
    n_executions = 0
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        for run_path, run, run_index, label in load_runs(scenario_path):
            if not label:
                continue
            files = [
                run_path,  # run{NN}.json itself -- NOT "{label}.json", a different filename convention
                scenario_path / "server" / f"{label}.pcap.gz",
                scenario_path / "client" / f"{label}.pcap.gz",
                scenario_path / "server" / f"{label}_gateway.log",
                scenario_path / "server" / f"{label}_cpu.jsonl",
                scenario_path / "client" / f"{label}_cpu.jsonl",
                scenario_path / "client" / f"{label}_ping.json",
                scenario_path / "runs" / f"{label}.calls.jsonl",
            ]
            size = sum(f.stat().st_size for f in files if f.exists())
            if size == 0:
                continue
            total_bytes += size
            n_executions += 1
    if n_executions == 0:
        print("  N/A -- no execution artifacts found to measure")
        return None
    avg_bytes = total_bytes / n_executions
    extrapolated_720_mb = avg_bytes * 720 / (1024 * 1024)
    print(f"  Measured: {n_executions} executions, avg {avg_bytes / 1024:.1f} KiB/execution "
          f"(both sides' pcaps + logs + cpu/mem/ping/calls data)")
    print(f"  Extrapolated to 720 executions: ~{extrapolated_720_mb:.1f} MiB")
    github_lfs_free_gb = 1  # GitHub's own free LFS storage/bandwidth quota, 1GB, as of this project's own era
    if extrapolated_720_mb / 1024 < github_lfs_free_gb * 0.5:
        print(f"  Recommendation: Git LFS -- well under GitHub's free {github_lfs_free_gb}GB quota "
              f"with comfortable margin.")
    else:
        print(f"  Recommendation: external storage with a sha256 manifest committed to the repo "
              f"(this project's own established pattern, Decision 57's pcap-bundling approach) -- "
              f"the extrapolated volume is close to or over GitHub's free LFS quota.")
    return True


# ---------------------------------------------------------------------------
# Criterion 9: campaign_pull.sh's hash manifest, re-verified
# ---------------------------------------------------------------------------
def criterion_9(root):
    print("=== Criterion 9: campaign_pull.sh cycle -- hash manifest re-verified ===")
    root = Path(root)
    verified_marker = root / ".pull-verified"
    manifest_path = root / "campaign-data.sha256"
    if not verified_marker.exists():
        print(f"  FAIL: {verified_marker} not found -- campaign_pull.sh either wasn't run or didn't "
              f"complete its own verification successfully.")
        return False
    if not manifest_path.exists():
        print(f"  FAIL: {manifest_path} not found alongside the pulled data.")
        return False
    import hashlib
    mismatches = []
    checked = 0
    for line in manifest_path.read_text().splitlines():
        if not line.strip():
            continue
        expected_hash, _, rel_path = line.partition("  ")
        target = root / rel_path.strip()
        if not target.exists():
            mismatches.append((rel_path, "MISSING"))
            continue
        actual_hash = hashlib.sha256(target.read_bytes()).hexdigest()
        checked += 1
        if actual_hash != expected_hash:
            mismatches.append((rel_path, "HASH MISMATCH"))
    if mismatches:
        print(f"  FAIL: {len(mismatches)}/{checked} files failed re-verification:")
        for rel_path, reason in mismatches[:10]:
            print(f"      {reason}: {rel_path}")
        return False
    print(f"  PASS: re-verified {checked} files against {manifest_path.name}, all match "
          f"(independent of campaign_pull.sh's own .pull-verified marker).")
    return True


CRITERIA = [
    ("1_total_bytes_exchanged", criterion_1),
    ("2_clienthello_size_sni", criterion_2),
    ("3_negotiated_group", criterion_3),
    ("4_steal_cpu_memory", criterion_4),
    ("5_rtt_pcap_vs_ping", criterion_5),
    ("6_bootstrap_ci_median", criterion_6),
    ("7_tcpdump_overhead", criterion_7),
    ("8_pcap_disk_volume", criterion_8),
    ("9_pull_manifest_reverify", criterion_9),
]


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <pulled-data-root>", file=sys.stderr)
        sys.exit(2)
    root = sys.argv[1]
    if not Path(root).is_dir():
        print(f"FATAL: {root} is not a directory.", file=sys.stderr)
        sys.exit(2)

    results = {}
    for name, fn in CRITERIA:
        results[name] = fn(root)
        print()

    print("=== SUMMARY ===")
    for name, result in results.items():
        label = "PASS" if result is True else ("FAIL" if result is False else "N/A")
        print(f"  {name}: {label}")

    hard_fails = [n for n, r in results.items() if r is False]
    print()
    if hard_fails:
        print(f"OVERALL: FAIL -- {len(hard_fails)} criterion/criteria failed: {', '.join(hard_fails)}")
        sys.exit(1)
    else:
        na = [n for n, r in results.items() if r is None]
        if na:
            print(f"OVERALL: PASS (with {len(na)} criterion/criteria N/A -- no applicable data found: "
                  f"{', '.join(na)})")
        else:
            print("OVERALL: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()

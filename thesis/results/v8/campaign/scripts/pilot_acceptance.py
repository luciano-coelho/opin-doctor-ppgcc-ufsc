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
     reference fixture (tests/fixtures/reference_clienthello.json).
     Snaplen is 256 bytes (TCPDUMP_SNAPLEN_BYTES, campaign_run.py, raised
     from 128 on 2026-10-22 -- DECISIONS.md) specifically so SNI ("mtls",
     at TLS-payload offset ~97) is recoverable; confirmed against a real
     local capture at 256. Size needs only the TLS record header (first
     5 bytes), always within the first captured segment regardless of
     snaplen or how many real TCP segments the ClientHello spans -- no
     reassembly needed either way.
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
  10. OPINsize's 4 terms (handshake, JWT, JWK, PKI) all present at L0
      for every profile, the complete total within +/-3% of v7's own
      figure (76,929/322,895/350,477 classic/pqc/hybrid -- see this
      file's own OPINSIZE_TOLERANCE_PCT comment for why 3%), and no
      `_FIXTURE`-tagged value anywhere in the consolidated data a real
      pilot run produces.
  11. Gateway-vs-pcap handshake-bytes diff, per scenario (L0 and L325):
      reports the diff%, and signals if it shifts by more than
      HANDSHAKE_DIFF_RTT_SHIFT_THRESHOLD_PP (5 percentage points,
      justified in that constant's own comment) between the two --
      consistent with a real RTT dependence, not just per-connection
      noise. Informational: it signals, it does not itself switch
      consolidate_v8.py's own HANDSHAKE_SOURCE.
"""
import json
import math
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import campaign_run as cr  # noqa: E402 -- reuse verify_negotiated_groups etc., not reimplement
import consolidate_v8 as cv8  # noqa: E402 -- reuse the real OPINsize/term computation, not reimplement
from pcap_utils import (  # noqa: E402 -- shared with consolidate_v8.py, see that module's own import comment
    read_pcap_packets,
    parse_tcp_packet,
    parse_tcp_packet_true_len,
    extract_clean_handshake_bytes,
    extract_sni,
    find_first_clienthello,
    find_syn_synack_rtt,
)

# Recalibrated 2026-10-25 (DECISIONS.md, Decision 87 -- "fluxo completo"
# turn): opin_flow.py now verifies every signed artifact it receives
# (id_token, JARM, RS-signed responses), which needed ONE new real call
# per sub-flow -- the RS's own /jwks, fetched once right after the first
# access token (the earliest point it can be: that endpoint itself
# requires a Bearer token, confirmed live) -- not in the original 42-call
# count at all. call_count is now 44 (was 42), confirmed identical across
# all 3 profiles; N_JWT stays 28 (unaffected -- the new calls aren't JWT-
# bearing); N_JWK rises (more keys published per /jwks response now that
# there are 4 fetches instead of 2, not 2 new keys per profile uniformly
# -- see Decision 87's own table). The two previous values in this dict's
# history (125,485 pre-Decision-85, 125,065 post-Decision-85) both
# predate this change; re-verified the same way Decision 85 established
# the method: a fresh local-lab run of the CURRENT code, same day,
# reproducing the exact same per-call bytes as a second independent run.
# Re-running this capture after any future change to opin_flow.py's
# call-recording path (do_call()/_capture_hop()/header_bytes()) OR its
# verification path (the new RS /jwks fetch, id_token/JARM decode) is the
# correct way to refresh it, not hand-editing the numbers.
BASELINE_BYTES = {"classic": 126_777, "pqc": 281_654, "hybrid": 339_145}
# Item 3 (2026-10-22): v7's own report_data_v7.json OPINsize figures.
V7_OPINSIZE = {"classic": 76_929, "pqc": 322_895, "hybrid": 350_477}
# Tolerance, justified: this turn's own real local-flow measurement
# against v7 (DECISIONS.md, the handshake-bytes-term investigation)
# found classic +0.47%, pqc +0.00%, hybrid +1.70% -- a SINGLE real
# execution against v7's own 60-run median, not an average of many, so
# some run-to-run jitter against that median is expected and not itself
# a regression. 3% is roughly double the largest of those three real
# deviations (1.70%): tight enough that a genuine regression (a wrong
# curve negotiated, a broken digest pin changing cert sizes, a missed
# JARM/PKI correction) -- which this project's own history shows moves
# OPINsize by single-digit-to-double-digit PERCENT, not fractions of a
# percent (Decision 11's JARM fix: +1.6%; Decision 14's PQC CA fix:
# +19.1%) -- would still fail loudly, while ordinary single-execution
# noise does not.
OPINSIZE_TOLERANCE_PCT = 3.0
# Criterion 11 (2026-10-22): how much the gateway-vs-pcap handshake-bytes
# diff% is allowed to shift between L0 and L325 before it's treated as
# RTT-dependent rather than ordinary per-connection noise. Justified from
# this turn's own real local measurement (DECISIONS.md): the diff% WITHIN
# one scenario (same L0, same profile, 7 real connections each) already
# spans up to 2.2 percentage points on its own (classic: -3.3% to -5.5%;
# pqc: -10.0% to -10.4%, only 0.4pp; hybrid: -2.3% to -2.9%, 0.6pp) purely
# from which first-request happens to leak into the gateway's own count --
# nothing to do with RTT, since L0 has ~0ms RTT throughout. 5 percentage
# points is more than double the largest of those three spreads: tight
# enough to catch a real RTT-driven shift, loose enough not to fire on
# ordinary per-connection noise alone.
HANDSHAKE_DIFF_RTT_SHIFT_THRESHOLD_PP = 5.0
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
# Pcap/TCP/TLS parsing primitives moved to pcap_utils.py (2026-10-22) --
# shared with consolidate_v8.py, which would otherwise need to import
# this module while this module already imports IT (circular).
# ---------------------------------------------------------------------------


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
    print("=== Criterion 2: client pcap ClientHello size + SNI == local lab ===")
    print(f"  reference fixture ({_CLIENTHELLO_FIXTURE_PATH.name}): "
          + ", ".join(f"{p}={v['size']}B/sni={v['sni']!r}" for p, v in BASELINE_CLIENTHELLO.items()))
    # 2026-10-22: SNI gating restored now that the real campaign snaplen
    # is 256 bytes (TCPDUMP_SNAPLEN_BYTES in campaign_run.py, raised from
    # 128 -- DECISIONS.md). At 128, SNI ("mtls", TLS-payload offset ~97)
    # was never recoverable (~62 bytes of payload actually captured,
    # confirmed directly) -- gating on it then would have failed every
    # real pilot execution unconditionally, which is why this criterion
    # spent one turn gating on size only. At 256, a real local capture
    # recovers SNI exactly (`(341/1784/1881, 'mtls')`, all 3 profiles),
    # so both size and SNI gate again, same as this criterion's own
    # original design. ClientHello size itself was never affected by
    # snaplen either way (only needs the TLS record header's own length
    # field, always within the first captured segment).
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
                print(f"  FAIL {profile}/{scenario}/{label}: no ClientHello found in pcap at all")
                all_ok = False
                continue
            size, sni = found
            ok = size == baseline["size"] and sni == baseline["sni"]
            all_ok = all_ok and ok
            sni_note = f", sni={sni!r} (expected {baseline['sni']!r})"
            print(f"  {'PASS' if ok else 'FAIL'} {profile}/{scenario}/{label}: "
                  f"size={size} (expected {baseline['size']}){sni_note}")
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
            # Pilot item 3 (this turn): found live, real pilot data --
            # a sampler file can end up with a malformed line (null-byte
            # gap from a concurrent writer -- see DECISIONS.md, the
            # per-execution background-process cleanup gap this same
            # turn found and fixed in campaign_run.py) when a run was
            # interrupted and retried before this fix landed. One bad
            # line used to crash this entire script outright, hiding
            # every criterion after it; skipped here instead, counted
            # and reported, not silently dropped.
            raw_lines = [l for l in cpu_path.read_text(errors="replace").splitlines() if l.strip()]
            samples = []
            bad_lines = 0
            for l in raw_lines:
                try:
                    samples.append(json.loads(l))
                except json.JSONDecodeError:
                    bad_lines += 1
            if bad_lines:
                print(f"  WARNING {profile}/{scenario}/{label}: {bad_lines}/{len(raw_lines)} CPU-sample "
                      f"line(s) malformed (skipped, not fabricated) -- see DECISIONS.md for the known cause")
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
    # campaign_pull.sh's own $DEST has ".pull-verified"/"campaign-data.sha256"
    # directly alongside "v8/" (both root's own direct children) -- true right
    # after a pull, before anything is reorganized. Once that data is moved
    # into the repository's own long-term thesis/results/v8/latency/
    # location (Decision 85), "root" for every OTHER criterion here becomes
    # the directory ABOVE "v8/" (so find_scenario_dirs()'s own root/v8/latency
    # still resolves) -- one level higher than where the pull itself left
    # these two files. Checking root/v8/ as a fallback (not a replacement)
    # keeps BOTH the original post-pull, pre-reorganization check (root IS
    # $DEST) and the final, committed-repo check (root is $DEST's own
    # parent, "v8" is now one path segment further down) working, instead of
    # breaking whichever case isn't being run at a given moment.
    base = root if (root / ".pull-verified").exists() else root / "v8"
    verified_marker = base / ".pull-verified"
    manifest_path = base / "campaign-data.sha256"
    if not verified_marker.exists():
        print(f"  FAIL: {verified_marker} not found (also checked {root / '.pull-verified'}) -- "
              f"campaign_pull.sh either wasn't run or didn't complete its own verification successfully.")
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
        # Always relative to `root`, never `base`: the manifest's own
        # entries are already "v8/latency/..." (campaign_pull.sh's own
        # $DEST-relative paths, unchanged by where .pull-verified/
        # campaign-data.sha256 themselves ended up) -- resolving them
        # against `base` when base == root/"v8" would double up the
        # "v8" segment.
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


# ---------------------------------------------------------------------------
# Criterion 10 (2026-10-22, follow-up to the handshake-bytes-term
# investigation): OPINsize's 4 terms, complete and within tolerance, for
# every profile's L0 scenario -- real data only, never a _FIXTURE.
# ---------------------------------------------------------------------------
def criterion_10(root):
    print("=== Criterion 10: OPINsize complete (4 terms) and within tolerance at L0, no _FIXTURE ===")
    all_ok = True
    any_found = False
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        if scenario_path.name != "L0":
            continue  # "any profile's L0 scenario" (this criterion's own spec) -- every server's own L0, not just sa-east-1's
        any_found = True
        result = cv8.consolidate_profile_scenario(scenario_path, profile)
        if result is None:
            print(f"  FAIL {profile}/{scenario}: no clean runs found at L0")
            all_ok = False
            continue

        term_names = {"term_handshake": result["term_handshake"]["status"] == "covered",
                      "term_jwt": result["term_jwt"] is not None,
                      "term_jwk": result["term_jwk"] is not None,
                      "term_pki": result["term_pki"] is not None}
        missing = [name for name, present in term_names.items() if not present]
        if missing:
            print(f"  FAIL {profile}/{scenario}: missing term(s) {missing} -- OPINsize cannot be complete")
            all_ok = False
            continue

        opinsize = result["opinsize"]
        if not opinsize or opinsize["status"] != "complete":
            print(f"  FAIL {profile}/{scenario}: OPINsize status {opinsize['status'] if opinsize else None} "
                  f"(expected 'complete')")
            all_ok = False
            continue

        value = opinsize["value_bytes"]
        v7v = V7_OPINSIZE[profile]
        pct_diff = abs(value - v7v) / v7v * 100
        ok = pct_diff <= OPINSIZE_TOLERANCE_PCT
        all_ok = all_ok and ok
        print(f"  {'PASS' if ok else 'FAIL'} {profile}/{scenario}: OPINsize {value:.0f} bytes "
              f"(v7: {v7v}, diff {pct_diff:.2f}%, tolerance +/-{OPINSIZE_TOLERANCE_PCT}%)")

        # Fixture leak check: scans the ACTUAL result dict this criterion
        # just built from the pilot's own real data -- not the generator's
        # source code -- so a future regression that silently reintroduces
        # a fixture value is caught here, at the data, not trusted away.
        dump = json.dumps(result)
        if "_FIXTURE" in dump or "FIXTURE" in dump.upper():
            print(f"  FAIL {profile}/{scenario}: a _FIXTURE-tagged value was found in data generated "
                  f"from the real pilot -- this must never happen outside a test.")
            all_ok = False

    if not any_found:
        print("  N/A -- no L0 scenario directories found under this data root")
        return None
    return all_ok


# ---------------------------------------------------------------------------
# Criterion 11 (2026-10-22): gateway-vs-pcap handshake-bytes diff, per
# scenario (L0 and L325), and whether it shifts with RTT.
# ---------------------------------------------------------------------------
def criterion_11(root):
    print("=== Criterion 11: gateway-vs-pcap handshake diff, L0 vs L325 (RTT dependence) ===")
    diffs_by_profile_scenario = {}  # (profile, scenario) -> diff_pct
    any_found = False
    for profile, scenario, scenario_path in find_scenario_dirs(root):
        if scenario_path.name not in ("L0", "L325"):
            continue
        result = cv8.consolidate_profile_scenario(scenario_path, profile)
        if result is None:
            continue
        diff = result.get("term_handshake_gateway_vs_pcap_diff")
        if not diff or diff["diff_pct"] is None:
            print(f"  SKIP {profile}/{scenario}: gateway and/or pcap handshake value not both available")
            continue
        any_found = True
        diffs_by_profile_scenario[(profile, scenario_path.name)] = diff["diff_pct"]
        print(f"  {profile}/{scenario}: gateway-vs-pcap diff = {diff['diff_pct']:+.2f}% "
              f"({diff['diff_bytes']:+.0f} bytes)")

    if not any_found:
        print("  N/A -- no scenario has both a gateway handshake value and a pcap handshake value")
        return None

    any_shift = False
    any_compared = False
    for profile in PROFILE_DIR:
        d0 = diffs_by_profile_scenario.get((profile, "L0"))
        d325 = diffs_by_profile_scenario.get((profile, "L325"))
        if d0 is None or d325 is None:
            print(f"  {profile}: L0 and/or L325 diff% not both available -- cannot compare RTT dependence yet")
            continue
        any_compared = True
        shift = abs(d325 - d0)
        print(f"  {profile}: L0={d0:+.2f}% L325={d325:+.2f}% shift={shift:.2f}pp "
              f"(threshold {HANDSHAKE_DIFF_RTT_SHIFT_THRESHOLD_PP}pp)")
        if shift > HANDSHAKE_DIFF_RTT_SHIFT_THRESHOLD_PP:
            any_shift = True
            print(f"    SIGNAL: {profile}'s gateway-vs-pcap diff shifts by {shift:.2f}pp between L0 and L325, "
                  f"above the {HANDSHAKE_DIFF_RTT_SHIFT_THRESHOLD_PP}pp threshold -- consistent with a "
                  f"real RTT dependence, not just per-connection noise. Recommendation: set "
                  f"consolidate_v8.py's own HANDSHAKE_SOURCE = \"pcap\" for this profile's own OPINsize "
                  f"handshake term (Luciano's own call -- this criterion signals, it does not switch "
                  f"the setting itself).")
    if any_compared and not any_shift:
        print("  No profile's gateway-vs-pcap diff shifts beyond the threshold between L0 and L325 -- "
              "no RTT-dependence signal; HANDSHAKE_SOURCE can stay \"gateway\" (comparability with v7).")
    elif not any_compared:
        print("  L325 data not available yet -- RTT-dependence comparison deferred until the real pilot "
              "produces it; the L0-only diffs above are still real and worth keeping an eye on.")
    print("  (informational -- this criterion reports and signals, it does not itself gate pass/fail; "
          "the signal above is what should inform changing HANDSHAKE_SOURCE, not an automatic switch.)")
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
    ("10_opinsize_complete_within_tolerance", criterion_10),
    ("11_handshake_gateway_vs_pcap_rtt_dependence", criterion_11),
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

#!/usr/bin/env python3
"""B.12: unit tests for verify_negotiated_groups() -- pure-function,
synthetic `docker logs -t` text, no Docker/AWS needed. Covers: the
happy path for all 3 profiles (client channel + internal carve-out
channel both correct), a forced-wrong client curve (per profile), a
forced-wrong internal curve (regression of the SNI carve-out), and an
unpaired carve-out line. Run directly: `python tests/test_negotiated_groups.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import campaign_run as cr

ADDR_CLIENT = "203.0.113.10:51000"
ADDR_INTERNAL = "203.0.113.10:51002"


def _line(ts, obj):
    import json
    return f"{ts} {json.dumps(obj)}"


def _handshake_line(ts, remote_addr, curve_id):
    return _line(ts, {"time": ts, "level": "INFO", "msg": cr._HANDSHAKE_COMPLETE_MSG,
                       "remoteAddr": remote_addr, "curveID": curve_id})


def _carveout_line(ts, remote_addr, sni="matls-api.local"):
    return _line(ts, {"time": ts, "level": "INFO", "msg": cr._CARVEOUT_MSG,
                       "sni": sni, "remoteAddr": remote_addr})


def _happy_path_log(client_curve):
    return "\n".join([
        _carveout_line("2026-10-13T19:00:00.000000000Z", ADDR_INTERNAL),
        _handshake_line("2026-10-13T19:00:00.050000000Z", ADDR_INTERNAL, "CurveP256"),
        _handshake_line("2026-10-13T19:00:00.100000000Z", ADDR_CLIENT, client_curve),
    ])


def test_happy_path_all_profiles():
    print("=== happy path: client curve correct + internal carve-out correct, all 3 profiles ===")
    ok_all = True
    for profile, expected_curve in cr._CLIENT_EXPECTED_CURVE.items():
        log = _happy_path_log(expected_curve)
        r = cr.verify_negotiated_groups(log, expected_curve)
        ok = r["ok"] and r["client_curves"] == [expected_curve] and r["internal_curves"] == ["CurveP256"]
        print(f"  {profile}: ok={r['ok']} client={r['client_curves']} internal={r['internal_curves']} "
              f"{'PASS' if ok else 'FAIL'}")
        ok_all = ok_all and ok
    return ok_all


def test_forced_wrong_client_curve_all_profiles():
    print("=== forced WRONG client curve -> must abort (ok=False), all 3 profiles ===")
    ok_all = True
    wrong_curve = "CurveP521"  # not any profile's expected client curve
    for profile, expected_curve in cr._CLIENT_EXPECTED_CURVE.items():
        log = _happy_path_log(wrong_curve)
        r = cr.verify_negotiated_groups(log, expected_curve)
        ok = (not r["ok"]) and any("CLIENT-FACING" in p for p in r["problems"])
        print(f"  {profile}: ok={r['ok']} problems={r['problems']} {'PASS' if ok else 'FAIL'}")
        ok_all = ok_all and ok
    return ok_all


def test_forced_wrong_internal_curve():
    print("=== forced WRONG internal (carve-out) curve -> regression, must abort ===")
    log = "\n".join([
        _carveout_line("2026-10-13T19:00:00.000000000Z", ADDR_INTERNAL),
        _handshake_line("2026-10-13T19:00:00.050000000Z", ADDR_INTERNAL, "CurveP384"),  # wrong -- should be P256
        _handshake_line("2026-10-13T19:00:00.100000000Z", ADDR_CLIENT, "CurveP384"),
    ])
    r = cr.verify_negotiated_groups(log, "CurveP384")
    ok = (not r["ok"]) and any("INTERNAL" in p and "regression" in p for p in r["problems"])
    print(f"  ok={r['ok']} problems={r['problems']} {'PASS' if ok else 'FAIL'}")
    return ok


def test_unpaired_carveout_is_a_failure():
    print("=== carve-out line with NO matching handshake-complete line -> unpaired failure ===")
    log = _carveout_line("2026-10-13T19:00:00.000000000Z", ADDR_INTERNAL)  # no handshake line at all
    r = cr.verify_negotiated_groups(log, "CurveP384")
    ok = (not r["ok"]) and any("UNPAIRED" in p for p in r["problems"])
    print(f"  ok={r['ok']} problems={r['problems']} {'PASS' if ok else 'FAIL'}")
    return ok


def test_correlation_window_prevents_cross_connection_mismatch():
    print("=== carve-out line far outside the correlation window -> NOT paired, handshake judged as client channel ===")
    log = "\n".join([
        _carveout_line("2026-10-13T19:00:00.000000000Z", ADDR_CLIENT),  # same addr, reused port, long ago
        _handshake_line("2026-10-13T19:01:00.000000000Z", ADDR_CLIENT, "CurveP384"),  # 60s later -- different connection
    ])
    r = cr.verify_negotiated_groups(log, "CurveP384", window_seconds=5.0)
    # Not paired (60s > 5s window) -> judged as client channel with correct curve (ok)
    # but the carve-out line itself is now unpaired -> a problem.
    ok = any("UNPAIRED" in p for p in r["problems"]) and "CurveP384" in r["client_curves"]
    print(f"  ok={r['ok']} client={r['client_curves']} problems={r['problems']} {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    results = {
        "happy_path_all_profiles": test_happy_path_all_profiles(),
        "forced_wrong_client_curve_all_profiles": test_forced_wrong_client_curve_all_profiles(),
        "forced_wrong_internal_curve": test_forced_wrong_internal_curve(),
        "unpaired_carveout_is_a_failure": test_unpaired_carveout_is_a_failure(),
        "correlation_window_prevents_cross_connection_mismatch": test_correlation_window_prevents_cross_connection_mismatch(),
    }
    print("\n=== SUMMARY ===")
    for k, v in results.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    sys.exit(0 if all(results.values()) else 1)

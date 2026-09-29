"""
Applies a second, related correction to thesis/results/v7/report_data_v7.json:
total_bytes_exchanged and bytes_by_participant (and its AS/RS decomposition,
apply_jarm_correction.py's own fix). This one closes the byte-total gap the
same finding left open (see DECISIONS.md, Decision 11's "What remains open").

Root cause (same as the JARM fix): simulate_login()'s login/consent traffic
(GET /auth, POST /login, POST /confirm, and every redirect hop `requests`
follows for each) ran entirely outside do_call(), so total_bytes_exchanged
and bytes_by_participant never saw it. opin_flow.py now instruments this
traffic with a session-level response hook (see its simulate_login()
docstring), closing the gap at the source going forward.

The already-collected v7 raw dataset (180 files) predates this second fix
too and has no field to recover the missing bytes from, so -- same
reasoning and same justification as the JARM correction (deterministic
quantity, already-established 0.00% spread on every size metric in this
dataset) -- this script applies the correction analytically, using one
fresh, isolated, single run per profile through the now-fixed pipeline
(thesis/scripts/.venv's pinned `requests` version, per Decision 10's own
environment-drift finding -- the global interpreter's newer `requests`
produces slightly different header byte counts and was deliberately NOT
used here):

    classic: total_requests 28->42, total_bytes_exchanged 66,828->125,065
    pqc:     total_requests 28->42, total_bytes_exchanged 185,013->259,552
    hybrid:  total_requests 28->42, total_bytes_exchanged 255,276->331,219

The new traffic is 100% AS-side (every request in simulate_login() targets
auth.local paths; the RS and PKI/CRL are never touched by the login flow),
so the whole delta is attributed to the AS entry of participants_decomposed
-- verified below to reconcile exactly with the new Other/Client totals,
the same reconciliation check Decision 10 used to validate the original
decomposition.

Usage: python thesis/scripts/apply_login_traffic_correction.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_PATH = REPO / "thesis" / "results" / "v7" / "report_data_v7.json"

# Measured live, once per profile, through the fixed pipeline (see module
# docstring) -- deterministic, not a statistical sample.
NEW_TOTAL_REQUESTS = 42
NEW_TOTAL_BYTES = {"classic": 125065, "pqc": 259552, "hybrid": 331219}
NEW_BYTES_BY_PARTICIPANT = {
    "classic": {
        "Client": {"sent_bytes": 21854, "received_bytes": 103211},
        "Other": {"sent_bytes": 94359, "received_bytes": 21122},
        "PKI/CRL": {"sent_bytes": 8852, "received_bytes": 732},
    },
    "pqc": {
        "Client": {"sent_bytes": 51679, "received_bytes": 207873},
        "Other": {"sent_bytes": 191261, "received_bytes": 50947},
        "PKI/CRL": {"sent_bytes": 16612, "received_bytes": 732},
    },
    "hybrid": {
        "Client": {"sent_bytes": 69354, "received_bytes": 261865},
        "Other": {"sent_bytes": 224097, "received_bytes": 68622},
        "PKI/CRL": {"sent_bytes": 37768, "received_bytes": 732},
    },
}

data = json.loads(DATA_PATH.read_text(encoding="utf-8"))

print(f"{'profile':10s} {'requests':16s} {'total_bytes (old->new)':28s} {'delta':>18s}")
for prof, new_total in NEW_TOTAL_BYTES.items():
    s = data["size"][prof]
    old_total = s["total_bytes"]
    old_requests = s["total_requests"]

    s["total_requests_corrected"] = NEW_TOTAL_REQUESTS
    s["total_bytes_corrected"] = new_total
    s["bytes_by_participant_corrected"] = NEW_BYTES_BY_PARTICIPANT[prof]

    delta = new_total - old_total
    print(f"{prof:10s} {old_requests:3d} -> {NEW_TOTAL_REQUESTS:<10d} "
          f"{old_total:10d} -> {new_total:<12d} "
          f"+{delta:8d} (+{delta / old_total * 100:.2f}%)")

print()
print(f"{'profile':10s} {'AS sent (old->new)':24s} {'AS received (old->new)':26s}")
for prof in NEW_TOTAL_BYTES:
    pd = data["participants_decomposed"][prof]
    old_as_sent, old_as_recv = pd["AS"]["sent_bytes"], pd["AS"]["received_bytes"]
    old_other = {
        "sent_bytes": old_as_sent + pd["RS"]["sent_bytes"],
        "received_bytes": old_as_recv + pd["RS"]["received_bytes"],
    }
    new_other = NEW_BYTES_BY_PARTICIPANT[prof]["Other"]

    # RS and PKI/CRL are never touched by simulate_login() -- the whole
    # Other-bucket delta is AS-side login/JARM traffic.
    new_as_sent = old_as_sent + (new_other["sent_bytes"] - old_other["sent_bytes"])
    new_as_recv = old_as_recv + (new_other["received_bytes"] - old_other["received_bytes"])

    # Reconciliation, same check Decision 10 used: AS_corrected + RS must
    # equal the newly measured Other bucket exactly.
    assert new_as_sent + pd["RS"]["sent_bytes"] == new_other["sent_bytes"], f"{prof}: AS+RS sent != Other sent"
    assert new_as_recv + pd["RS"]["received_bytes"] == new_other["received_bytes"], f"{prof}: AS+RS received != Other received"

    pd["AS_corrected"] = {"sent_bytes": new_as_sent, "received_bytes": new_as_recv}
    pd["Client_corrected"] = NEW_BYTES_BY_PARTICIPANT[prof]["Client"]

    print(f"{prof:10s} {old_as_sent:6d} -> {new_as_sent:<12d} {old_as_recv:6d} -> {new_as_recv:<12d}")

DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nWrote corrected fields into {DATA_PATH}")

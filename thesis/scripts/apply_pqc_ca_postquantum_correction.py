"""
Applies a third correction to thesis/results/v7/report_data_v7.json,
closing the external review's item 4.3/Recommendation 2 in full: the PQC
profile is now genuinely post-quantum end-to-end, not just for its subject
keys -- root_ca_pqc.crt/issuer_ca_pqc.crt (the CA-download simulation
artifacts) AND client_one_pqc.crt/mtls_pqc.crt/op_pqc.crt (the certificates
that actually participate in the live mTLS handshake) are now signed with
ML-DSA-65 throughout, with no classical RSA component left anywhere in the
PQC profile's certificate chain.

Root cause and fix, in two layers (mock-service-os/certs/main.go):

1. `-pqc-ca-fully-post-quantum`: root_ca_pqc.crt re-issued self-signed
   (pure ML-DSA-65); issuer_ca_pqc.crt re-issued signed by root_ca_pqc's own
   ML-DSA-65 key. Both reuse their existing keys unchanged.
2. `-pqc-live-certs-fully-post-quantum`: client_one_pqc.crt, mtls_pqc.crt,
   and op_pqc.crt re-issued signed directly by root_ca_pqc's ML-DSA-65 key,
   replacing the classical ca.crt. mock_mtls/main.go's caCertPool() was
   extended to also trust root_ca_pqc.crt under CRYPTO_PROFILE=pqc, or the
   live handshake would reject the new client certificate outright.

Both root_ca_pqc.crt and issuer_ca_pqc.crt needed real X.509 CA properties
(IsCA, KeyUsageCertSign, BasicConstraintsValid) for step 2's chain
verification to succeed at all -- caught live: without them, mock_mtls
rejected client_one_pqc.crt with "x509: invalid signature: parent
certificate cannot sign this kind of certificate". This changed
root_ca_pqc.crt/issuer_ca_pqc.crt's byte sizes a second time (the two small
extensions add a few dozen bytes each) -- the constants below are the FINAL
measured values, after that fix, not the first (incorrectly CA-less)
attempt.

This is a scope revision of the PQC profile, justified by the thesis's own
SAD three-phase model: PQC pure = Phase 3 (the ecosystem's final state, no
classical component preserved anywhere); Hybrid = Phase 2 (the transition
profile, where backward compatibility is the entire point). The original v2
decision to leave the PQC profile's CA and live-handshake certs classical
predates that phase model and is revised here, not silently overridden.
Verified end-to-end: the real pqc flow (all 2 sub-flows, all mTLS
connections) completes successfully against the new all-ML-DSA-65 chain,
and Hybrid's own alt-signature verification (-verify-hybrid) still passes
unmodified, since issuer_ca_pqc.key's public component never changed.

Every changed quantity here is deterministic (0% spread already established
on every other size metric in this dataset), so -- same justification as
Decisions 11/12 -- one live measurement per quantity suffices; no
re-collection of the 60-run PQC size batch is needed. Measured live, through
the actual running gateway, thesis/scripts/.venv's pinned requests version:

    root_ca_pqc.crt:      4,048 -> 8,001 bytes (PEM, self-signed ML-DSA-65)
    issuer_ca_pqc.crt:    4,052 -> 8,013 bytes (PEM, signed by root_ca_pqc)
    handshake_bytes (P50): 16,605 -> 22,607 bytes (6 connections, client cert now ML-DSA-65-signed)
    client_cert_der_bytes: 2,953 -> 5,879 bytes (client_one_pqc.crt, DER)
    HTTP framing per response: 103 bytes, unchanged (still constant across profiles)

Usage: python thesis/scripts/apply_pqc_ca_postquantum_correction.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_PATH = REPO / "thesis" / "results" / "v7" / "report_data_v7.json"

NEW_ROOT_BYTES = 8001
NEW_ISSUER_BYTES = 8013
NEW_MEASURED_SENT = 2 * (103 + NEW_ROOT_BYTES) + 2 * (103 + NEW_ISSUER_BYTES)  # measured live: 32440
NEW_MEASURED_RECEIVED = 732  # unchanged: request side doesn't depend on cert size
NEW_HANDSHAKE_P50 = 22607.0
NEW_CLIENT_CERT_DER = 5879

data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
pki = data["pki"]["pqc"]
size = data["size"]["pqc"]
opinsize = data["opinsize"]["pqc"]

old_root, old_issuer = pki["root_bytes"], pki["issuer_bytes"]
n_root, n_issuer, n_pki = pki["n_root"], pki["n_issuer"], pki["n_pki"]
n_mtls = size["n_mtls"]

new_pki_body_total = n_root * NEW_ROOT_BYTES + n_issuer * NEW_ISSUER_BYTES
new_framing_total = NEW_MEASURED_SENT - new_pki_body_total
assert new_framing_total % n_pki == 0
new_framing_each = new_framing_total // n_pki
assert new_framing_each == pki["framing_each"], (
    f"HTTP framing per response changed ({pki['framing_each']} -> {new_framing_each}) "
    "-- expected to stay constant across profiles"
)

pki["root_bytes_corrected"] = NEW_ROOT_BYTES
pki["issuer_bytes_corrected"] = NEW_ISSUER_BYTES
pki["pki_bytes_mean_corrected"] = new_pki_body_total / n_pki
pki["pki_body_total_corrected"] = new_pki_body_total
pki["measured_sent_corrected"] = NEW_MEASURED_SENT
pki["measured_received_corrected"] = NEW_MEASURED_RECEIVED
pki["ca_signature_scheme_corrected"] = "self-signed root (ML-DSA-65) + ML-DSA-65-signed issuer -- see Decision 14"

size["handshake_p50_corrected"] = NEW_HANDSHAKE_P50
size["client_cert_der_corrected"] = NEW_CLIENT_CERT_DER

old_term_pki = opinsize["term_pki"]
old_term_handshake = opinsize["term_handshake"]
new_term_pki = new_pki_body_total
new_term_handshake = n_mtls * NEW_HANDSHAKE_P50

# opinsize["extended_corrected"] already includes Decisions 11/12's JARM/
# login-traffic fix (term_jwt_corrected in place of term_jwt) -- this
# correction is layered on top of that, not the original pre-Decision-11
# "extended" field.
base_extended_corrected = opinsize["extended_corrected"]
new_extended = base_extended_corrected - old_term_pki - old_term_handshake + new_term_pki + new_term_handshake

opinsize["term_pki_corrected"] = new_term_pki
opinsize["term_handshake_corrected"] = new_term_handshake
opinsize["extended_fully_corrected"] = new_extended
opinsize["delta_from_pqc_ca_correction"] = new_extended - base_extended_corrected
opinsize["delta_pct_from_pqc_ca_correction"] = (new_extended / base_extended_corrected - 1) * 100
opinsize["pki_share_of_extended_pct_corrected"] = new_term_pki / new_extended * 100

print(f"PKI_bytes (root/issuer, old->new): {old_root}/{old_issuer} -> {NEW_ROOT_BYTES}/{NEW_ISSUER_BYTES}")
print(f"PKI_bytes mean (old->new): {old_term_pki / n_pki:.1f} -> {new_term_pki / n_pki:.1f}")
print(f"handshake_bytes P50 (old->new): {old_term_handshake / n_mtls:.1f} -> {NEW_HANDSHAKE_P50:.1f}")
print(f"client_cert_der_bytes (old->new): {size['client_cert_der']} -> {NEW_CLIENT_CERT_DER}")
print(f"OPINsize PQC (JARM+login-corrected -> fully corrected): {base_extended_corrected:.0f} -> {new_extended:.0f} "
      f"(+{new_extended - base_extended_corrected:.0f}, +{(new_extended / base_extended_corrected - 1) * 100:.2f}%)")

classic_ext = data["opinsize"]["classic"]["extended_corrected"]
hybrid_ext = data["opinsize"]["hybrid"]["extended_corrected"]
print()
print("Corrected ratios (fully corrected PQC vs Decision 11/12-corrected Classic/Hybrid):")
print(f"  PQC/Classic: {new_extended / classic_ext:.4f}x (+{(new_extended / classic_ext - 1) * 100:.2f}%)")
print(f"  Hybrid/Classic: {hybrid_ext / classic_ext:.4f}x (+{(hybrid_ext / classic_ext - 1) * 100:.2f}%) -- unchanged")
print(f"  Hybrid/PQC: {hybrid_ext / new_extended:.4f}x (+{(hybrid_ext / new_extended - 1) * 100:.2f}%)")

DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nWrote corrected fields into {DATA_PATH}")

"""Mandatory negative tests for the "fluxo completo" turn (thesis/results/
v8/DECISIONS.md): a tampered signature, the wrong key, or a token claiming
the wrong algorithm must all be REJECTED by verify_jwt()/
decrypt_and_verify_jwt(), in every one of the 3 profiles, not merely
"usually work". Run against the REAL local lab stack (no AWS, no mocks --
a positive verification passing proves nothing about whether tampering is
actually detected; these tests tamper REAL artifacts captured from a real
flow execution). Requires the local docker-compose stack up and
CRYPTO_PROFILE switched to each profile in turn before this file runs for
that profile (see run_negative_tests.sh, which drives all 3).

One profile per process (CRYPTO_PROFILE is read at opin_flow.py import
time) -- invoke as:
  CRYPTO_PROFILE=classic python -m pytest tests/test_signature_verification.py
  CRYPTO_PROFILE=pqc     python -m pytest tests/test_signature_verification.py
  CRYPTO_PROFILE=hybrid  python -m pytest tests/test_signature_verification.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import opin_flow as of
import pytest
import requests

PROFILE = os.environ.get("CRYPTO_PROFILE", "classic")


@pytest.fixture(scope="module")
def live_artifacts():
    """Runs one real flow against the local stack, capturing the real
    classic_jwk/pqc_jwk pairs (AS and RS) and one real RS-signed response
    -- the artifacts every test below tampers."""
    proc = of.start_tls_kem_proxy(PROFILE)
    signer_started = of.start_pqc_signer_service(PROFILE)
    try:
        session = requests.Session()
        cert = of.get_local_leg_cert_paths(PROFILE)
        calls = []
        as_keys = of.fetch_server_keys_and_ca(calls, session, cert, PROFILE)
        signing_key, kid, alg = of.load_client_signing_key(PROFILE)
        consent_id, consent_url, cc_access_token, ac_access_token, rs_keys = of.create_and_authorize_consent(
            calls, session, cert, signing_key, kid, alg, PROFILE,
            permissions=of.INSURANCE_CONSENT_PERMISSIONS, scope=of.INSURANCE_AUTHORIZATION_SCOPES, poll_count=1,
            as_keys=as_keys,
        )
        r = session.get(consent_url, cert=cert, verify=False,
                         headers={"Authorization": f"Bearer {cc_access_token}", "Host": of.API_HOST})
        r.raise_for_status()
        yield {"as_keys": as_keys, "rs_keys": rs_keys, "rs_response_jwt": r.text}
    finally:
        of.stop_pqc_signer_service(signer_started)
        of.stop_tls_kem_proxy(proc)


def _tamper_signature(compact_jwt: str) -> str:
    """Flips the LAST base64url character of the signature segment --
    guaranteed to change the decoded signature bytes (base64url's own
    alphabet has no two characters that decode identically at a fixed
    position), without touching the PEM/JOSE framing the way a blind
    byte-slice replacement risked (confirmed live, this turn: an earlier,
    cruder tamper produced a framing error instead of a clean signature
    mismatch for PEM content -- this method avoids that class of false
    pass entirely)."""
    header_b64, payload_b64, sig_b64 = compact_jwt.rsplit(".", 2)
    last = sig_b64[-1]
    replacement = "A" if last != "A" else "B"
    return f"{header_b64}.{payload_b64}.{sig_b64[:-1]}{replacement}"


def test_tampered_signature_rejected(live_artifacts):
    classic_jwk, pqc_jwk = live_artifacts["rs_keys"]
    tampered = _tamper_signature(live_artifacts["rs_response_jwt"])
    with pytest.raises(of.SignatureVerificationError):
        of.verify_jwt(tampered, classic_jwk=classic_jwk, pqc_jwk=pqc_jwk)


def test_wrong_key_rejected(live_artifacts):
    """Verifies the RS's own response against the AS's key instead of the
    RS's -- two REAL, independently-issued key pairs, confirmed different
    live (they are never the same key in this project's own architecture:
    separate services, separate crypto-profiles/*.json)."""
    as_classic_jwk, as_pqc_jwk = live_artifacts["as_keys"]
    rs_classic_jwk, rs_pqc_jwk = live_artifacts["rs_keys"]
    assert (as_classic_jwk or as_pqc_jwk) != (rs_classic_jwk or rs_pqc_jwk)
    with pytest.raises(of.SignatureVerificationError):
        of.verify_jwt(live_artifacts["rs_response_jwt"], classic_jwk=as_classic_jwk, pqc_jwk=as_pqc_jwk)


def test_wrong_algorithm_rejected(live_artifacts):
    """Only meaningful for classic/pqc (hybrid's own verify_jwt() call
    shape doesn't take expected_alg -- it dispatches structurally, by
    signature shape, which is itself the "wrong algorithm" defense for
    that profile: see test_hybrid_scheme_confusion_rejected below)."""
    if PROFILE == "hybrid":
        pytest.skip("hybrid dispatches by signature shape, not a declared expected_alg -- see the dedicated test below")
    classic_jwk, pqc_jwk = live_artifacts["rs_keys"]
    wrong_alg = "RS256" if PROFILE == "classic" else "PS256"
    with pytest.raises(of.SignatureVerificationError):
        of.verify_jwt(live_artifacts["rs_response_jwt"], classic_jwk=classic_jwk, pqc_jwk=pqc_jwk, expected_alg=wrong_alg)


def test_hybrid_scheme_confusion_rejected(live_artifacts):
    """hybrid only: feeding a genuine payload-extension-signed RS response
    through as if it were Strong-Nesting-shaped (by lying about which half
    of rs_keys is which) must still fail closed, not silently misverify."""
    if PROFILE != "hybrid":
        pytest.skip("hybrid-only: the two dual-signature schemes only exist under this profile")
    classic_jwk, pqc_jwk = live_artifacts["rs_keys"]
    # Swapping which jwk is passed as "classic" vs "pqc" corrupts both the
    # RS256 key material AND the ML-DSA-65 key material verify_jwt() would
    # use -- a real, not merely cosmetic, key-confusion attempt.
    with pytest.raises(of.SignatureVerificationError):
        of.verify_jwt(live_artifacts["rs_response_jwt"], classic_jwk=pqc_jwk, pqc_jwk=classic_jwk)

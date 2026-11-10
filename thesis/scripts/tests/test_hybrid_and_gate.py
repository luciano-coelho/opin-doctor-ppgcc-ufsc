"""Negative/positive tests for the AS's hybrid AND-gate client auth
(mock-service-os/mock_as/utils/opin/clientHybridAuth.js) -- Decisao 115
(thesis/results/v9/DECISIONS.md): the AS's /token endpoint must reject a
client_assertion whose payload-extension pqc claim is either
present-but-invalid OR absent entirely, and must accept one whose pqc
claim verifies. Runs against the REAL local stack, CRYPTO_PROFILE=hybrid
-- the same backend config serves both Hibrido dual=false (control) and
Hibrido dual=true (AND); clientHybridAuth.js has no signal to tell them
apart and Decisao 115 deliberately didn't add one, so this one test run
covers both profiles' application-layer behavior identically. The
distinct TLS-layer behavior between the two profiles is covered
elsewhere (toolchain/patches/and.patch's own tests), never by this file.

Invoke as:
  CRYPTO_PROFILE=hybrid python -m pytest tests/test_hybrid_and_gate.py
"""
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import opin_flow as of
import pytest
import requests

PROFILE = os.environ.get("CRYPTO_PROFILE", "classic")


@pytest.fixture(scope="module")
def stack():
    if PROFILE not in ("hybrid", "hibrido-and"):
        pytest.skip("the payload-extension AND-gate only exists in the two hybrid profiles -- "
                     "classic/pqc never load clientHybridAuth.js (express.js's isHybridProfile gate)")
    proc = of.start_tls_kem_proxy(PROFILE)
    signer_started = of.start_pqc_signer_service(PROFILE)
    try:
        session = requests.Session()
        cert = of.get_local_leg_cert_paths(PROFILE)
        signing_key, kid, alg = of.load_client_signing_key(PROFILE)
        yield session, cert, signing_key, kid, alg
    finally:
        of.stop_pqc_signer_service(signer_started)
        of.stop_tls_kem_proxy(proc)


@pytest.fixture(scope="module")
def any_profile_stack():
    """Same as `stack`, minus the hybrid-only skip -- used only by
    test_classic_and_pqc_unaffected, which needs to run precisely for the
    two profiles `stack` skips."""
    proc = of.start_tls_kem_proxy(PROFILE)
    signer_started = of.start_pqc_signer_service(PROFILE)
    try:
        session = requests.Session()
        cert = of.get_local_leg_cert_paths(PROFILE)
        signing_key, kid, alg = of.load_client_signing_key(PROFILE)
        yield session, cert, signing_key, kid, alg
    finally:
        of.stop_pqc_signer_service(signer_started)
        of.stop_tls_kem_proxy(proc)


def _token_request(session, cert, assertion: str):
    body = {
        "grant_type": "client_credentials",
        "scope": "consents",
        "client_assertion": assertion,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
    }
    _, resp = of.do_call(
        session, "POST", f"{of.GATEWAY_SCHEME}://{of.AUTH_CONNECT_HOST}/token", cert=cert,
        host_header=of.AUTH_MTLS_HOST_HEADER, headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=body, src="test_hybrid_and_gate",
    )
    return resp


def test_pqc_absent_rejected(stack):
    """A classical-only PS256 assertion with no `pqc` claim at all must now
    be rejected. This is the exact case Decisao 13's own original text
    already named as a downgrade risk ("invalido ou ausente"), but the
    code only ever implemented the "invalido" half until Decisao 115."""
    session, cert, signing_key, kid, _alg = stack
    classic_key, _pqc_jwk = signing_key
    assertion = of.make_client_assertion(
        classic_key, kid, "PS256", audience=f"https://{of.AUTH_MTLS_HOST_HEADER}/token",
        artifact="test:pqc_absent",
    )
    payload = json.loads(of._b64url_decode(assertion.split(".")[1]))
    assert "pqc" not in payload, "sanity check: this assertion must genuinely have no pqc claim"

    resp = _token_request(session, cert, assertion)
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}: {resp.text}"
    assert "hybrid AND-gate failed" in resp.json().get("error_description", "")


def test_pqc_invalid_rejected(stack):
    """A present-but-corrupted pqc signature must still be rejected -- the
    behavior Decisao 13's original implementation already covered;
    confirmed unchanged by Decisao 115's fix to the absent case."""
    session, cert, signing_key, kid, alg = stack
    classic_key, pqc_jwk = signing_key
    assertion = of.make_client_assertion(signing_key, kid, alg, audience=f"https://{of.AUTH_MTLS_HOST_HEADER}/token",
                                          artifact="test:pqc_invalid")
    header_b64, payload_b64, _old_sig_b64 = assertion.split(".")
    payload = json.loads(of._b64url_decode(payload_b64))
    pqc_sig = bytearray(of._b64url_decode(payload["pqc"]["signature"]))
    pqc_sig[-1] ^= 0xFF
    payload["pqc"]["signature"] = of._b64url_encode(bytes(pqc_sig))

    # Re-sign the classical half over the tampered payload so PS256 itself
    # still verifies -- otherwise oidc-provider's own native check would
    # reject it first, for the wrong reason, before clientHybridAuth.js
    # ever inspects the pqc claim at all.
    retampered = of.pyjwt.encode(payload, classic_key, algorithm="PS256", headers={"kid": kid, "alg": "PS256"})

    resp = _token_request(session, cert, retampered)
    assert resp.status_code == 400, f"expected 400, got {resp.status_code}: {resp.text}"
    assert "hybrid AND-gate failed" in resp.json().get("error_description", "")


def test_pqc_valid_accepted(stack):
    """A genuine hybrid assertion (valid PS256 + valid pqc/ML-DSA-65) must
    still be accepted -- confirms this round didn't turn the AND-gate into
    an always-reject gate."""
    session, cert, signing_key, kid, alg = stack
    assertion = of.make_client_assertion(signing_key, kid, alg, audience=f"https://{of.AUTH_MTLS_HOST_HEADER}/token",
                                          artifact="test:pqc_valid")
    resp = _token_request(session, cert, assertion)
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    assert "access_token" in resp.json()


def test_classic_and_pqc_unaffected(any_profile_stack):
    """Decisao 115 touches only clientHybridAuth.js, which classic/pqc
    never load -- confirms LIVE, not just by reading express.js's
    isHybridProfile gate, that an ordinary client_credentials token
    request still succeeds unchanged in both profiles."""
    if PROFILE == "hybrid":
        pytest.skip("covered by test_pqc_valid_accepted above")
    session, cert, signing_key, kid, alg = any_profile_stack
    assertion = of.make_client_assertion(signing_key, kid, alg, audience=f"https://{of.AUTH_MTLS_HOST_HEADER}/token",
                                          artifact="test:classic_pqc_unaffected")
    resp = _token_request(session, cert, assertion)
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}: {resp.text}"
    assert "access_token" in resp.json()

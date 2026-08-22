"""
Strong Nesting hybrid signature verification (PS256 + ML-DSA-65), per
thesis/results/v4/Arquitetura_Tecnica_Experimento3_Strong_Nesting.docx.

A pure, standalone function -- NOT wired into opin_flow.py's flow control.
opin_flow.py does not cryptographically verify any profile's signatures
today (classic or pqc included; parse_rs_body() always calls
pyjwt.decode(..., verify_signature=False)), so there is no existing
verification point in the flow to extend for hybrid. This module exists so
the verification logic is implemented and tested (Etapa 4) independently
of when/whether it gets wired into the main flow (a natural fit for Etapa
7, when opin_flow.py itself becomes hybrid-aware). Mirrors
mock-service-os/mock_as/utils/opin/hybridVerification.js exactly -- same
byte convention (raw concatenation, not base64), same 256-byte split
point for sigma1.
"""
import base64
import json
import subprocess

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

PQC_SIGNER_IMAGE = "mockopin-pqc-signer"
CLASSIC_SIG_BYTES = 256  # RSA-2048 PS256 signature length, fixed.


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def verify_hybrid(compact_jwt: str, classic_public_jwk: dict, pqc_public_jwk: dict) -> tuple[bool, str]:
    """
    Decomposes the compact JWS's signature into sigma1 (first 256 bytes,
    PS256/RSA-2048) and sigma2 (the remainder, ML-DSA-65), verifies sigma1
    against the header.payload signing input with classic_public_jwk,
    reconstructs signing_input + sigma1, verifies sigma2 against that
    reconstruction with pqc_public_jwk, and AND-gates the result: valid
    only if both verifications pass.

    classic_public_jwk: {"kty": "RSA", "n": ..., "e": ...} (base64url).
    pqc_public_jwk: {"kty": "AKP", "alg": "ML-DSA-65", "pub": ...} (base64url).

    The ML-DSA-65 half is verified out-of-process (mockopin-pqc-signer,
    the same Docker helper used for signing in pqc mode) since Python has
    no native ML-DSA support. This is a raw-bytes verify, not a JWS
    verify: jose's CompactVerify would recompute its own signing input
    from a header/payload it parses, which has no way to check a
    signature over an arbitrary byte string like signing_input+sigma1 --
    the same reason hybridSigning.js had to move off jose's CompactSign
    for the signing side (see DECISIONS.md).
    """
    parts = compact_jwt.split(".")
    if len(parts) != 3:
        return False, "not a 3-segment compact JWS"
    header_b64, payload_b64, sig_b64 = parts
    message = f"{header_b64}.{payload_b64}".encode("ascii")

    try:
        combined = _b64url_decode(sig_b64)
    except Exception:
        return False, "signature segment is not valid base64url"
    if len(combined) <= CLASSIC_SIG_BYTES:
        return False, f"combined signature too short ({len(combined)} bytes)"
    sigma1 = combined[:CLASSIC_SIG_BYTES]
    sigma2 = combined[CLASSIC_SIG_BYTES:]

    classic_key = rsa.RSAPublicNumbers(
        e=int.from_bytes(_b64url_decode(classic_public_jwk["e"]), "big"),
        n=int.from_bytes(_b64url_decode(classic_public_jwk["n"]), "big"),
    ).public_key()
    try:
        classic_key.verify(
            sigma1, message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
            hashes.SHA256(),
        )
    except InvalidSignature:
        return False, "sigma1 (PS256) verification failed"

    message_plus_sigma1 = message + sigma1
    verify_input = json.dumps({
        "jwk": pqc_public_jwk,
        "message_b64": base64.b64encode(message_plus_sigma1).decode("ascii"),
        "signature_b64": base64.b64encode(sigma2).decode("ascii"),
    })
    result = subprocess.run(
        ["docker", "run", "--rm", "-i", PQC_SIGNER_IMAGE],
        input=verify_input, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return False, f"pqc-signer verify call failed: {result.stderr}"
    if result.stdout.strip() != "true":
        return False, "sigma2 (ML-DSA-65) verification failed"

    return True, "both sigma1 and sigma2 verified"

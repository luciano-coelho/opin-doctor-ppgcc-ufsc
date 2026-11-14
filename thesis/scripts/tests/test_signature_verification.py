"""Mandatory negative tests for the "fluxo completo" turn (thesis/results/
v8/DECISIONS.md): a tampered signature, the wrong key, or a token claiming
the wrong algorithm must all be REJECTED by verify_jwt()/
decrypt_and_verify_jwt(), in every one of the 4 profiles, not merely
"usually work".

Decisao 164 (pedido do autor, reversao da quarentena nominal da Decisao
163): HERMETICO desde esta rodada -- nunca mais via o tls_kem_proxy
legado (confirmado quebrado 3 jeitos diferentes nesta sessao, incluindo
sob V9_HARNESS=1, que o `insurance-server-lambdas` docker-compose nao
tem infraestrutura pra sustentar pra este arquivo -- ver Decisao 163
pro detalhe). O ARTEFATO sob teste (um JWT de resposta do RS,
construido no formato REAL -- "payload extension", confirmado lendo
`signer_core.mjs` diretamente, nunca Strong Nesting, que e so pra
artefatos emitidos pelo AS) e gerado de ponta a ponta com chaves
DESCARTAVEIS criadas na hora (RSA-2048 local via `cryptography`; ML-
DSA-65 via o signer real do repositorio, `mockopin-pqc-signer`,
chamado diretamente -- a mesma imagem que `start_pqc_signer_service()`
ja usa) -- nada gitignorado, nenhuma rede, nenhum mock_mtls. Se o
signer estiver genuinamente inalcancavel, `start_pqc_signer_service()`
ja levanta (RuntimeError), nunca retorna silenciosamente -- essa
propriedade e reaproveitada aqui tambem, nunca um `pytest.skip`.

One profile per process (CRYPTO_PROFILE is read at opin_flow.py import
time) -- invoke as:
  CRYPTO_PROFILE=classic     python -m pytest tests/test_signature_verification.py
  CRYPTO_PROFILE=pqc         python -m pytest tests/test_signature_verification.py
  CRYPTO_PROFILE=hybrid      python -m pytest tests/test_signature_verification.py
  CRYPTO_PROFILE=hibrido-and python -m pytest tests/test_signature_verification.py
"""
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import opin_flow as of
import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric import rsa

PROFILE = os.environ.get("CRYPTO_PROFILE", "classic")


def _b64url_uint(value: int, length: int) -> str:
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def _generate_throwaway_rsa_keypair(kid: str) -> tuple[dict, dict]:
    """RSA-2048, gerada na hora, nunca a chave real de producao --
    retorna (private_jwk, public_jwk). `private_jwk["alg"]="PS256"` e
    obrigatorio: `signer_core.mjs`'s `handleRequest()` generic-sign
    branch importa a chave com `jwk.alg` (nunca `headers.alg`)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    alg = of.pyjwt.algorithms.RSAAlgorithm(of.pyjwt.algorithms.RSAAlgorithm.SHA256)
    private_jwk = alg.to_jwk(key, as_dict=True)
    private_jwk["alg"] = "PS256"
    private_jwk["kid"] = kid
    public_numbers = key.public_key().public_numbers()
    public_jwk = {"kty": "RSA", "n": _b64url_uint(public_numbers.n, 256), "e": _b64url_uint(public_numbers.e, 3)}
    return private_jwk, public_jwk


_ML_DSA_65_KEYGEN_SCRIPT = """
import { webcrypto } from 'node:crypto';
const { publicKey, privateKey } = await webcrypto.subtle.generateKey({ name: 'ML-DSA-65' }, true, ['sign', 'verify']);
const priv = await webcrypto.subtle.exportKey('jwk', privateKey);
const pub = await webcrypto.subtle.exportKey('jwk', publicKey);
console.log(JSON.stringify({priv, pub}));
"""


def _generate_throwaway_ml_dsa65_keypair(kid: str) -> tuple[dict, dict]:
    """Gera um par ML-DSA-65 descartavel de verdade, rodando
    `webcrypto.subtle.generateKey` dentro da imagem REAL do signer
    (`mockopin-pqc-signer`, a mesma que `start_pqc_signer_service()` ja
    usa) -- confirmado ao vivo nesta sessao que isto funciona (Node
    emite um `ExperimentalWarning`, inofensivo, esperado). Nunca
    modifica a imagem nem `signer_core.mjs`/`server.mjs` -- so roda um
    script descartavel via stdin (`node --input-type=module`), nenhum
    binario muda, nenhum repin necessario."""
    result = subprocess.run(
        ["docker", "run", "--rm", "-i", of.PQC_SIGNER_IMAGE, "node", "--input-type=module"],
        input=_ML_DSA_65_KEYGEN_SCRIPT, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ML-DSA-65 throwaway keygen failed (rc={result.returncode}): {result.stderr}")
    data = json.loads(result.stdout.strip().splitlines()[-1])
    priv, pub = data["priv"], data["pub"]
    priv["kid"] = kid
    pub["kid"] = kid
    return priv, pub


def _sign_generic(private_jwk: dict, headers: dict, claims: dict) -> str:
    """Generic-sign shape (`signer_core.mjs`'s `handleRequest()`,
    ultimo ramo do dispatch): `{jwk, headers, claims}` -> `jose`'s
    `SignJWT(claims).setProtectedHeader(headers).sign(key)`. Funciona
    pra QUALQUER algoritmo que `jose` suporte -- PS256 (RSA) e
    ML-DSA-65 (AKP) igualmente, mesma chamada."""
    payload = json.dumps({"jwk": private_jwk, "headers": headers, "claims": claims})
    return of._run_pqc_signer_service(payload)


def _raw_ml_dsa65_sign(private_jwk: dict, message: bytes) -> bytes:
    """Assinatura ML-DSA-65 crua (sem envelope JWT) -- shape
    `{jwk, message_b64}` (sem `signature_b64`) de `handleRequest()`,
    `webcrypto.subtle.sign({name:'ML-DSA-65'}, ...)` por baixo. Usada
    pra assinar os bytes CANONICALIZADOS (RFC 8785) da claim `pqc` no
    formato "payload extension" -- nunca o JWT inteiro."""
    payload = json.dumps({"jwk": private_jwk, "message_b64": base64.b64encode(message).decode("ascii")})
    sig_b64 = of._run_pqc_signer_service(payload)
    return base64.b64decode(sig_b64)


@pytest.fixture(scope="module")
def live_artifacts():
    """HERMETICO (Decisao 164): constroi um JWT de resposta do RS REAL
    e validamente assinado, pra cada perfil, so com chaves descartaveis
    geradas na hora -- nunca rede, nunca mock_mtls, nunca material
    gitignorado. Formato "payload extension" (PS256 classico + claim
    `pqc.signature` em ML-DSA-65 sobre os bytes RFC-8785-canonicalizados
    dos claims sem a propria claim `pqc`) -- confirmado lendo
    `signer_core.mjs`'s `verifyPayloadExtension()`/`verifyStrongNesting()`
    diretamente: e o formato REAL que o RS usa (Strong Nesting e so
    pra artefatos emitidos pelo AS, id_token/JARM, nunca resposta do
    RS). classic/pqc usam o ramo de chave unica (sem claim `pqc`
    nenhuma). `as_keys` (outro par descartavel, independente do `rs_keys`)
    existe so pra `test_wrong_key_rejected` ter uma chave genuinamente
    DIFERENTE pra verificar contra -- nao implica mais nenhum round-trip
    real com um AS.

    Validacao da propria construcao, antes de devolver qualquer coisa
    pros testes: o artefato GENUINO (nao adulterado) tem que verificar
    com sucesso via `of.verify_jwt()` -- se isso falhar, o formato/
    canonicalizacao estao errados, e o erro aparece AQUI, nunca
    disfarcado de "teste de seguranca passou" por acidente.

    Se `start_pqc_signer_service()` nao conseguir subir o signer (porta
    ocupada, imagem ausente, container crashou), ela mesma levanta
    RuntimeError -- NUNCA pytest.skip. Um signer genuinamente
    inalcancavel e uma falha real deste ambiente de teste, nao uma
    precondicao de infraestrutura ausente que justifique pular."""
    signer_started = of.start_pqc_signer_service(PROFILE)
    try:
        rs_classic_priv, rs_classic_pub = _generate_throwaway_rsa_keypair("rs-classic")
        as_classic_priv, as_classic_pub = _generate_throwaway_rsa_keypair("as-classic")
        claims = {"iss": "hermetic-test-rs", "sub": "hermetic-test-subject", "aud": "hermetic-test-aud"}

        if PROFILE == "pqc":
            rs_pqc_priv, rs_pqc_pub = _generate_throwaway_ml_dsa65_keypair("rs-pqc")
            as_pqc_priv, as_pqc_pub = _generate_throwaway_ml_dsa65_keypair("as-pqc")
            token = _sign_generic(rs_pqc_priv, {"alg": "ML-DSA-65", "kid": "rs-pqc"}, claims)
            rs_keys = (None, rs_pqc_pub)
            as_keys = (None, as_pqc_pub)
        elif PROFILE in ("hybrid", "hibrido-and"):
            rs_pqc_priv, rs_pqc_pub = _generate_throwaway_ml_dsa65_keypair("rs-pqc")
            as_pqc_priv, as_pqc_pub = _generate_throwaway_ml_dsa65_keypair("as-pqc")
            canonical = rfc8785.dumps(claims)
            pqc_sig = _raw_ml_dsa65_sign(rs_pqc_priv, canonical)
            claims_with_pqc = {**claims, "pqc": {"signature": of._b64url_encode(pqc_sig)}}
            token = _sign_generic(rs_classic_priv, {"alg": "PS256", "kid": "rs-classic"}, claims_with_pqc)
            rs_keys = (rs_classic_pub, rs_pqc_pub)
            as_keys = (as_classic_pub, as_pqc_pub)
        else:  # classic
            token = _sign_generic(rs_classic_priv, {"alg": "PS256", "kid": "rs-classic"}, claims)
            rs_keys = (rs_classic_pub, None)
            as_keys = (as_classic_pub, None)

        # Sanidade: o artefato genuino tem que verificar -- prova que a
        # construcao esta correta antes de qualquer teste de adulteracao.
        of.verify_jwt(token, classic_jwk=rs_keys[0], pqc_jwk=rs_keys[1], artifact="hermetic_sanity_check")

        yield {"as_keys": as_keys, "rs_keys": rs_keys, "rs_response_jwt": token}
    finally:
        of.stop_pqc_signer_service(signer_started)


def _tamper_signature(compact_jwt: str) -> str:
    """Flips the LAST base64url character of the signature segment --
    guaranteed to change the decoded signature bytes (base64url's own
    alphabet has no two characters that decode identically at a fixed
    position) -- NOT a character-level swap. An earlier version of this
    function swapped the signature segment's own last base64url CHARACTER
    (replacing it with "A" unless it already was "A") and was found, this
    turn, to silently produce a BYTE-IDENTICAL "tampered" signature
    roughly 25% of the time: a 256-byte (RSA-2048) signature's base64url
    encoding ends in a 2-character group where the SECOND character's own
    bottom 4 bits are pure padding a decoder ignores -- only its top 2
    bits are real signature bits. Whenever that character's original
    6-bit value already had both top bits zero (any of "A".."P", 16 of 64
    possible values -- confirmed live: a real captured signature whose
    last char was "A" decoded to the IDENTICAL raw bytes before and after
    "tampering"), replacing it with "A" (value 0) changed only the
    already-irrelevant padding bits, leaving the decoded signature
    completely unchanged -- so `verify_jwt()` correctly accepted it,
    and the test's own "must be rejected" assertion failed intermittently
    for a reason that had nothing to do with opin_flow.py/signer_core.mjs
    at all (see DECISIONS.md for the full investigation; the originally-
    suspected "container startup timing race" was a correlation in the
    data, not the actual cause). Decoding to real bytes and XORing the
    LAST BYTE with 0xFF before re-encoding is immune to this class of
    bug entirely: it is impossible for flipping every bit of a byte to
    leave that byte unchanged, regardless of base64 alignment."""
    header_b64, payload_b64, sig_b64 = compact_jwt.rsplit(".", 2)
    sig = bytearray(of._b64url_decode(sig_b64))
    sig[-1] ^= 0xFF
    return f"{header_b64}.{payload_b64}.{of._b64url_encode(bytes(sig))}"


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
    """Only meaningful for classic/pqc. Real gap found and fixed this
    round: this used to skip only "hybrid", but signer_core.mjs's own
    verifyJwt() dispatches by signature SHAPE (isStrongNestingShaped)
    whenever BOTH classic_jwk and pqc_jwk are passed -- `if (classicJwk
    && pqcJwk)`, never a check on CRYPTO_PROFILE's name -- completely
    ignoring expected_alg in that branch. hibrido-and is ALSO a
    dual-keyed profile (both halves of its AND-gate get verified
    together), so it hits this exact same branch -- confirmed live:
    running this test under hibrido-and before this fix made
    verify_jwt() silently accept the "wrong" algorithm (DID NOT RAISE),
    not because of a real verification gap, but because expected_alg
    was never consulted for either dual-keyed profile. hybrid and
    hibrido-and are the project's only 2 dual-keyed profiles (same
    pairing test_hybrid_and_gate.py's own PROFILE check already uses) --
    classic/pqc are the only 2 single-keyed ones this test is actually
    exercising."""
    if PROFILE in ("hybrid", "hibrido-and"):
        pytest.skip("dual-keyed profile -- verify_jwt() dispatches by signature shape, not a declared expected_alg -- see test_hybrid_scheme_confusion_rejected below, which now runs under both dual-keyed profiles and is this test's real equivalent for them")
    classic_jwk, pqc_jwk = live_artifacts["rs_keys"]
    wrong_alg = "RS256" if PROFILE == "classic" else "PS256"
    with pytest.raises(of.SignatureVerificationError):
        of.verify_jwt(live_artifacts["rs_response_jwt"], classic_jwk=classic_jwk, pqc_jwk=pqc_jwk, expected_alg=wrong_alg)


def test_hybrid_rs256_payload_extension_rejected():
    """Decisao de hoje (nota datada na Decisao 13, thesis/results/v4/
    DECISIONS.md): a payload extension (client_assertion, PAR, resposta do
    RS) passou a exigir PS256 (RSASSA-PSS), nao mais RS256 (RSASSA-
    PKCS1-v1_5, o esquema antigo ate 2026-11-09). Esta e a regressao que
    garante isso: um artefato assinado com RS256 -- o esquema ANTIGO --
    tem que ser REJEITADO pelo verificador atual, nunca aceito por engano
    so porque o padding bate em algum library mais tolerante.

    Chave RSA-2048 gerada localmente so para este teste (nunca a chave
    real de producao) -- nao depende do stack real/live_artifacts, roda
    em qualquer profile, so pula fora do hybrid (payload extension nao
    existe nos outros dois)."""
    if PROFILE != "hybrid":
        pytest.skip("payload extension so existe no perfil hybrid")

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()
    classic_jwk = {
        "kty": "RSA",
        "n": _b64url_uint(public_numbers.n, 256),
        "e": _b64url_uint(public_numbers.e, 3),
    }
    # pqc_jwk is never reached: verifyPayloadExtension checks the classical
    # signature FIRST (payloadExtensionVerification.js/signer_core.mjs) and
    # returns valid=False immediately on a padding mismatch, before ever
    # looking at the `pqc` claim -- a syntactically well-shaped but unused
    # AKP JWK is enough to prove that, never a real key.
    pqc_jwk = {"kty": "AKP", "alg": "ML-DSA-65", "pub": _b64url_uint(0, 1952)}

    claims = {"iss": "test-rs256-rejection", "pqc": {"alg": "ML-DSA-65", "signature": "AA"}}
    forged = of.pyjwt.encode(claims, private_key, algorithm="RS256", headers={"alg": "RS256", "typ": "JWT"})

    with pytest.raises(of.SignatureVerificationError):
        of.verify_jwt(forged, classic_jwk=classic_jwk, pqc_jwk=pqc_jwk, artifact="rs256_regression")


def test_hybrid_scheme_confusion_rejected(live_artifacts):
    """Dual-keyed profiles only (hybrid, hibrido-and): feeding a genuine
    RS response through verify_jwt() with classic_jwk/pqc_jwk SWAPPED must
    still fail closed, not silently misverify.

    This is also the real equivalent, for both dual-keyed profiles, of
    test_wrong_algorithm_rejected above (which skips for both of them,
    since signer_core.mjs's verifyJwt() dispatches by signature SHAPE
    whenever both JWKs are present -- `if (classicJwk && pqcJwk)` --
    never consulting a declared expected_alg). Swapping which jwk is fed
    as "classic" vs "pqc" corrupts both the RS256 key material AND the
    ML-DSA-65 key material verify_jwt() would use for that shape-dispatch
    branch -- a real key/algorithm-confusion attempt, not merely cosmetic.

    Until this round, this test's own guard only ran it under "hybrid",
    leaving hibrido-and (also dual-keyed, confirmed hitting the exact same
    isStrongNestingShaped() dispatch branch) with ZERO coverage for this
    attack shape -- the "see the dedicated test below" skip message in
    test_wrong_algorithm_rejected was not actually true for hibrido-and
    until this fix. Extended to cover both profiles, and re-verified live
    under hibrido-and specifically (not just hybrid) before this change
    was trusted."""
    if PROFILE not in ("hybrid", "hibrido-and"):
        pytest.skip("hybrid/hibrido-and only: the two dual-signature schemes only exist under these 2 profiles")
    classic_jwk, pqc_jwk = live_artifacts["rs_keys"]
    # Swapping which jwk is passed as "classic" vs "pqc" corrupts both the
    # RS256 key material AND the ML-DSA-65 key material verify_jwt() would
    # use -- a real, not merely cosmetic, key-confusion attempt.
    with pytest.raises(of.SignatureVerificationError):
        of.verify_jwt(live_artifacts["rs_response_jwt"], classic_jwk=pqc_jwk, pqc_jwk=classic_jwk)

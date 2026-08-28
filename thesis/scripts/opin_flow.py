"""
Drives the OPIN consent flow directly against the AS and RS -- replacing the
Conformance Suite as the traffic generator for Experiments 1/2/3, since the
CS cannot act as an mTLS client with an ML-DSA-65 certificate at all (see
thesis/results/experiment2 - PQC/DECISIONS.md, Decision 7: a hardcoded RSA
assumption in its own compiled code, not something fixable from our side).

Runs BOTH real plans Experiment 1 measured for a scenario (see
baseline_automation.py's PLANS), back to back, combining their calls into
one metrics/report per scenario -- same as the original CS-driven runs did.
Each flow's exact call sequence was not designed from scratch: it's the real
sequence validated against the raw exported logs from Experiment 1's 0ms
scenario (thesis/results/experiment1 - Classic/0ms/).

Flow 1 -- run_insurance_flow(), opin-consent-api-status-test-v3 module
(Insurance consents api test V3.0.0 plan), validated against
consents_v3__opin-consent-api-status-test-v3_20260803T192725Z.json:

  1.  GET  /jwks                                          (AS server keys)
  2.  GET  https://crl.sandbox.pki.opinbrasil.com.br/root-ca.pem
  3.  GET  https://crl.sandbox.pki.opinbrasil.com.br/issuer-ca.pem
  4.  POST /token          grant_type=client_credentials   -> bearer token
  5.  POST /open-insurance/consents/v3/consents             -> 201, consentId
  6.  GET  /open-insurance/consents/v3/consents/{id}  x3    (AWAITING_AUTHORIZATION)
  7.  POST /request  (PAR, signed request object)           -> request_uri
  8.  -- automated login (see simulate_login()) --
  9.  POST /token          grant_type=authorization_code    -> new bearer token
  10. GET  /open-insurance/consents/v3/consents/{id}  x2    (AUTHORISED)

  Total: 12 HTTP calls (the step list above sums to 12; confirmed against
  a direct parse of the raw log's request entries, which also counted 12 --
  an earlier "13" here was a stale miscount, not a real discrepancy).

Flow 2 -- run_person_flow(), person_api_core_test-module_v2.0.0 module
(person_test-plan_v2.0.0 plan), validated against
person_v2__person_api_core_test-module_v2.0.0_20260803T192831Z.json. Steps
1-9 are the same shape as flow 1 (shared in create_and_authorize_consent),
with person-specific permissions/scope and only 1 status poll before login,
none after:

  1-9. jwks / PKI x2 / token(cc) / consent POST / consent GET x1 / PAR /
       automated login / token(ac)             -- 8 HTTP calls
  10.  GET  /open-insurance/insurance-person/v2/insurance-person       x2
  11.  GET  .../insurance-person/{policyId}/claim                     x2
  12.  GET  .../insurance-person/{policyId}/policy-info               x2
  13.  GET  .../insurance-person/{policyId}/premium                   x2

  Total: 16 HTTP calls (insurance-person is genuinely fetched twice in the
  real log, not once, despite reading like a single lookup).

Combined: 28 HTTP calls per scenario (verified against a live 0ms run's
baseline_metrics.json). This intentionally excludes the two
opin-consents_api_preflight_test-module_v3 modules (9 more calls in the raw
logs) -- see thesis/results/experiment2 - PQC/DECISIONS.md for why: they
depend on Raidiam's real Directory and always resulted in FAILED, so their
traffic isn't a real consent flow and isn't comparable across algorithms.

Deliberate simplifications from the CS's exact behaviour, disclosed here
rather than silently baked in:
  - response_type is "code" (authorization code only), not the CS's
    "code id_token" hybrid, combined with response_mode=jwt (JARM) --
    oidc-provider's fapi feature rejects plain "code" + the default query
    response_mode outright (confirmed empirically), and hybrid's fragment
    response isn't readable without browser JS. JARM keeps the callback
    purely server-side without changing which endpoints are called or how
    many times.
  - No SSA fetch in either flow above: confirmed by the raw logs that
    neither module calls .../softwarestatements/.../assertion -- client_one
    is a statically pre-registered client, not going through DCR. (The SSA
    fetch does appear in the excluded preflight modules, which this script
    doesn't replicate.)

CRYPTO_PROFILE (classic|pqc|hybrid) picks client_one's mTLS certificate,
mirroring the same switch already used by mock_as and the RS -- see
mock-service-os/mock_as/crypto-profiles/ and
insurance-server-lambdas/src/main/resources/crypto-profiles/. Under hybrid,
the mTLS transport identity is the real dual-signed certificate
(client_one_hybrid.crt, Etapa 6), and client assertions/the PAR request
object are Strong Nesting hybrid-signed too (Decision 9 in
thesis/results/v4/DECISIONS.md) -- see load_client_signing_key's and
sign_jwt()'s docstrings for the header-format asymmetry this direction
requires (client-to-AS artifacts use an ordinary `alg: "PS256"` header,
not the combined alg string the AS/RS's own outbound artifacts use).

Usage:
  CRYPTO_PROFILE=classic|pqc|hybrid EXPERIMENT_NUMBER=1|2|3 python opin_flow.py <latency_ms>
"""
import argparse
import base64
import hashlib
import ipaddress
import json
import os
import re
import secrets
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import jwt as pyjwt
import rfc8785
import requests
import urllib3
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# The system/Python-bundled OpenSSL on the machine this was developed on is
# 3.0.x, which predates ML-DSA support (added in OpenSSL 3.5) -- presenting
# client_one_pqc.crt/.key through Python's stdlib `ssl` module fails with
# "SSL: EE_KEY_TOO_SMALL" (confirmed empirically: it loads and uses the
# `cryptography` package's own bundled OpenSSL instead, which is newer,
# fine). `pyOpenSSL` + urllib3's pyopenssl contrib module route requests'
# TLS through that bundled OpenSSL instead of the stdlib one -- needed for
# any pqc-profile run, harmless for classic. See thesis/scripts/README.md
# for the venv this dependency is meant to be installed into (it is NOT
# assumed to be present in whatever `python` is on PATH globally).
try:
    import urllib3.contrib.pyopenssl

    urllib3.contrib.pyopenssl.inject_into_urllib3()
except ImportError:
    pass  # classic-only runs work fine without it; pqc runs will fail loudly at cert-load time if missing

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
# Reused as-is: none of these are Conformance-Suite-specific -- they operate
# on plain byte counts / URIs / the gateway's own docker logs. Only
# parse_calls() (which expects the CS's export JSON shape) and the
# API-orchestration functions (create_plan/start_module/poll_until_terminal)
# are NOT reused, since this script replaces exactly that part.
import baseline_automation as ba  # noqa: E402

THESIS_DIR = SCRIPTS_DIR.parent
BASE_DIR = THESIS_DIR.parent
CERTS_DIR = BASE_DIR / "mock-service-os" / "certs"

# Same container/logic as set_latency.sh, but called via `docker exec`
# directly instead of shelling out to that script -- which bash to run
# ("bash" on PATH resolving to Git Bash vs. WSL's bash.exe) turned out to be
# environment-dependent, and WSL's bash doesn't understand a Windows-style
# "C:/..." path the same way Git Bash's does ("No such file or directory"
# for a file that does exist, confirmed empirically). `docker exec` avoids
# the whole cross-shell path-translation question since it never touches a
# host filesystem path.
GATEWAY_CONTAINER = ba.GATEWAY_CONTAINER
ALLOWED_LATENCY_MS = (0, 14, 30, 140, 225, 320)

def client_cert_der_bytes(crypto_profile: str) -> int:
    """
    The exact wire size of the client certificate this run authenticates
    with -- passed to compute_metrics() so its gateway-side handshake
    stats aren't polluted by other clientCertBytes populations sharing the
    same gateway (the AS's own internal, always-classical calls to the RS;
    confirmed the naive fix of filtering by remoteIP doesn't work either,
    since Docker Desktop's NAT collapses every host-to-container connection
    onto the same source address regardless of which host process made it
    -- see compute_metrics()'s client_cert_bytes docstring in
    baseline_automation.py for the full story). Computed from the actual
    cert file rather than hardcoded so it can't drift if the certs are ever
    regenerated.
    """
    crt_path, _key_path = get_client_cert_paths(crypto_profile)
    cert = x509.load_pem_x509_certificate(Path(crt_path).read_bytes())
    return len(cert.public_bytes(encoding=serialization.Encoding.DER))

CLIENT_ID = "client_one"

# auth.local/api.local/directory are already in the host's hosts file
# (127.0.0.1); matls-auth.local is not, and adding it requires editing the
# system hosts file with admin rights -- avoided entirely by connecting to
# auth.local's already-resolvable IP and overriding the Host header instead.
# mock_mtls's router (mock-service-os/mock_mtls/main.go) registers
# "matls-auth.local/" and "auth.local/" on the exact same handler and Go's
# http.ServeMux matches on the request's Host header, not the DNS name the
# client actually resolved -- confirmed against main.go, not yet re-verified
# empirically against a live server at the time of writing (flagged in the
# handoff report).
AUTH_HOST = "auth.local"
AUTH_MTLS_HOST_HEADER = "matls-auth.local"
API_HOST = "api.local"

CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8765
# https, not http: client_one's response_types includes "code id_token"
# (implicit-capable), and oidc-provider enforces "redirect_uris for web
# clients using implicit flow MUST only register URLs using the https
# scheme" on ALL of a client's registered redirect_uris, not just the one
# actually used per-request -- confirmed empirically (a plain http loopback
# URI was rejected with exactly that error on the very first /token call).
REDIRECT_URI = f"https://{CALLBACK_HOST}:{CALLBACK_PORT}/callback"

INSURANCE_CONSENT_PERMISSIONS = [
    "CUSTOMERS_PERSONAL_ADDITIONALINFO_READ",
    "RESOURCES_READ",
    "CUSTOMERS_PERSONAL_QUALIFICATION_READ",
    "CUSTOMERS_PERSONAL_IDENTIFICATIONS_READ",
]
PERSON_CONSENT_PERMISSIONS = [
    "DAMAGES_AND_PEOPLE_PERSON_CLAIM_READ",
    "DAMAGES_AND_PEOPLE_PERSON_READ",
    "RESOURCES_READ",
    "DAMAGES_AND_PEOPLE_PERSON_POLICYINFO_READ",
    "DAMAGES_AND_PEOPLE_PERSON_PREMIUM_READ",
]
CONSENT_CPF = "76109277673"
CONSENT_CNPJ = "01773247000103"

# Mock account credentials (thesis/README.md) used to drive the login
# interaction automatically -- see wait_for_authorization_code() below.
LOGIN_USERNAME = "usuario1@seguradoramodelo.com.br"
LOGIN_PASSWORD = "P@ssword01"

# mock_as/views/interaction.ejs (the consent screen) renders one hidden
# <input name="{scope}-accounts" value="{resourceId}"> per selectable
# resource, pre-checked by default -- a real browser just clicking "Confirm"
# submits these as-is. Posting an empty confirm body skips that selection
# entirely, so the RS never links any resource to the consent
# (mock_as/utils/opin/routes.js's getAuthorizedConsentData reads them into
# linkedPersonPolicyIds etc.), which fails every person-flow resource call
# with "consent does not cover this person" -- confirmed empirically while
# validating this exact pattern in the scratch driver scripts used to
# collect Experiment 2's PKI/CRL data (see DECISIONS.md).
HIDDEN_ACCOUNTS_RE = re.compile(r'<input\s+type="hidden"\s+name="([\w-]+-accounts)"\s+value="([^"]*)"')

# Matches each plan's real PAR request scope exactly (validated against
# thesis/results/experiment1 - Classic/0ms's raw logs for both plans),
# minus openid/id_token-related nuance -- consent:{id} is appended at
# request time once the real consentId is known.
INSURANCE_AUTHORIZATION_SCOPES = (
    "openid consents resources customers "
    "insurance-acceptance-and-branches-abroad insurance-auto "
    "insurance-financial-risk insurance-patrimonial insurance-responsibility"
)
PERSON_AUTHORIZATION_SCOPES = "openid insurance-person"


def get_client_cert_paths(crypto_profile: str):
    if crypto_profile == "pqc":
        crt, key = CERTS_DIR / "client_one_pqc.crt", CERTS_DIR / "client_one_pqc.key"
    elif crypto_profile == "hybrid":
        # client_one_hybrid.crt/.key (Etapa 6): an ordinary RSA cert/key pair
        # as far as this script's TLS stack is concerned -- the ML-DSA-65
        # material rides along as three inert X.509 extensions the gateway's
        # own VerifyPeerCertificate AND-gates, but that's transparent here.
        # No urllib3/pyopenssl special-casing needed for this profile (that
        # workaround exists only for presenting a *native* ML-DSA-65 leaf
        # key, which this cert's own TLS-facing key never is).
        crt, key = CERTS_DIR / "client_one_hybrid.crt", CERTS_DIR / "client_one_hybrid.key"
    else:
        crt, key = CERTS_DIR / "client_one.crt", CERTS_DIR / "client_one.key"
    return str(crt), str(key)


PQC_SIGNER_IMAGE = "mockopin-pqc-signer"


def load_client_signing_key(crypto_profile: str):
    """
    Returns (signing_key, kid, alg). classic: signing_key is a pyjwt-usable
    RSA key object, alg "PS256" -- client_one's original key, unchanged.
    pqc: signing_key is the raw private AKP JWK dict itself (needed as-is
    by sign_jwt()'s docker signer, not something pyjwt can consume), alg
    "ML-DSA-65" -- see thesis/scripts/pqc-signer/ for why client-side
    ML-DSA-65 signing can't go through pyjwt/cryptography directly.

    hybrid (Decision 9 in thesis/results/v4/DECISIONS.md): signing_key is
    a (classic_key, pqc_jwk) tuple -- client_one.jwks's pyjwt-usable RSA
    key (unchanged from classic mode, used for sigma1) plus
    client_one_pqc.jwks's raw private AKP JWK (used for sigma2, via the
    pqc-signer docker helper, same as pqc mode). kid is the CLASSIC key's
    kid -- the header this ends up under always says `alg: "PS256"` with
    that same classic kid, since the AS can only ever verify what the
    client signs, never re-sign it on the client's behalf; sigma1 must
    therefore be a valid signature over the exact header the AS will see,
    which means that header has to already look like an ordinary
    classical one. See sign_jwt()'s "hybrid" branch and DECISIONS.md for
    the full reasoning. This was a deliberate scope limit through Etapa 7
    (client assertions/request objects stayed plain PS256, matching
    mock_as/utils/opin/configuration.js's clientAuthSigningAlgValues
    still being PS256-only) -- closed here once the AS gained its own
    inbound verification (utils/opin/clientHybridAuth.js).
    """
    if crypto_profile == "pqc":
        path = CERTS_DIR / "client_one_pqc.jwks"
        jwks = json.loads(path.read_text(encoding="utf-8"))
        jwk = next(k for k in jwks["keys"] if k.get("use") == "sig")
        return jwk, jwk["kid"], "ML-DSA-65"
    if crypto_profile == "hybrid":
        classic_jwks = json.loads((CERTS_DIR / "client_one.jwks").read_text(encoding="utf-8"))
        classic_jwk = next(k for k in classic_jwks["keys"] if k.get("use") == "sig")
        classic_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(classic_jwk))
        pqc_jwks = json.loads((CERTS_DIR / "client_one_pqc.jwks").read_text(encoding="utf-8"))
        pqc_jwk = next(k for k in pqc_jwks["keys"] if k.get("use") == "sig")
        return (classic_key, pqc_jwk), classic_jwk["kid"], "hybrid"
    path = CERTS_DIR / "client_one.jwks"
    jwks = json.loads(path.read_text(encoding="utf-8"))
    jwk = next(k for k in jwks["keys"] if k.get("use") == "sig")
    key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    return key, jwk["kid"], "PS256"


def sign_jwt(claims: dict, headers: dict, signing_key, alg: str) -> str:
    if alg == "PS256":
        return pyjwt.encode(claims, signing_key, algorithm="PS256", headers=headers)
    if alg == "ML-DSA-65":
        # signing_key is the raw private JWK here (see load_client_signing_key).
        payload = json.dumps({"jwk": signing_key, "headers": headers, "claims": claims})
        result = subprocess.run(
            ["docker", "run", "--rm", "-i", PQC_SIGNER_IMAGE],
            input=payload, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(f"pqc-signer failed: {result.stderr}")
        return result.stdout.strip()
    if alg == "hybrid":
        return _sign_jwt_hybrid(claims, headers, signing_key)
    raise ValueError(f"unsupported signing alg: {alg}")


def _sign_jwt_hybrid(claims: dict, headers: dict, signing_key) -> str:
    """
    Payload-extension client-side signing (Decision 13 in
    thesis/results/v4/DECISIONS.md) -- replaces Decision 9's Strong Nesting
    for client_assertion/the PAR request object. Full RFC 8785 rationale in
    DECISIONS.md; summary here:

    1. ML-DSA-65 signs RFC 8785 (JCS) canonical bytes of `claims` alone
       (no `pqc` field yet) -- via the pqc-signer docker helper's raw-sign
       mode, over the pqc_jwk half of signing_key.
    2. That signature is embedded as `claims["pqc"] = {"alg": "ML-DSA-65",
       "signature": base64url(...)}`.
    3. The classic_key half of signing_key signs the claims-with-pqc
       normally via pyjwt, alg RS256 (not PS256 -- a deliberate part of
       this scheme, chosen for maximal legacy-verifier compatibility, see
       DECISIONS.md), header alg "RS256" from the start.

    The result is an entirely ordinary RS256 JWT: no truncation is needed
    on the AS side (unlike Decision 9), since nothing about this token's
    shape is unusual to a standard verifier -- `pqc` is just an extra,
    ignorable claim. clientHybridAuth.js additionally verifies it and
    rejects the request if that verification fails, but no longer needs to
    rewrite the token before handing it to oidc-provider.
    """
    classic_key, pqc_jwk = signing_key
    canonical_claims = rfc8785.dumps(claims)

    sign_payload = json.dumps({
        "jwk": pqc_jwk,
        "message_b64": base64.b64encode(canonical_claims).decode("ascii"),
    })
    result = subprocess.run(
        ["docker", "run", "--rm", "-i", PQC_SIGNER_IMAGE],
        input=sign_payload, capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pqc-signer (payload-extension raw-sign) failed: {result.stderr}")
    pqc_sig_raw = base64.b64decode(result.stdout.strip())
    pqc_sig_b64url = base64.urlsafe_b64encode(pqc_sig_raw).rstrip(b"=").decode("ascii")

    claims_with_pqc = {**claims, "pqc": {"alg": "ML-DSA-65", "signature": pqc_sig_b64url}}
    rs256_headers = {**headers, "alg": "RS256"}
    return pyjwt.encode(claims_with_pqc, classic_key, algorithm="RS256", headers=rs256_headers)


def make_client_assertion(signing_key, kid, alg, audience: str) -> str:
    now = int(time.time())
    claims = {
        "sub": CLIENT_ID,
        "aud": audience,
        "iss": CLIENT_ID,
        "exp": now + 60,
        "iat": now,
        "jti": secrets.token_urlsafe(18),
    }
    return sign_jwt(claims, {"kid": kid, "alg": alg}, signing_key, alg)


def make_pkce_pair():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier, challenge


def make_request_object(signing_key, kid, alg, *, scope: str, state: str, nonce: str, code_challenge: str) -> str:
    now = int(time.time())
    claims = {
        "iss": CLIENT_ID,
        "client_id": CLIENT_ID,
        "aud": f"https://{AUTH_HOST}",
        "response_type": "code",
        # oidc-provider's fapi feature (profile "1.0 Final", see
        # mock_as/utils/opin/configuration.js) rejects plain "code" +
        # default query response_mode ("requested response_mode is not
        # allowed for this client or request", confirmed empirically) --
        # FAPI Advanced requires either the "code id_token" hybrid (fragment
        # response, needs JS to read since fragments never reach a server)
        # or JARM (response_mode=jwt, a signed "response" JWT delivered as
        # a normal query param instead). JARM keeps the callback purely
        # server-side, which is why it's used here over the hybrid.
        "response_mode": "jwt",
        "redirect_uri": REDIRECT_URI,
        "scope": scope,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "nbf": now,
        "exp": now + 300,
    }
    return sign_jwt(claims, {"kid": kid, "alg": alg}, signing_key, alg)


def _generate_callback_tls_cert():
    """
    Throwaway self-signed cert for the local callback listener (127.0.0.1),
    needed only because oidc-provider requires an https redirect_uri (see
    REDIRECT_URI above). Written to temp files each run -- ssl.SSLContext
    has no in-memory PEM-loading API, only load_cert_chain(path). The
    browser will show a security warning on first hit; that's expected and
    part of the manual-login protocol below (click through it once).
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=6))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(CALLBACK_HOST))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_file = tempfile.NamedTemporaryFile(suffix=".crt", delete=False)
    key_file = tempfile.NamedTemporaryFile(suffix=".key", delete=False)
    cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    cert_file.close()
    key_file.close()
    return cert_file.name, key_file.name


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib method name)
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)
            params = {k: v[0] for k, v in params.items()}
            if "response" in params:
                # JARM (response_mode=jwt, see make_request_object): the
                # real params (code/state/error) are claims inside this
                # signed JWT, not top-level query params.
                params = pyjwt.decode(params["response"], options={"verify_signature": False})
            self.server.captured_params = params  # type: ignore[attr-defined]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body>Login concluido. Pode fechar esta aba e voltar ao terminal.</body></html>")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):  # noqa: A002 - silence default stderr logging
        pass


def simulate_login(auth_url: str, cert) -> None:
    """
    Drives the login+consent interaction over plain HTTP, exactly like a
    browser submitting mock_as's forms would -- no CSRF token or JS-driven
    submission exists in mock_as (confirmed by reading views/login.ejs and
    utils/opin/routes.js directly), so a plain requests.Session() carrying
    the session cookie set by the first GET is sufficient. Ported from the
    scratch driver scripts' simulate_login(), which validated this exact
    sequence across all 12 official scenario runs before this function
    existed -- see DECISIONS.md for why the browser this replaced could not
    give a deterministic mTLS connection count.

    Uses its own Session (not the flow's shared one) so the connection
    pattern this produces at the gateway matches what was already validated
    under CRYPTO_PROFILE=pqc: a third, separate connection pool per flow,
    alongside the AS and RS pools -- see DECISIONS.md for the reasoning.
    """
    session = requests.Session()
    session.cert = cert
    session.verify = False

    resp = session.get(auth_url, allow_redirects=True, timeout=60)
    if "/interaction/" not in resp.url:
        raise RuntimeError(f"No interaction page reached; final URL={resp.url}, body[:500]={resp.text[:500]}")

    uid = resp.url.rstrip("/").rsplit("/", 1)[-1]
    if 'name="login"' in resp.text:
        resp = session.post(
            f"https://{AUTH_HOST}/interaction/{uid}/login",
            data={"login": LOGIN_USERNAME, "password": LOGIN_PASSWORD},
            allow_redirects=True, timeout=60,
        )
        if "/interaction/" not in resp.url:
            raise RuntimeError(f"Login did not reach interaction page; final URL={resp.url}, body[:500]={resp.text[:500]}")
        uid = resp.url.rstrip("/").rsplit("/", 1)[-1]

    if "/confirm" not in resp.text:
        raise RuntimeError(f"No consent/confirm page reached; body[:500]={resp.text[:500]}")

    confirm_fields = {}
    for name, value in HIDDEN_ACCOUNTS_RE.findall(resp.text):
        confirm_fields.setdefault(name, []).append(value)

    try:
        session.post(
            f"https://{AUTH_HOST}/interaction/{uid}/confirm",
            data=confirm_fields, allow_redirects=True, timeout=60,
        )
    except requests.exceptions.RequestException:
        pass  # server-side callback already recorded before this response finishes streaming back


def wait_for_authorization_code(
    auth_url: str, cert, timeout_seconds: int = 600, attempt_timeout_seconds: int = 20, max_attempts: int = 3,
) -> str:
    """
    Runs simulate_login() up to max_attempts times against the SAME local
    callback server, each attempt getting attempt_timeout_seconds to
    produce a callback before the whole thing is retried from scratch (a
    fresh session.get(auth_url) onward -- simulate_login always starts a
    brand new interaction, so a retry is a genuinely independent login
    attempt, not a resume of a half-finished one).

    This retry loop exists because of a real, confirmed intermittent race:
    session.post(.../confirm, allow_redirects=True) is supposed to follow
    the redirect chain all the way to this local HTTPS server, but
    occasionally the chain doesn't complete that far (the broad
    `except requests.exceptions.RequestException: pass` in simulate_login
    can't distinguish "reached the local server, then errored while
    streaming the response back" -- the expected, harmless case the
    comment there describes -- from "never reached the local server at
    all"). Confirmed via tracing do_GET() and a classic-mode control run
    with the identical two-flows-one-process pattern: reproduces
    identically regardless of CRYPTO_PROFILE, so it is not specific to
    hybrid mode or this etapa's own changes. See thesis/results/v4/
    DECISIONS.md, Etapa 7, for the full investigation.
    """
    cert_path, key_path = _generate_callback_tls_cert()
    try:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(cert_path, key_path)

        server = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), _CallbackHandler)
        server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
        server.captured_params = None  # type: ignore[attr-defined]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            overall_started = time.time()
            for attempt in range(1, max_attempts + 1):
                simulate_login(auth_url, cert)

                attempt_started = time.time()
                while server.captured_params is None:  # type: ignore[attr-defined]
                    elapsed_total = time.time() - overall_started
                    if elapsed_total > timeout_seconds:
                        raise TimeoutError(
                            f"No callback received after {attempt} simulated login attempt(s) "
                            f"({elapsed_total:.0f}s total)"
                        )
                    if time.time() - attempt_started > attempt_timeout_seconds:
                        break  # give up this attempt, retry simulate_login() from scratch
                    time.sleep(0.5)
                else:
                    break  # captured_params was set -- success, stop retrying
            else:
                raise TimeoutError(f"No callback received after {max_attempts} simulated login attempts")

            params = server.captured_params  # type: ignore[attr-defined]
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
    finally:
        os.unlink(cert_path)
        os.unlink(key_path)

    if "error" in params:
        raise RuntimeError(f"Authorization error: {params}")
    if "code" not in params:
        raise RuntimeError(f"No 'code' in callback params: {params}")
    return params["code"]


def parse_rs_body(response: requests.Response) -> dict:
    """
    The RS (mockapi) signs every response body as a JWS Compact
    Serialization (Content-Type: application/jwt) in BOTH classic and pqc
    CRYPTO_PROFILE -- see insurance-server-lambdas' ResponseSigningFilter
    and thesis/results/experiment2 - PQC/DECISIONS.md, Decision 4.
    response.json() fails on that body (it's "header.payload.signature",
    not JSON) -- empirically confirmed while testing this script: the
    consent-creation call returned 201 with a JWT body, not a JSON object.
    The signature itself isn't verified here (PyJWT has no ML-DSA support,
    matching the same Nimbus gap that motivated the RS's own BouncyCastle
    workaround) -- this script only needs the claims to keep driving the
    flow, not a security proof.
    """
    body = response.text
    if response.headers.get("Content-Type", "").startswith("application/jwt") or body.count(".") == 2:
        return pyjwt.decode(body, options={"verify_signature": False})
    return response.json()


def do_call(session: requests.Session, method: str, url: str, *, cert, headers=None, data=None, host_header=None, src="") -> tuple[dict, requests.Response]:
    """
    Makes one HTTP call and returns (call_dict, response) -- call_dict is in
    the exact shape baseline_automation.compute_metrics()/parse_calls()
    already expects, so the rest of the metrics/report pipeline is reused
    unmodified.

    Takes a shared `session` rather than calling `requests.request()`
    directly: the latter creates and tears down a brand-new Session (hence a
    brand-new TCP+TLS connection) on every single call, which is not how a
    real client (browser or the Conformance Suite's own HTTP client) behaves
    -- and at higher injected latencies it compounds badly enough that the
    320ms scenario's PAR request_uri (oidc-provider's default 60s TTL,
    thesis/results -- see create_and_authorize_consent) expired before the
    flow could finish. A shared, connection-reusing Session per flow doesn't
    change the byte-level metrics (those come from the gateway's own
    countingConn instrumentation, not from this client), only the latency
    this script itself pays -- and more accurately reflects a real client.
    """
    headers = dict(headers or {})
    headers.setdefault("x-fapi-interaction-id", str(uuid.uuid4()))
    if host_header:
        headers["Host"] = host_header

    start = time.time()
    response = session.request(
        method, url, cert=cert, verify=False, headers=headers, data=data, timeout=60
    )
    end = time.time()

    req_headers = dict(response.request.headers)
    req_body = response.request.body or ""
    if isinstance(req_body, bytes):
        req_body = req_body.decode("utf-8", errors="replace")
    resp_headers = dict(response.headers)
    resp_body = response.text or ""

    req_bytes = ba.header_bytes(req_headers) + len(req_body.encode("utf-8"))
    resp_bytes = ba.header_bytes(resp_headers) + len(resp_body.encode("utf-8"))

    endpoint = urlparse(url).path or url
    participant = ba.classify_participant(url)
    jwts = ba.extract_jwts(req_body, req_headers.get("Authorization"), resp_body)
    jwk_sizes = ba.extract_jwk_sizes(resp_body) if endpoint.rstrip("/").endswith("jwks") else []

    call = {
        "endpoint": endpoint,
        "full_uri": url,
        "method": method,
        "src": src,
        "participant": participant,
        "request_bytes": req_bytes,
        "response_bytes": resp_bytes,
        "total_bytes": req_bytes + resp_bytes,
        "latency_ms": (end - start) * 1000,
        "authorization_header": req_headers.get("Authorization"),
        "jwts": jwts,
        "jwt_sizes": [len(j) for j in jwts],
        "jwk_sizes": jwk_sizes,
        "status_code": f"{response.status_code} {response.reason}",
    }
    return call, response


def fetch_server_keys_and_ca(calls, session, cert, crypto_profile):
    # 1. GET /jwks
    call, resp = do_call(session, "GET", f"https://{AUTH_HOST}/jwks", cert=cert, src="FetchServerKeys")
    calls.append(call)

    # 2-3. GET root-ca.pem / issuer-ca.pem. classic: real public sandbox
    # host, no mTLS cert needed (see module docstring: this traffic never
    # touches our local mock stack at all). pqc/hybrid: local stand-ins
    # (ML-DSA-65-only for pqc, RSA+ML-DSA-65 dual nested combiner for
    # hybrid) served by the gateway's "directory" host (mock_mtls's
    # directoryHandler, already used for the OPIN Directory mock) -- see
    # thesis/results/v2/experiment2 - PQC/DECISIONS.md, Decision 11, for why
    # this simulates rather than migrates Raidiam's real sandbox PKI, and
    # thesis/results/v4/DECISIONS.md for hybrid's own stand-ins (closing a
    # symmetry gap: hybrid used to silently fall through to this real,
    # external, classical host instead of getting its own local stand-in).
    ca_host = "directory" if crypto_profile in ("pqc", "hybrid") else "crl.sandbox.pki.opinbrasil.com.br"
    for path in ("root-ca.pem", "issuer-ca.pem"):
        call, resp = do_call(
            session, "GET", f"https://{ca_host}/{path}", cert=None, src="OpinInsertMtlsCa"
        )
        calls.append(call)


def create_and_authorize_consent(calls, session, cert, signing_key, kid, alg, *, permissions, scope, poll_count):
    """
    Shared AS handshake used by both flows (insurance consents and person):
    client_credentials token, create consent, poll its status, PAR + manual
    login, exchange the code. They diverge only in which permissions/scope
    they request, how many times they poll before login, and what they do
    with the resulting token afterward -- confirmed as two genuinely
    separate OPIN API domains/plans, not a single flow with variations, by
    reading both plans' raw logs in
    thesis/results/experiment1 - Classic/0ms/.
    """
    # POST /token (client_credentials)
    assertion = make_client_assertion(signing_key, kid, alg, audience=f"https://{AUTH_MTLS_HOST_HEADER}/token")
    body = {
        "grant_type": "client_credentials",
        "scope": "consents",
        "client_assertion": assertion,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
    }
    call, resp = do_call(
        session, "POST", f"https://{AUTH_HOST}/token", cert=cert, host_header=AUTH_MTLS_HOST_HEADER,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, data=body, src="CallTokenEndpoint",
    )
    calls.append(call)
    resp.raise_for_status()
    cc_access_token = resp.json()["access_token"]

    # POST /open-insurance/consents/v3/consents
    expiration = (datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    consent_body = json.dumps({
        "data": {
            "permissions": permissions,
            "loggedUser": {"document": {"identification": CONSENT_CPF, "rel": "CPF"}},
            "businessEntity": {"document": {"identification": CONSENT_CNPJ, "rel": "CNPJ"}},
            "expirationDateTime": expiration,
        }
    })
    call, resp = do_call(
        session, "POST", f"https://{API_HOST}/open-insurance/consents/v3/consents", cert=cert,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cc_access_token}",
            "x-idempotency-key": str(uuid.uuid4()),
            "x-fapi-auth-date": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
        },
        data=consent_body, src="CallConsentEndpointWithBearerToken",
    )
    calls.append(call)
    resp.raise_for_status()
    consent_id = parse_rs_body(resp)["data"]["consentId"]
    consent_uid = consent_id.rsplit(":", 1)[-1]
    consent_url = f"https://{API_HOST}/open-insurance/consents/v3/consents/{consent_id}"

    # GET consent x poll_count (AWAITING_AUTHORIZATION)
    for _ in range(poll_count):
        call, resp = do_call(
            session, "GET", consent_url, cert=cert,
            headers={"Authorization": f"Bearer {cc_access_token}"}, src="CallProtectedResource",
        )
        calls.append(call)

    # POST /request (PAR)
    state = secrets.token_urlsafe(9)
    nonce = secrets.token_urlsafe(9)
    verifier, challenge = make_pkce_pair()
    request_object = make_request_object(
        signing_key, kid, alg, scope=f"{scope} consent:urn:raidiaminsurance:{consent_uid}",
        state=state, nonce=nonce, code_challenge=challenge,
    )
    par_assertion = make_client_assertion(signing_key, kid, alg, audience=f"https://{AUTH_MTLS_HOST_HEADER}/request")
    par_body = {
        "request": request_object,
        "client_id": CLIENT_ID,
        "client_assertion": par_assertion,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
    }
    call, resp = do_call(
        session, "POST", f"https://{AUTH_HOST}/request", cert=cert, host_header=AUTH_MTLS_HOST_HEADER,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, data=par_body, src="CallPAREndpoint",
    )
    calls.append(call)
    resp.raise_for_status()
    request_uri = resp.json()["request_uri"]

    # Automated login (see simulate_login()/wait_for_authorization_code())
    auth_url = f"https://{AUTH_HOST}/auth?" + urlencode({"client_id": CLIENT_ID, "request_uri": request_uri})
    code = wait_for_authorization_code(auth_url, cert)

    # POST /token (authorization_code)
    ac_assertion = make_client_assertion(signing_key, kid, alg, audience=f"https://{AUTH_MTLS_HOST_HEADER}/token")
    token_body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_assertion": ac_assertion,
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "code_verifier": verifier,
    }
    call, resp = do_call(
        session, "POST", f"https://{AUTH_HOST}/token", cert=cert, host_header=AUTH_MTLS_HOST_HEADER,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, data=token_body, src="CallTokenEndpoint",
    )
    calls.append(call)
    resp.raise_for_status()
    ac_access_token = resp.json()["access_token"]

    return consent_id, consent_url, cc_access_token, ac_access_token


def run_insurance_flow(crypto_profile: str):
    """
    opin-consent-api-status-test-v3 (Insurance consents api test V3.0.0
    plan): 13 HTTP calls -- see the module docstring for the full sequence.
    """
    cert = get_client_cert_paths(crypto_profile)
    signing_key, kid, alg = load_client_signing_key(crypto_profile)
    calls = []
    session = requests.Session()

    fetch_server_keys_and_ca(calls, session, cert, crypto_profile)
    consent_id, consent_url, cc_access_token, ac_access_token = create_and_authorize_consent(
        calls, session, cert, signing_key, kid, alg,
        permissions=INSURANCE_CONSENT_PERMISSIONS, scope=INSURANCE_AUTHORIZATION_SCOPES, poll_count=3,
    )

    # GET consent x2 (AUTHORISED) -- this plan re-checks status after login,
    # the person plan below does not (confirmed against both raw logs). Uses
    # cc_access_token, NOT ac_access_token: confirmed against the real CS
    # log (thesis/results/v1/experiment1 - Classic/0ms/consents_v3__...json)
    # that these post-login consent-status checks reuse the SAME
    # client_credentials token as the pre-login checks (identical bearer
    # token value across calls 6-8 and 11-12) -- the authorization_code
    # token is for actual protected-resource APIs, not the consent-status
    # endpoint. Using ac_access_token here was a bug: the RS rejected it
    # with 401 on every scenario, silently (no raise_for_status() on this
    # loop), which also explains part of the earlier v1-vs-v3 byte/JWT-count
    # mismatch.
    for _ in range(2):
        call, resp = do_call(
            session, "GET", consent_url, cert=cert,
            headers={"Authorization": f"Bearer {cc_access_token}"}, src="CallProtectedResource",
        )
        calls.append(call)

    return calls


def run_person_flow(crypto_profile: str):
    """
    person_api_core_test-module_v2.0.0 (person_test-plan_v2.0.0 plan): 16
    HTTP calls -- jwks/PKI/token/consent/PAR/login/token (8, shared with the
    insurance flow's shape) plus 8 resource calls: GET insurance-person x2,
    then claim/policy-info/premium x2 each for the one policy the account
    has. Sequence and call counts validated against
    thesis/results/experiment1 - Classic/0ms/person_v2__person_api_core_test-module_v2.0.0_20260803T192831Z.json
    -- notably GET insurance-person is called twice, not once, despite it
    reading as a single lookup.
    """
    cert = get_client_cert_paths(crypto_profile)
    signing_key, kid, alg = load_client_signing_key(crypto_profile)
    calls = []
    session = requests.Session()

    fetch_server_keys_and_ca(calls, session, cert, crypto_profile)
    consent_id, _consent_url, _cc_access_token, ac_access_token = create_and_authorize_consent(
        calls, session, cert, signing_key, kid, alg,
        permissions=PERSON_CONSENT_PERMISSIONS, scope=PERSON_AUTHORIZATION_SCOPES, poll_count=1,
    )

    person_url = f"https://{API_HOST}/open-insurance/insurance-person/v2/insurance-person"
    auth_header = {"Authorization": f"Bearer {ac_access_token}"}

    last_resp = None
    for _ in range(2):
        call, resp = do_call(session, "GET", person_url, cert=cert, headers=auth_header, src="CallProtectedResource")
        calls.append(call)
        last_resp = resp
    last_resp.raise_for_status()
    policy_id = parse_rs_body(last_resp)["data"][0]["brand"]["companies"][0]["policies"][0]["policyId"]

    for sub_resource in ("claim", "policy-info", "premium"):
        for _ in range(2):
            call, resp = do_call(
                session, "GET", f"{person_url}/{policy_id}/{sub_resource}", cert=cert,
                headers=auth_header, src="CallProtectedResource",
            )
            calls.append(call)

    return calls


def set_latency(latency_ms: int):
    """
    Same tc/netem logic as set_latency.sh, called via `docker exec` instead
    of shelling out to that script (see the comment on ALLOWED_LATENCY_MS
    for why). Always clears first: "tc qdisc add" fails if a qdisc is
    already attached, "tc qdisc del" on a clean interface is a harmless
    no-op.
    """
    if latency_ms not in ALLOWED_LATENCY_MS:
        raise SystemExit(f"latency_ms must be one of {ALLOWED_LATENCY_MS}, got {latency_ms}")

    subprocess.run(
        ["docker", "exec", GATEWAY_CONTAINER, "tc", "qdisc", "del", "dev", "eth0", "root"],
        capture_output=True,
    )  # ignore failure: no-op if no qdisc was attached

    if latency_ms == 0:
        print(f"Latency reset on {GATEWAY_CONTAINER} (eth0).")
    else:
        subprocess.run(
            ["docker", "exec", GATEWAY_CONTAINER, "tc", "qdisc", "add", "dev", "eth0", "root",
             "netem", "delay", f"{latency_ms}ms"],
            check=True,
        )
        print(f"Latency set to {latency_ms}ms on {GATEWAY_CONTAINER} (eth0).")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("latency_ms", type=int, help=f"WAN latency scenario in ms, one of {ALLOWED_LATENCY_MS}")
    args = parser.parse_args()

    crypto_profile = os.environ.get("CRYPTO_PROFILE", "classic")
    experiment_number = os.environ.get("EXPERIMENT_NUMBER", "2")
    # thesis/results was reorganized into versioned top-level folders
    # (v1 = archived Experiment 1/CS-driven runs, v2 = early Experiment 2
    # docs-only, v3 = current -- both experiment1/experiment2 result trees
    # live under it now). Overridable via env var since another reorg is
    # plausible later and this is the one thing that would need to change.
    results_version = os.environ.get("RESULTS_VERSION", "v3")

    print(
        f"CRYPTO_PROFILE={crypto_profile}  EXPERIMENT_NUMBER={experiment_number}  "
        f"RESULTS_VERSION={results_version}  latency={args.latency_ms}ms"
    )

    set_latency(args.latency_ms)

    run_start = datetime.now(timezone.utc)

    print("\n### Flow 1/2: Insurance consents api test V3.0.0 ###")
    insurance_calls = run_insurance_flow(crypto_profile)

    print("\n### Flow 2/2: person_test-plan_v2.0.0 ###")
    person_calls = run_person_flow(crypto_profile)

    run_end = datetime.now(timezone.utc)
    calls = insurance_calls + person_calls

    gateway_entries = ba.collect_gateway_metrics(run_start, run_end)
    metrics = ba.compute_metrics(
        calls, gateway_entries, latency_scenario_ms=args.latency_ms,
        client_cert_bytes=client_cert_der_bytes(crypto_profile),
    )

    results_root = BASE_DIR / "thesis" / "results" / results_version
    experiment_dir = None
    for candidate in results_root.glob(f"experiment{experiment_number}*"):
        experiment_dir = candidate
        break
    if experiment_dir is None:
        raise SystemExit(
            f"No {results_root}/experiment{experiment_number}* folder found -- create it first "
            f"(see {results_root}/experiment1 - classic and .../experiment2 - PQC for the naming convention)."
        )

    output_dir = experiment_dir / f"{args.latency_ms}ms"
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "baseline_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    def _module_result(module_name, module_calls):
        return {
            "plan_alias": f"opin_flow (crypto_profile={crypto_profile})",
            "module": f"{module_name} (direct, no Conformance Suite)",
            "status": "FINISHED",
            "result": "PASSED" if all(c["status_code"].startswith("2") for c in module_calls) else "FAILED",
            "log_file": "(no raw CS log -- see baseline_metrics.json for the captured calls)",
        }

    module_results = [
        _module_result("opin-consent-api-status-test-v3", insurance_calls),
        _module_result("person_api_core_test-module_v2.0.0", person_calls),
    ]
    ba.write_report_md(metrics, module_results, output_dir / "BASELINE_REPORT.md")

    print(f"\nWrote {output_dir / 'baseline_metrics.json'}")
    print(f"Wrote {output_dir / 'BASELINE_REPORT.md'}")


if __name__ == "__main__":
    main()

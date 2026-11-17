#!/usr/bin/env python3
"""Correcao da Decisao 147 (OPINsize, DECISIONS.md): mede de verdade,
numa execucao LOCAL (docker compose local, NUNCA a frota AWS), o
tamanho real da assinatura interna dos 2 id_tokens (JWE) por execucao,
nos 4 perfis (classico/pqc/hibrido-v8="Control"/hibrido-and="Hybrid").

Nunca altera nenhum arquivo oficial/pinado (orchestrator.py, opin_flow.py,
baseline_automation.py, run_gate.py, PINS.json) -- so LE/importa/reusa
essas funcoes, nunca monkey-patcha em disco (so em memoria, no proprio
processo deste script, restaurado no finally de cada perfil).

Reusa INTEGRALMENTE o caminho oficial de start/stop de stack local
(`run_gate.py`'s `_make_executor`/`teardown_stack`/
`stop_legacy_mtls_alias_collision`) e o MESMO fluxo real que toda
execucao oficial roda (`latency_automation.run_once_timed_with_retry` ->
`opin_flow.run_insurance_flow`/`run_person_flow` ->
`create_and_authorize_consent`), nunca uma rota alternativa.

A UNICA instrumentacao nova: um "spy" em memoria sobre
`opin_flow.decrypt_and_verify_jwt` que CAPTURA o token JWE bruto do
id_token antes de chama-lo de verdade (a verificacao real continua
acontecendo, comportamento idêntico ao oficial) -- nunca decodifica/
decifra nada dentro do proprio opin_flow.py.

Decifragem do JWE (RSA-OAEP + A256GCM, identica nos 4 perfis -- ver
opin_flow.py:872-874) feita aqui, neste script, com a MESMA chave
privada "enc" que o cliente real usa (`opin_flow.load_client_
encryption_key`), usando a biblioteca `cryptography` ja pinada em
`thesis/scripts/requirements.txt`. O JWS interno decifrado e entao
medido pela MESMA funcao oficial (`baseline_automation.jwt_sig_
breakdown`), garantindo a MESMA unidade (bytes brutos decodificados de
base64url, nunca o tamanho da forma transmitida) que os outros 26 JWTs
do OPINsize oficial.

Uso:
  python measure_id_token_signature_local.py [--profiles classico pqc hibrido-v8 hibrido-and]

Saida: thesis/results/v9/opinsize_correction_id_token/id_token_signature_measurements.json
"""
from __future__ import annotations

import argparse
import base64
import importlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CAMPAIGN_SCRIPTS_DIR = REPO_ROOT / "thesis" / "results" / "v9" / "campaign" / "scripts"
THESIS_SCRIPTS_DIR = REPO_ROOT / "thesis" / "scripts"
OUT_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(CAMPAIGN_SCRIPTS_DIR))
sys.path.insert(0, str(THESIS_SCRIPTS_DIR))

import cli  # noqa: E402
import orchestrator as orch  # noqa: E402
import run_gate as rg  # noqa: E402  -- reusa _make_executor/teardown_stack/stop_legacy_mtls_alias_collision

ROUTE = rg.ROUTE  # "L0" -- idem ao run_gate.py, validacao local pura
ALL_PROFILES = list(orch.PROFILES)  # ["classico", "pqc", "hibrido-v8", "hibrido-and"]


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def decrypt_jwe_rsa_oaep_a256gcm(token: str, enc_jwk: dict) -> str:
    """Decifra um JWE compacto de 5 partes (RSA-OAEP + A256GCM, o unico
    esquema que este projeto usa pro id_token -- opin_flow.py:872-874,
    AS_ENC_JWK.alg='RSA-OAEP' em mock-service-os/mock_as/utils/opin/
    configuration.js:70) usando a MESMA chave privada "enc" do cliente
    real. Levanta ValueError alto se o token nao bater exatamente com
    esse esquema -- nunca adivinha nem tenta um esquema alternativo."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    parts = token.split(".")
    if len(parts) != 5:
        raise ValueError(f"esperado JWE compacto de 5 partes, recebido {len(parts)} partes")
    header_b64, ek_b64, iv_b64, ct_b64, tag_b64 = parts
    header = json.loads(_b64url_decode(header_b64))
    if header.get("alg") != "RSA-OAEP":
        raise ValueError(f"JWE alg inesperado: {header.get('alg')!r} (esperado RSA-OAEP)")
    if header.get("enc") != "A256GCM":
        raise ValueError(f"JWE enc inesperado: {header.get('enc')!r} (esperado A256GCM)")

    import jwt as pyjwt_lib

    priv_key = pyjwt_lib.algorithms.RSAAlgorithm.from_jwk(json.dumps(enc_jwk))
    cek = priv_key.decrypt(
        _b64url_decode(ek_b64),
        rsa_padding.OAEP(mgf=rsa_padding.MGF1(algorithm=hashes.SHA1()), algorithm=hashes.SHA1(), label=None),
    )
    iv = _b64url_decode(iv_b64)
    ct = _b64url_decode(ct_b64)
    tag = _b64url_decode(tag_b64)
    aad = header_b64.encode("ascii")  # RFC 7516 sec. 5.1: AAD = ASCII(BASE64URL(protected header))
    plaintext = AESGCM(cek).decrypt(iv, ct + tag, aad)
    return plaintext.decode("utf-8")


def measure_one_profile(gateway_profile: str) -> dict:
    """Roda EXATAMENTE o caminho real de uma execucao oficial
    (latency_automation.run_once_timed_with_retry -> opin_flow.
    run_insurance_flow/run_person_flow), com um spy em memoria sobre
    opin_flow.decrypt_and_verify_jwt que so OBSERVA o token antes de
    repassar pra funcao real (restaurada no finally -- nunca fica
    monkey-patchada em disco nem entre perfis)."""
    opin_profile = orch.CLIENT_CRYPTO_PROFILE_ENV[gateway_profile]
    import os

    os.environ["V9_HARNESS"] = "1"
    os.environ["CRYPTO_PROFILE"] = opin_profile
    os.environ["REMOTE_GATEWAY_HOST"] = "127.0.0.1"

    import opin_flow as of
    import latency_automation as la
    import baseline_automation as ba

    importlib.reload(of)
    importlib.reload(la)

    proxy = of.start_tls_kem_proxy(opin_profile, detached=True)
    signer_started = of.start_pqc_signer_service(opin_profile)

    captured: dict[str, str] = {}
    state = {"flow": None}
    orig_decrypt = of.decrypt_and_verify_jwt

    def _spy_decrypt(token, enc_jwk, *, classic_jwk=None, pqc_jwk=None, expected_alg=None, artifact="id_token"):
        captured[state["flow"]] = token
        return orig_decrypt(
            token, enc_jwk, classic_jwk=classic_jwk, pqc_jwk=pqc_jwk, expected_alg=expected_alg, artifact=artifact,
        )

    of.decrypt_and_verify_jwt = _spy_decrypt
    try:
        state["flow"] = "insurance"
        of.run_insurance_flow(opin_profile)
        state["flow"] = "person"
        of.run_person_flow(opin_profile)
    finally:
        of.decrypt_and_verify_jwt = orig_decrypt
        of.stop_pqc_signer_service(signer_started)
        of.stop_tls_kem_proxy(proxy)
        os.environ.pop("V9_HARNESS", None)

    enc_jwk = of.load_client_encryption_key(opin_profile)
    result = {}
    for flow_name, token in captured.items():
        inner_jws = decrypt_jwe_rsa_oaep_a256gcm(token, enc_jwk)
        breakdown = ba.jwt_sig_breakdown(inner_jws)
        inner_parts = inner_jws.split(".")
        result[flow_name] = {
            "jwe_transmitted_bytes": len(token),
            "jwe_n_parts": len(token.split(".")),
            "inner_jws_header_alg": json.loads(_b64url_decode(inner_parts[0])).get("alg") if len(inner_parts) == 3 else None,
            "inner_jws_n_parts": len(inner_parts),
            "breakdown": breakdown,
            "classical_sig_bytes": breakdown.get("classical_sig_bytes"),
            "pq_sig_bytes": breakdown.get("pq_sig_bytes"),
            "total_sig_bytes_raw": (breakdown.get("classical_sig_bytes") or 0) + (breakdown.get("pq_sig_bytes") or 0),
        }
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", nargs="+", default=ALL_PROFILES, choices=ALL_PROFILES)
    args = ap.parse_args()

    shim_bin_dir = Path(tempfile.mkdtemp(prefix="v9_idtoken_measure_shim_"))
    cli.enable_local_shell_shim(scripts_cwd=THESIS_SCRIPTS_DIR, python_exe=sys.executable, shim_bin_dir=shim_bin_dir)
    executor = rg._make_executor(Path.home() / "images")

    all_results: dict[str, dict] = {}
    errors: dict[str, str] = {}
    try:
        rg.stop_legacy_mtls_alias_collision()
        for gateway_profile in args.profiles:
            print(f"== {gateway_profile} ==", file=sys.stderr)
            try:
                executor.start_block(gateway_profile, ROUTE)
                all_results[gateway_profile] = measure_one_profile(gateway_profile)
            except Exception as e:  # noqa: BLE001 -- registrado, nunca escondido
                errors[gateway_profile] = f"{type(e).__name__}: {e}"
                print(f"  ERRO: {errors[gateway_profile]}", file=sys.stderr)
            finally:
                rg.teardown_stack(executor, gateway_profile)
    finally:
        cli.disable_local_shell_shim()

    out = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "execucao LOCAL real via docker compose (run_gate.py's start_block/teardown_stack), "
                  "NUNCA a frota AWS -- spy em memoria sobre opin_flow.decrypt_and_verify_jwt, "
                  "decifragem RSA-OAEP+A256GCM feita neste script com cryptography, "
                  "medicao da assinatura interna via baseline_automation.jwt_sig_breakdown (mesma funcao oficial)",
        "route": ROUTE,
        "results": all_results,
        "errors": errors,
    }
    out_path = OUT_DIR / "id_token_signature_measurements.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nsalvo em: {out_path}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

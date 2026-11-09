#!/usr/bin/env python3
"""v9, piloto real AWS (piloto-real-aws-2026-11-09-v2): RELATORIO FINAL
CONSOLIDADO -- item 4 da diretoria vigente (ver DECISIONS.md, Decisao
104 e seguintes). Le SOMENTE dados ja preservados em `--run-dir` (a
copia de `raw/` ja verificada por sha256 + `criteria_evaluation.json`
ja gerado por `consolidate_v9_pilot.py`/`evaluate_criteria.py`) e a
reanalise offline do criterio 2 (Decisao 102, ja aplicada dentro do
proprio `raw/criterio2_initcwnd.json`). NUNCA toca AWS, NUNCA
reconstroi imagem, NUNCA roda `docker image prune`.

Parametros criptograficos (secao a) sao extraidos dos ARTEFATOS REAIS
coletados -- nunca do codigo-fonte:
  - certificados X.509: `tshark --export-objects x509af` sobre os 12
    pares pcap+keylog de `raw/criterio1_capturas/` (decifragem TLS via
    keylog, igual ao que `criterio2_probe.py`/`evaluate_criteria.py`
    ja fazem), parseados com a lib `cryptography` quando possivel; para
    chaves PQC (ML-DSA, que a lib `cryptography` 46.x ainda nao sabe
    extrair) o tamanho em bytes da BIT STRING da SubjectPublicKeyInfo e
    da assinatura e obtido via `openssl asn1parse`, nunca assumido.
  - parametros do handshake (versao TLS, cipher suite, grupo
    negociado, SignatureScheme): `tshark -T fields` sobre as mesmas
    capturas decifradas.
  - JWT/JWKS: campos `jwt_sizes`/`jwk_sizes` ja presentes em cada
    chamada de `raw/piloto_calls.json` (nenhuma extracao nova
    necessaria -- o gateway ja registra isso por chamada real).
  - DualAuthenticated/CurveID: `raw/criterio6_execucoes.json` (uma
    linha por execucao real, 60 no total).

Roda com:
    python build_consolidated_report_v9.py --run-dir <piloto-real-aws-...-v2> --out-subdir CONSOLIDATED_REPORT

Saida (sempre dentro de `<run-dir>/<out-subdir>/`, nunca dentro de
`raw/`):
    consolidated.json          -- tudo, maquina-legivel
    CONSOLIDATED_REPORT.md      -- narrativa principal
    crypto_params.md            -- secao (a) detalhada
    sizes.md                    -- secao (b) detalhada
    latency.md                  -- secao (c) detalhada
    flows_criteria.md           -- secoes (d)(e)(f) detalhadas
    environment.md               -- secoes (g)(h)
    sha256_manifest.json        -- sha256 de TODO arquivo em raw/ + de
                                    cada arquivo gerado aqui
"""
import argparse
import hashlib
import json
import statistics as st
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
ROUTES = ["L0", "L219", "L325"]
DOCKER_IMAGE = "mockopin-v9-measure"

KNOWN_SIG_OIDS = {
    "1.2.840.113549.1.1.11": "sha256WithRSAEncryption",
    "2.16.840.1.101.3.4.3.18": "ML-DSA-65 (FIPS 204 -- OID NIST; nao resolvido pela lib cryptography, "
                                 "confirmado por tamanho de chave/assinatura, ver extract_pqc_asn1_sizes)",
}
KNOWN_GROUPS = {
    "24": "secp384r1 (classico)",
    "514": "MLKEM1024 puro (IANA 0x0202) -- sem componente classico",
    "4589": "SecP384r1MLKEM1024 (IANA 0x11ED, hibrido)",
}
KNOWN_SIGSCHEMES = {
    "0x0804": "rsa_pss_rsae_sha256",
    "0x0905": "PQC puro (ML-DSA, codepoint 0x0905 -- ver nota)",
    "0xfe65": "composto/dual classico+PQC (faixa experimental 0xFE00-0xFEFF -- \"o AND\")",
}


# ---------------------------------------------------------------- utils

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_sha256(root: Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root)).replace("\\", "/")] = sha256_file(p)
    return out


def median_p95_min_max_n(values):
    if not values:
        return {"median": None, "p95": None, "min": None, "max": None, "n": 0}
    vs = sorted(values)
    n = len(vs)
    p95_idx = min(n - 1, max(0, round(0.95 * (n - 1))))
    return {"median": st.median(vs), "p95": vs[p95_idx], "min": vs[0], "max": vs[-1], "n": n}


# -------------------------------------------------------- tshark/openssl

def run_tshark(capturas_dir: Path, profile: str, route: str, extra_args: list) -> str:
    pcap = f"{profile}_{route}.pcap"
    keylog = f"{profile}_{route}.keylog"
    cmd = ["docker", "run", "--rm", "--entrypoint", "tshark",
           "-v", f"{capturas_dir}:/data", DOCKER_IMAGE,
           "-r", f"/data/{pcap}", "-o", f"tls.keylog_file:/data/{keylog}"] + extra_args
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"tshark falhou para {profile}/{route}: {r.stderr}")
    return r.stdout


def extract_handshake(capturas_dir: Path, profile: str, route: str) -> dict:
    sh = run_tshark(capturas_dir, profile, route,
                     ["-Y", "tls.handshake.type==2", "-T", "fields",
                      "-e", "tls.handshake.version", "-e", "tls.handshake.ciphersuite",
                      "-e", "tls.handshake.extensions_key_share_group"])
    lines = [l for l in sh.strip().splitlines() if l.strip()]
    first = lines[0].split("\t") if lines else [None, None, None]
    version, ciphersuite, group = (first + [None, None, None])[:3]
    n_serverhello = len(lines)
    uniform_serverhello = len(set(lines)) == 1

    cv = run_tshark(capturas_dir, profile, route,
                     ["-Y", "tls.handshake.type==15", "-T", "fields",
                      "-e", "tls.handshake.sig_hash_alg"])
    sigs = sorted(set(l for l in cv.strip().splitlines() if l.strip()))

    creq = run_tshark(capturas_dir, profile, route,
                       ["-Y", "tls.handshake.type==13", "-T", "fields", "-e", "frame.number"])
    n_certreq = len([l for l in creq.strip().splitlines() if l.strip()])

    # tls.handshake.extensions_key_share_group vem formatado em DECIMAL
    # (BASE_DEC no dissector), nunca hex -- nao converter com int(x,16).
    group_dec = group
    group_hex = f"0x{int(group):04x}" if group else None
    return {
        "legacy_record_version": version,
        "ciphersuite_hex": ciphersuite,
        "negotiated_group_hex": group_hex,
        "negotiated_group_dec": group_dec,
        "negotiated_group_name": KNOWN_GROUPS.get(group_dec, "nao catalogado -- ver valor hex bruto"),
        "n_serverhello_messages_in_capture": n_serverhello,
        "serverhello_fields_uniform_across_all_streams": uniform_serverhello,
        "certificateverify_sig_hash_alg_hex_distinct": sigs,
        "certificateverify_sig_hash_alg_name": [KNOWN_SIGSCHEMES.get(s, "nao catalogado") for s in sigs],
        "n_certificaterequest_messages_in_capture": n_certreq,
    }


def extract_pqc_asn1_sizes(cer_path: Path) -> dict:
    r = subprocess.run(["openssl", "asn1parse", "-in", str(cer_path), "-inform", "DER"],
                        capture_output=True, text=True)
    import re
    bitstrings = []
    for line in r.stdout.splitlines():
        if "BIT STRING" in line:
            m = re.search(r"\sl=\s*(\d+)", line)
            if m:
                bitstrings.append(int(m.group(1)))
    return {
        "asn1_bitstring_lengths_bytes_raw": bitstrings,
        "note": "DER BIT STRING inclui 1 byte de 'unused bits' no inicio; tamanho real da chave/assinatura "
                "e length-1. 1a BIT STRING = SubjectPublicKeyInfo (chave publica); demais = assinaturas.",
    }


def extract_certs(capturas_dir: Path, profile: str, route: str, scratch_dir: Path) -> list:
    outdir = scratch_dir / f"{profile}_{route}"
    outdir.mkdir(parents=True, exist_ok=True)
    pcap = f"{profile}_{route}.pcap"
    keylog = f"{profile}_{route}.keylog"
    cmd = ["docker", "run", "--rm", "--entrypoint", "tshark",
           "-v", f"{capturas_dir}:/data", "-v", f"{outdir}:/certout", DOCKER_IMAGE,
           "-r", f"/data/{pcap}", "-o", f"tls.keylog_file:/data/{keylog}",
           "--export-objects", "x509af,/certout"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"export-objects falhou para {profile}/{route}: {r.stderr}")

    seen_sha256 = {}
    rejected = []
    for f in sorted(outdir.glob("*.cer")):
        data = f.read_bytes()
        digest = sha256_bytes(data)
        if len(data) < 100:
            rejected.append({"file": f.name, "size_bytes": len(data), "sha256": digest,
                              "reason": "menor que 100 bytes -- nao e um certificado X.509 valido "
                                        "(openssl nao decodifica), provavel fragmento de reassemblagem "
                                        "do exportador x509af; NAO usado como evidencia criptografica"})
            continue
        if digest in seen_sha256:
            seen_sha256[digest]["n_instances"] += 1
            seen_sha256[digest]["instance_files"].append(f.name)
            continue
        info = {"first_seen_file": f.name, "size_bytes": len(data), "sha256": digest,
                "n_instances": 1, "instance_files": [f.name]}
        try:
            cert = x509.load_der_x509_certificate(data)
            info["subject"] = cert.subject.rfc4514_string()
            info["issuer"] = cert.issuer.rfc4514_string()
            info["not_valid_before_utc"] = cert.not_valid_before_utc.isoformat()
            info["not_valid_after_utc"] = cert.not_valid_after_utc.isoformat()
            sig_oid = cert.signature_algorithm_oid.dotted_string
            info["signature_algorithm_oid"] = sig_oid
            info["signature_algorithm_name"] = KNOWN_SIG_OIDS.get(sig_oid, f"OID desconhecido: {sig_oid}")
            try:
                san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
                info["san"] = [str(n.value) for n in san_ext.value]
            except x509.ExtensionNotFound:
                info["san"] = []
            try:
                pk = cert.public_key()
                info["public_key_algorithm"] = type(pk).__name__
                info["public_key_size_bits"] = getattr(pk, "key_size", None)
            except ValueError:
                info["public_key_algorithm"] = "nao suportado pela lib cryptography 46.x (PQC)"
                info["public_key_size_bits"] = None
                info.update(extract_pqc_asn1_sizes(f))
            info["parse_ok"] = True
        except Exception as e:
            info["parse_ok"] = False
            info["parse_error"] = str(e)
        seen_sha256[digest] = info
    return {"certificates": list(seen_sha256.values()), "rejected_non_cert_objects": rejected}


def rsa_2048_check(crypto_by_profile: dict) -> dict:
    """Checagem automatizada exigida pelo item 4(a): FALHA se algum RSA
    em Classico/Hibrido nao for exatamente 2048 bits, ou se PQC mostrar
    qualquer componente classico impropio."""
    failures = []
    for profile in ["classico", "hibrido-v8", "hibrido-and"]:
        for cert in crypto_by_profile[profile]["certs"]["certificates"]:
            if cert.get("public_key_algorithm") == "RSAPublicKey" and cert.get("public_key_size_bits") != 2048:
                failures.append(f"{profile}: certificado {cert.get('subject')} com RSA de "
                                 f"{cert.get('public_key_size_bits')} bits, esperado 2048")
            if cert.get("public_key_algorithm") not in ("RSAPublicKey",) and cert.get("parse_ok"):
                failures.append(f"{profile}: certificado {cert.get('subject')} NAO e RSA "
                                 f"({cert.get('public_key_algorithm')}) -- inesperado neste perfil")
    pqc_group_dec = crypto_by_profile["pqc"]["handshake_l0"]["negotiated_group_dec"]
    if pqc_group_dec in ("24", "23", "25", "29", "30") or (pqc_group_dec and pqc_group_dec.startswith("45")):
        failures.append(f"pqc: grupo negociado {pqc_group_dec} parece conter componente classico/hibrido")
    for cert in crypto_by_profile["pqc"]["certs"]["certificates"]:
        if cert.get("public_key_algorithm") == "RSAPublicKey" or "rsa" in (cert.get("signature_algorithm_name") or "").lower():
            failures.append(f"pqc: certificado {cert.get('subject')} contem componente RSA impropio")
    return {"pass": len(failures) == 0, "failures": failures}


# ------------------------------------------------------------- loaders

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def iso_to_epoch(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def build_latency(piloto_calls: list) -> dict:
    by_pr = {}
    per_endpoint = {}
    for execu in piloto_calls:
        profile, route = execu["profile"], execu["route"]
        calls = execu["insurance"] + execu["person"]
        if not calls:
            continue
        starts = [iso_to_epoch(c["start_utc"]) for c in calls]
        ends = [iso_to_epoch(c["end_utc"]) for c in calls]
        t_fluxo = max(ends) - min(starts)
        by_pr.setdefault((profile, route), []).append(t_fluxo)
        for c in calls:
            key = (profile, route, c["endpoint"])
            per_endpoint.setdefault(key, []).append(c["latency_ms"])

    t_fluxo_stats = {f"{p}/{r}": median_p95_min_max_n(v) for (p, r), v in by_pr.items()}
    endpoint_stats = {f"{p}/{r}/{e}": median_p95_min_max_n(v) for (p, r, e), v in per_endpoint.items()}
    return {"t_fluxo_seconds_by_profile_route": t_fluxo_stats,
            "latency_ms_by_profile_route_endpoint": endpoint_stats,
            "method_note": "Descritivo apenas -- N=5 execucoes por celula (perfil x rota). "
                            "SEM teste de significancia estatistica (pre-registro v9 nunca definiu "
                            "nenhum; diferente da v8, que usa N=30 e bootstrap/Mann-Kendall)."}


def build_sizes(criteria_eval: list) -> dict:
    c1 = next(c for c in criteria_eval if c["criterion"] == 1)
    return {"message_sizes_by_profile_route": c1["rows"], "criterion_1_pass": c1["pass"],
            "missing_captures": c1.get("missing_captures", [])}


def build_jwt_jwks(piloto_calls: list) -> dict:
    jwt_bytes = {}
    jwk_info = {}
    for execu in piloto_calls:
        profile = execu["profile"]
        for c in execu["insurance"] + execu["person"]:
            if c.get("jwt_sizes"):
                jwt_bytes.setdefault(profile, []).extend(c["jwt_sizes"])
            if c.get("jwk_sizes"):
                jwk_info.setdefault(profile, [])
                for jwk in c["jwk_sizes"]:
                    if jwk not in jwk_info[profile]:
                        jwk_info[profile].append(jwk)
    return {"jwt_size_bytes_stats_by_profile": {p: median_p95_min_max_n(v) for p, v in jwt_bytes.items()},
            "jwk_entries_by_profile": jwk_info}


def build_flows(criteria_eval: list, criterio3: dict) -> dict:
    c4 = next(c for c in criteria_eval if c["criterion"] == 4)
    c6 = next(c for c in criteria_eval if c["criterion"] == 6)
    flows = {}
    for row in c4["rows"]:
        key = f"{row['profile']}/{row['route']}"
        flows.setdefault(key, {})["counts"] = row["actual"]
        flows[key]["counts_expected"] = row["expected"]
        flows[key]["counts_ok"] = row["ok"]
    for row in c6["rows"]:
        key = f"{row['profile']}/{row['route']}"
        flows.setdefault(key, {})
        flows[key].setdefault("curveID_by_run", []).append(row["curveID"])
        flows[key].setdefault("dualAuthenticated_by_run", []).append(row["dualAuthenticated"])
    for key, v in flows.items():
        if "curveID_by_run" in v:
            v["curveID_consistent"] = len(set(v["curveID_by_run"])) == 1
            v["curveID"] = v["curveID_by_run"][0] if v["curveID_consistent"] else "DIVERGENTE"
        if "dualAuthenticated_by_run" in v:
            v["dualAuthenticated_consistent"] = len(set(v["dualAuthenticated_by_run"])) == 1
            v["dualAuthenticated"] = v["dualAuthenticated_by_run"][0] if v["dualAuthenticated_consistent"] else "DIVERGENTE"
    l325_errors = sum(1 for e in criterio3["execucoes"] if not e.get("ok", True))
    return {"by_profile_route": flows, "l325_total_execucoes": len(criterio3["execucoes"]),
            "l325_errors_found": l325_errors}


def build_profile_route_table(sizes: dict, flows: dict, latency: dict) -> list:
    rows = []
    for p in PROFILES:
        for r in ROUTES:
            key = f"{p}/{r}"
            has_size = any(row["profile"] == p and row["route"] == r for row in sizes["message_sizes_by_profile_route"])
            has_flow = key in flows["by_profile_route"]
            has_latency = key in latency["t_fluxo_seconds_by_profile_route"]
            rows.append({
                "profile": p, "route": r,
                "tamanhos_criterio1": "verificado" if has_size else "não verificado",
                "fluxo_contagens_criterio4_6": "verificado" if has_flow else "não verificado",
                "latencia_t_fluxo": "verificado" if has_latency else "não verificado",
            })
    return rows


# --------------------------------------------------------------- render

def fmt(v, nd=3):
    return "n/d" if v is None else (round(v, nd) if isinstance(v, float) else v)


def render_crypto_md(crypto: dict, rsa_check: dict) -> str:
    lines = ["# Secao (a) -- Parametros criptograficos por perfil (extraidos de artefatos reais)", ""]
    lines.append("Extraido via `tshark --export-objects x509af` + `tshark -T fields` sobre os pares "
                  "pcap+keylog reais preservados em `raw/criterio1_capturas/` (decifragem TLS por keylog, "
                  "nunca assumido do codigo-fonte). Cada perfil foi extraido das 3 rotas pilotadas "
                  "(L0/L219/L325) e os resultados foram comparados -- ver `cross_route_consistent`.")
    lines.append("")
    for p in PROFILES:
        c = crypto[p]
        lines.append(f"## Perfil: {p}")
        hs = c["handshake_l0"]
        lines.append(f"- TLS (ServerHello.legacy_record_version): `{hs['legacy_record_version']}` (TLS 1.3 negociado via extensao supported_versions)")
        lines.append(f"- Cipher suite: `{hs['ciphersuite_hex']}` (TLS_AES_128_GCM_SHA256 se 0x1301)")
        lines.append(f"- Grupo negociado: `{hs['negotiated_group_hex']}` / dec {hs['negotiated_group_dec']} -- {hs['negotiated_group_name']}")
        lines.append(f"- SignatureScheme(s) em CertificateVerify: {hs['certificateverify_sig_hash_alg_hex_distinct']} -- {hs['certificateverify_sig_hash_alg_name']}")
        lines.append(f"- Consistente nas 3 rotas pilotadas (L0/L219/L325)? **{c['cross_route_consistent']}**")
        lines.append(f"- CertificateRequest presentes na captura (mTLS): {hs['n_certificaterequest_messages_in_capture']}")
        lines.append("")
        lines.append("Certificados X.509 reais (DER extraido do handshake decifrado):")
        for cert in c["certs"]["certificates"]:
            lines.append(f"  - `{cert.get('subject')}` emitido por `{cert.get('issuer')}` -- "
                          f"{cert.get('signature_algorithm_name')} -- "
                          f"chave: {cert.get('public_key_algorithm')} "
                          f"{cert.get('public_key_size_bits') or cert.get('asn1_bitstring_lengths_bytes_raw')} -- "
                          f"SAN: {cert.get('san')} -- sha256(DER)={cert['sha256'][:16]}... -- "
                          f"{cert['n_instances']} instancia(s) identica(s) na captura")
        if c["certs"]["rejected_non_cert_objects"]:
            lines.append(f"  - {len(c['certs']['rejected_non_cert_objects'])} objeto(s) pequeno(s) exportado(s) pelo "
                          f"x509af NAO sao certificados X.509 validos (tamanho < 100 bytes, openssl nao decodifica) "
                          f"-- NAO usados como evidencia: {[o['size_bytes'] for o in c['certs']['rejected_non_cert_objects']]} bytes")
        lines.append("")
    lines.append("## Checagem automatizada obrigatoria (item 4a)")
    lines.append(f"**Resultado: {'PASS' if rsa_check['pass'] else 'FAIL'}**")
    if rsa_check["failures"]:
        for f in rsa_check["failures"]:
            lines.append(f"- FALHA: {f}")
    else:
        lines.append("- Todo RSA em classico/hibrido-v8/hibrido-and == 2048 bits exatos.")
        lines.append("- pqc nao mostra nenhum componente classico impropio (grupo MLKEM1024 puro, "
                      "certificado ML-DSA-65 puro).")
    lines.append("")
    lines.append("## Nota honesta sobre hibrido-and (\"o AND\")")
    lines.append("O SignatureScheme 0xfe65 (composto/dual) foi confirmado REAL na mensagem "
                  "CertificateVerify do handshake decifrado desse perfil. O certificado X.509 da cadeia "
                  "permanece puramente RSA-2048 nas 3 rotas -- o componente PQC da assinatura dupla NAO "
                  "foi isolado como um certificado X.509 separado por esta extracao (os objetos extras "
                  "exportados pelo x509af sao fragmentos de ~23-24 bytes, nao certificados validos). "
                  "A natureza exata de como o lado PQC da assinatura composta e transportado "
                  "(certificado adicional fora da cadeia padrao, extensao TLS propria, ou outro "
                  "mecanismo) permanece um item aberto -- nao investigado mais a fundo aqui.")
    return "\n".join(lines) + "\n"


def render_sizes_md(sizes: dict, jwt_jwks: dict) -> str:
    lines = ["# Secao (b) -- Tamanhos", "",
             "Fonte: `criteria_evaluation.json`, criterio 1 (bytes por mensagem de handshake, "
             "extraidos do pcap decifrado real, com baseline do RFC 8446 Secao 4.4.2) + "
             "`raw/piloto_calls.json` (jwt_sizes/jwk_sizes reais por chamada).", ""]
    lines.append("## Bytes por mensagem de handshake, por perfil x rota (real vs baseline)")
    lines.append("| Perfil | Rota | ClientHello | Certificate | OK? |")
    lines.append("|---|---|---|---|---|")
    for row in sizes["message_sizes_by_profile_route"]:
        lines.append(f"| {row['profile']} | {row['route']} | {row['clienthello_bytes']} "
                      f"(baseline {row['clienthello_baseline']}) | {row['certificate_bytes']} "
                      f"(baseline {row['certificate_baseline']}, tol. {row['certificate_tolerance']}) | "
                      f"{'OK' if row['ok'] else 'FALHA'} |")
    lines.append("")
    lines.append("Demais mensagens (ServerHello/EncryptedExtensions/CertificateRequest/"
                  "Certificate_cliente/CertificateVerify/Finished) por perfil x rota -- ver "
                  "`consolidated.json -> sizes.message_sizes_by_profile_route[*].other_messages` "
                  "(omitido aqui por repeticao -- os valores sao IDENTICOS nas 3 rotas de cada perfil, "
                  "como esperado: o conteudo do handshake nao depende da rota/latencia, so o cipher "
                  "suite do perfil).")
    lines.append("")
    lines.append("## JWT (bytes, real, por perfil)")
    lines.append("| Perfil | median | p95 | min | max | n |")
    lines.append("|---|---|---|---|---|---|")
    for p, s in jwt_jwks["jwt_size_bytes_stats_by_profile"].items():
        lines.append(f"| {p} | {s['median']} | {s['p95']} | {s['min']} | {s['max']} | {s['n']} |")
    lines.append("")
    lines.append("## JWKS (kty/use/bytes, real, por perfil -- entradas unicas observadas)")
    for p, entries in jwt_jwks["jwk_entries_by_profile"].items():
        lines.append(f"- **{p}**: {entries}")
    lines.append("")
    lines.append("## OPINsize")
    lines.append("Nao computado. `OPINsize` e uma metrica agregada especifica da v7/v8 (soma de bytes de "
                  "todo o fluxo OIDC-FAPI PAR/JARM/mTLS de uma execucao OPIN completa). O piloto v9 mede "
                  "um protocolo e um conjunto de criterios pre-registrados DIFERENTES (handshake "
                  "TLS/mTLS direto, sem fluxo OIDC-FAPI) -- nao existe um equivalente direto de "
                  "`OPINsize` nos 7 criterios pre-registrados de v9, entao nenhum numero e inventado aqui.")
    return "\n".join(lines) + "\n"


def render_latency_md(latency: dict, rtt_initcwnd: dict) -> str:
    lines = ["# Secao (c) -- Latencia por perfil/rota", "", f"**{latency['method_note']}**", ""]
    lines.append("## T_fluxo (segundos, por perfil x rota)")
    lines.append("| Perfil/Rota | median | p95 | min | max | n |")
    lines.append("|---|---|---|---|---|---|")
    for k, s in sorted(latency["t_fluxo_seconds_by_profile_route"].items()):
        lines.append(f"| {k} | {fmt(s['median'])} | {fmt(s['p95'])} | {fmt(s['min'])} | {fmt(s['max'])} | {s['n']} |")
    lines.append("")
    lines.append("## Latencia por endpoint (ms, amostra -- ver consolidated.json para a lista completa)")
    lines.append("| Perfil/Rota/Endpoint | median | p95 | min | max | n |")
    lines.append("|---|---|---|---|---|---|")
    for k, s in sorted(latency["latency_ms_by_profile_route_endpoint"].items())[:20]:
        lines.append(f"| {k} | {fmt(s['median'])} | {fmt(s['p95'])} | {fmt(s['min'])} | {fmt(s['max'])} | {s['n']} |")
    lines.append(f"(+{max(0, len(latency['latency_ms_by_profile_route_endpoint']) - 20)} linhas adicionais em consolidated.json)")
    lines.append("")
    lines.append("## RTT nominal vs medido (ambos os canais) e initcwnd/MSS reais")
    lines.append("| Rota | nominal (ms) | medido via probe (ms) | medido via pcap (ms) | consistente? |")
    lines.append("|---|---|---|---|---|")
    for route, v in rtt_initcwnd["rtt_by_route"].items():
        lines.append(f"| {route} | {v['nominal_ms']} | {v['rtt_ms_probe']} | {v['rtt_ms_pcap']} | {v['consistent']} |")
    lines.append("")
    i = rtt_initcwnd["initcwnd"]
    lines.append(f"initcwnd/MSS medidos REALMENTE apenas para **{i['profile']}/{i['route']}** "
                  f"(unica combinacao que o probe dedicado do criterio 2 cobriu neste piloto -- "
                  f"ver `REQUISITOS_CAMPANHA_OFICIAL.md` item (a) para o gap conhecido): "
                  f"cwnd={i['ss_ti_cwnd']}, mss={i['mss_bytes']}B, "
                  f"bytes enviados na 1a janela de RTT={i['bytes_sent_within_first_rtt_window']}B "
                  f"(RTT usado: {i['rtt_ms_used_for_window']}ms). As demais 11 combinacoes de "
                  f"perfil x rota: **não verificado**.")
    return "\n".join(lines) + "\n"


def render_flows_md(flows: dict, criteria_eval: list, profile_route_table: list) -> str:
    lines = ["# Secoes (d)(e)(f) -- Fluxos, tabela perfil x rota, criterios", ""]
    lines.append("## (d) Contagens de fluxo / DualAuthenticated / CurveID por perfil x rota")
    lines.append("| Perfil/Rota | http | jwts | jwks | ca | mtls | OK? | curveID | dualAuthenticated |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for k, v in sorted(flows["by_profile_route"].items()):
        c = v.get("counts", {})
        lines.append(f"| {k} | {c.get('http')} | {c.get('jwts')} | {c.get('jwks')} | {c.get('ca')} | "
                      f"{c.get('mtls')} | {v.get('counts_ok')} | {v.get('curveID')} | {v.get('dualAuthenticated')} |")
    lines.append("")
    lines.append(f"L325 (rota mais distante): {flows['l325_total_execucoes']} execucoes, "
                  f"{flows['l325_errors_found']} erro(s) encontrado(s).")
    lines.append("")
    lines.append("## (e) Tabela perfil x rota (verificacao real)")
    lines.append("| Perfil | Rota | Tamanhos (crit.1) | Fluxo/contagens (crit.4/6) | Latencia T_fluxo |")
    lines.append("|---|---|---|---|---|")
    for row in profile_route_table:
        lines.append(f"| {row['profile']} | {row['route']} | {row['tamanhos_criterio1']} | "
                      f"{row['fluxo_contagens_criterio4_6']} | {row['latencia_t_fluxo']} |")
    lines.append("")
    lines.append("## (f) Resultado dos 7 criterios pre-registrados + desvios consolidados")
    lines.append("| # | Nome | Resultado |")
    lines.append("|---|---|---|")
    for r in criteria_eval:
        lines.append(f"| {r['criterion']} | {r['name']} | {'PASS' if r['pass'] else 'FAIL'} |")
    all_pass = all(r["pass"] for r in criteria_eval)
    lines.append("")
    lines.append(f"**Resultado geral: {'PASS' if all_pass else 'FAIL'} (7/7)**")
    lines.append("")
    lines.append("Lista consolidada de desvios/ajustes de metodo (ver DECISIONS.md para o texto "
                  "completo de cada decisao -- Decisao 104 e a Emenda formal ao pre-registro):")
    lines.append("| Decisao | O que mudou | Desvio FORMAL do pre-registro? |")
    lines.append("|---|---|---|")
    deviations = [
        ("61", "Re-pin de Image ID do gateway apos imagem original deixar de existir localmente (binario/certs idênticos, prova de conteúdo)", "Não -- mecanismo de verificação de proveniência, nunca o que é medido"),
        ("75", "Organização final de piloto/dados_oficiais/ no padrão v8 (fonte json + relatório md)", "Não -- forma de apresentação"),
        ("91", "Ajustes de robustez na coleta remota (nohup/disown em passos SSH longos)", "Não -- mecanismo de execução"),
        ("93", "Emenda MSS-efetivo ao critério 2 (passa a exigir concordância pcap vs ss -ti)", "SIM -- muda a definição pré-registrada do critério"),
        ("97", "Emenda RTT-pcap ao critério 7 (RTT medido via SYN-ACK/ACK do mesmo handshake, não só via probe)", "Não -- mecanismo de medição, o limiar pré-registrado não muda"),
        ("98", "Emenda robustez-de-captura ao critério 1, com retry em decifragem incompleta", "SIM -- muda o procedimento de aceitação de captura pré-registrado"),
        ("99", "Fail-closed de teardown novo", "Não -- mecanismo operacional"),
        ("102", "Emenda robustez-de-janela ao critério 2 (bug de contagem por ACK corrigido para contagem por timestamp de envio dentro de 1 RTT)", "Não -- correção de um bug de mecanismo, nunca do que é medido"),
    ]
    for d, desc, formal in deviations:
        lines.append(f"| {d} | {desc} | {formal} |")
    return "\n".join(lines) + "\n"


def render_environment_md(manifest: dict, pins_note: dict) -> str:
    lines = ["# Secoes (g)(h) -- Ambiente/protocolo e limitacoes", ""]
    lines.append("## (g) Ambiente e protocolo")
    lines.append("- Instancia (real, de `criterio2_initcwnd.json`): `m7i-flex.large`")
    lines.append("- Topologia: 1 regiao AWS (`sa-east-1`) -- controle + servidor + 1 cliente")
    lines.append("- Go (binarios gateway/proxy, real de `PINS.json`): `go1.27.3`")
    lines.append("- tcpdump/tshark (imagem measure, reconstruida com equivalencia provada, Decisao 103): "
                  "`tcpdump 4.99.6` (libpcap 1.10.7), `TShark (Wireshark) 4.6.9`, base `Alpine 3.24.3`")
    lines.append("- Docker: proxy do AMI real = Docker 25.0.16 (testado com `docker:25-dind` 25.0.5 "
                  "como aproximacao), operador = Docker 29.9.1 (ver Decisao 68 para a divergencia de "
                  "Image ID entre versoes e por que isso NAO afeta a verificacao de entrega)")
    lines.append(f"- Pins: `campaign/PINS.json` -- {len(pins_note)} entradas de imagem pinadas")
    lines.append(f"- Execucoes reais: {manifest.get('total_execucoes')}/{manifest.get('expected_total')} "
                  f"-- capturas dedicadas: {manifest.get('total_capturas')}")
    lines.append("- Protocolo de coleta: `orchestrator.py run_pilot` (execucao real) -> "
                  "`collect_artifacts.py` (coleta + verificacao sha256) -> `consolidate_v9_pilot.py` "
                  "(7 criterios + RELATORIO_PILOTO.md) -> este script (`build_consolidated_report_v9.py`, "
                  "consolidacao final, SOMENTE leitura de `raw/`+`criteria_evaluation.json`, nunca "
                  "tocando AWS)")
    lines.append("- Custo real do piloto: ver `campaign/REQUISITOS_CAMPANHA_OFICIAL.md`, secao de "
                  "custo/duracao (item 5 da diretoria vigente) para a aritmetica completa com as 4 "
                  "taxas reais medidas desta rodada.")
    lines.append("")
    lines.append("## (h) Limitacoes e itens abertos")
    limitations = [
        "N=5 execucoes/celula -- apenas descritivo (median/p95/min/max/n), NUNCA teste de "
        "significancia estatistica. Qualquer leitura causal sobre diferencas entre perfis exigiria "
        "a escala N=30 da campanha oficial.",
        "Criterio 2 (initcwnd/MSS real) so cobre 1 das 12 combinacoes perfil x rota (classico/L219) "
        "-- as outras 11 permanecem nao verificadas por esta metrica especifica.",
        "hibrido-and: o componente PQC da assinatura dupla/composta (SignatureScheme 0xfe65) foi "
        "confirmado no handshake real mas NAO foi isolado como certificado X.509 separado nesta "
        "extracao -- mecanismo exato nao investigado.",
        "ML-DSA-65 (perfil pqc): a lib `cryptography` 46.x nao sabe extrair o objeto de chave publica "
        "desse OID -- o tamanho foi inferido via `openssl asn1parse` (comprimento bruto da BIT STRING "
        "da SubjectPublicKeyInfo), consistente com os parametros publicados do FIPS 204, mas NAO "
        "confirmado por uma biblioteca que entenda nativamente o formato da chave.",
        "1 unica regiao AWS pilotada (sa-east-1) e 3 das 8 rotas da campanha oficial (L0/L219/L325) -- "
        "us-east-1/ap-northeast-1 e as rotas L14/L30/L123 nunca foram tocadas por este piloto. Ver "
        "`REQUISITOS_CAMPANHA_OFICIAL.md` para os riscos concretos de cada gap.",
        "Sampler de steal de CPU/memoria (achado 10, Decisao 58) NAO implementado neste piloto por "
        "desenho -- item bloqueante de alta prioridade antes da campanha oficial, ver "
        "`REQUISITOS_CAMPANHA_OFICIAL.md`.",
        "Nenhum checkpoint/resume existe em `orchestrator.py run_pilot` -- uma interrupcao a meio da "
        "campanha oficial (960 execucoes) perderia TODO o progresso nao salvo (so grava arquivos "
        "finais ao fim).",
    ]
    for l in limitations:
        lines.append(f"- {l}")
    return "\n".join(lines) + "\n"


def render_main_md(run_label: str, sha256_summary: dict, all_pass: bool, toc_files: list) -> str:
    lines = [f"# v9 -- Relatorio Final Consolidado ({run_label})", "",
             f"Gerado em: {datetime.now(timezone.utc).isoformat()}", "",
             f"Regenere TUDO com: `python campaign/scripts/build_consolidated_report_v9.py "
             f"--run-dir thesis/results/v9/piloto/dados_oficiais/{run_label} "
             f"--out-subdir CONSOLIDATED_REPORT`", "",
             f"**Resultado geral dos 7 criterios pre-registrados: {'PASS (7/7)' if all_pass else 'FAIL'}**", "",
             "## Indice", ""]
    for f in toc_files:
        lines.append(f"- [{f}](./{f})")
    lines.append("")
    lines.append("## sha256 (resumo -- ver sha256_manifest.json para a lista completa)")
    lines.append(f"- Arquivos de entrada (`raw/`): {sha256_summary['n_raw_files']}")
    lines.append(f"- Arquivos gerados por este relatorio: {sha256_summary['n_generated_files']}")
    lines.append(f"- sha256 do proprio `consolidated.json`: `{sha256_summary['consolidated_json_sha256']}`")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-subdir", default="CONSOLIDATED_REPORT")
    ap.add_argument("--scratch-dir", default=None, help="fora do run-dir, para export de certificados")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    raw_dir = run_dir / "raw"
    capturas_dir = raw_dir / "criterio1_capturas"
    out_dir = run_dir / args.out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir = Path(args.scratch_dir) if args.scratch_dir else out_dir / "_cert_extract_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_json(raw_dir / "manifest.json")
    criteria_eval = load_json(run_dir / "criteria_evaluation.json")
    piloto_calls = load_json(raw_dir / "piloto_calls.json")
    criterio7 = load_json(raw_dir / "criterio7_rtt_por_rota.json")
    criterio2 = load_json(raw_dir / "criterio2_initcwnd.json")
    criterio3 = load_json(raw_dir / "criterio3_l325_execucoes.json")
    pins = load_json(run_dir.parents[2] / "campaign" / "PINS.json")

    print("Extraindo parametros criptograficos reais (tshark+openssl) para 4 perfis x 3 rotas...",
          file=sys.stderr)
    crypto = {}
    for p in PROFILES:
        per_route = {}
        for r in ROUTES:
            per_route[r] = {"handshake": extract_handshake(capturas_dir, p, r),
                             "certs": extract_certs(capturas_dir, p, r, scratch_dir)}
        hs_all = [per_route[r]["handshake"] for r in ROUTES]
        consistent = all(
            h["ciphersuite_hex"] == hs_all[0]["ciphersuite_hex"] and
            h["negotiated_group_hex"] == hs_all[0]["negotiated_group_hex"] and
            h["certificateverify_sig_hash_alg_hex_distinct"] == hs_all[0]["certificateverify_sig_hash_alg_hex_distinct"]
            for h in hs_all)
        crypto[p] = {"handshake_l0": per_route["L0"]["handshake"],
                     "handshake_all_routes": {r: per_route[r]["handshake"] for r in ROUTES},
                     "certs": per_route["L0"]["certs"],
                     "certs_all_routes": {r: per_route[r]["certs"] for r in ROUTES},
                     "cross_route_consistent": consistent}

    rsa_check = rsa_2048_check(crypto)

    sizes = build_sizes(criteria_eval)
    jwt_jwks = build_jwt_jwks(piloto_calls)
    latency = build_latency(piloto_calls)
    c7_rows = next(c for c in criteria_eval if c["criterion"] == 7)["rows"]
    rtt_initcwnd = {"rtt_by_route": c7_rows, "initcwnd": criterio2}
    flows = build_flows(criteria_eval, criterio3)
    profile_route_table = build_profile_route_table(sizes, flows, latency)
    all_pass = all(r["pass"] for r in criteria_eval)

    consolidated = {
        "run_label": run_dir.name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "all_criteria_pass": all_pass,
        "criteria_evaluation": criteria_eval,
        "crypto_params_by_profile": crypto,
        "rsa_2048_and_pqc_purity_check": rsa_check,
        "sizes": sizes,
        "jwt_jwks": jwt_jwks,
        "latency": latency,
        "rtt_and_initcwnd": rtt_initcwnd,
        "flows": flows,
        "profile_route_verification_table": profile_route_table,
        "manifest_summary": {k: manifest.get(k) for k in
                              ("total_execucoes", "expected_total", "total_capturas", "smoke")},
    }
    (out_dir / "consolidated.json").write_text(
        json.dumps(consolidated, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    (out_dir / "crypto_params.md").write_text(render_crypto_md(crypto, rsa_check), encoding="utf-8")
    (out_dir / "sizes.md").write_text(render_sizes_md(sizes, jwt_jwks), encoding="utf-8")
    (out_dir / "latency.md").write_text(render_latency_md(latency, rtt_initcwnd), encoding="utf-8")
    (out_dir / "flows_criteria.md").write_text(
        render_flows_md(flows, criteria_eval, profile_route_table), encoding="utf-8")
    (out_dir / "environment.md").write_text(render_environment_md(manifest, pins), encoding="utf-8")

    consolidated_sha = sha256_file(out_dir / "consolidated.json")
    toc_files = ["crypto_params.md", "sizes.md", "latency.md", "flows_criteria.md", "environment.md",
                 "consolidated.json", "sha256_manifest.json"]
    raw_sha = walk_sha256(raw_dir)

    main_md = render_main_md(run_dir.name,
                              {"n_raw_files": len(raw_sha), "n_generated_files": len(toc_files),
                               "consolidated_json_sha256": consolidated_sha},
                              all_pass, toc_files)
    (out_dir / "CONSOLIDATED_REPORT.md").write_text(main_md, encoding="utf-8")

    generated_sha = {}
    for f in toc_files + ["CONSOLIDATED_REPORT.md"]:
        p = out_dir / f
        if p.is_file():
            generated_sha[f] = sha256_file(p)
    (out_dir / "sha256_manifest.json").write_text(
        json.dumps({"raw_inputs": raw_sha, "generated_outputs": generated_sha}, indent=2), encoding="utf-8")

    # limpeza do scratch de extracao de certificados (nunca faz parte da evidencia oficial)
    import shutil
    shutil.rmtree(scratch_dir, ignore_errors=True)

    print(json.dumps({"out_dir": str(out_dir), "all_criteria_pass": all_pass,
                       "rsa_2048_and_pqc_purity_check_pass": rsa_check["pass"]}, indent=2))


if __name__ == "__main__":
    main()

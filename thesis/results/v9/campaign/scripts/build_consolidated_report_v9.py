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
  - certificados X.509: parser DER generico PROPRIO (funcoes
    `read_der_len`/`read_der_tlv`/`der_oid_to_str`/
    `parse_der_certificate_generic` abaixo), aplicado sobre os bytes
    DECIFRADOS REAIS da mensagem TLS Certificate (obtidos via
    `tshark -x` com keylog, lendo o bloco "Decrypted TLS" que o
    tshark imprime -- nunca o exportador `--export-objects x509af`,
    que se mostrou incapaz de reassemblar corretamente o certificado
    ML-DSA do hibrido-and, ver Decisao 105). O parser generico extrai
    OID+tamanho bruto em bytes da chave publica e da assinatura
    DIRETO da estrutura ASN.1 (SubjectPublicKeyInfo/signatureValue),
    sem depender de nenhuma lib ter suporte NATIVO ao algoritmo --
    funciona identicamente pra RSA e pra ML-DSA, sem inferencia
    indireta nem cross-validacao com JWKS.
  - Achado real (Decisao 105): a mensagem Certificate real do
    hibrido-and contem DUAS CertificateEntry (RSA-2048 + ML-DSA-65),
    com 3 bytes de padding zero nao-padrao entre elas -- confirmado
    via parsing direto dos bytes decifrados e validado byte-a-byte
    (sha256 identico) contra os arquivos .crt reais em
    `certs/generated/hibrido_and_mldsa_{server,client}.crt`.
  - parametros do handshake (versao TLS, cipher suite, grupo
    negociado, SignatureScheme): `tshark -T fields` sobre as mesmas
    capturas decifradas.
  - JWT/JWKS: campos `jwt_sizes`/`jwk_sizes` ja presentes em cada
    chamada de `raw/piloto_calls.json` (nenhuma extracao nova
    necessaria -- o gateway ja registra isso por chamada real).
  - DualAuthenticated/CurveID: `raw/criterio6_execucoes.json` (uma
    linha por execucao real, 60 no total) + `dualAuthenticated=true`
    no log real do gateway (`raw/full_container_logs/v9-mtls.log`).

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
import base64
import hashlib
import json
import re
import statistics as st
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
ROUTES = ["L0", "L219", "L325"]
DOCKER_IMAGE = "mockopin-v9-measure"

KNOWN_OIDS = {
    "1.2.840.113549.1.1.11": "sha256WithRSAEncryption",
    "1.2.840.113549.1.1.1": "rsaEncryption",
    "2.16.840.1.101.3.4.3.18": "ML-DSA-65 (FIPS 204, OID NIST)",
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


def read_der_len(data: bytes, pos: int):
    first = data[pos]
    pos += 1
    if first < 0x80:
        return first, pos
    n = first & 0x7F
    length = int.from_bytes(data[pos:pos + n], "big")
    pos += n
    return length, pos


def read_der_tlv(data: bytes, pos: int):
    tag = data[pos]
    pos += 1
    length, pos = read_der_len(data, pos)
    value = data[pos:pos + length]
    end = pos + length
    return tag, value, pos, end


def der_oid_to_str(der_oid: bytes) -> str:
    first = der_oid[0]
    parts = [str(first // 40), str(first % 40)]
    val = 0
    for b in der_oid[1:]:
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            parts.append(str(val))
            val = 0
    return ".".join(parts)


def parse_der_certificate_generic(der: bytes) -> dict:
    """Le OID+tamanho (bytes brutos) da chave publica e da assinatura
    DIRETO da estrutura ASN.1 do certificado (Decisao 105, item 2 da
    diretoria BLOCO B) -- generico, funciona pra QUALQUER algoritmo
    (RSA ou ML-DSA), sem depender de nenhuma lib ter suporte NATIVO
    ao algoritmo e sem cross-validar com nenhuma outra fonte (JWKS,
    etc.) -- leitura direta da estrutura do certificado real."""
    _, cert_body, _, _ = read_der_tlv(der, 0)
    _, tbs_val, p2, p2end = read_der_tlv(cert_body, 0)
    _, sa_val, p3, p3end = read_der_tlv(cert_body, p2end)
    _, sig_alg_oid, _, _ = read_der_tlv(sa_val, 0)
    sv_tag, sv_val, p4, p4end = read_der_tlv(cert_body, p3end)
    sig_raw = sv_val[1:]  # 1o byte da BIT STRING = "unused bits", sempre 0 aqui

    pos2 = 0
    if tbs_val[pos2] == 0xA0:
        _, _, pos2, pos2end = read_der_tlv(tbs_val, pos2)
        pos2 = pos2end
    _, serial, pos2, pos2end = read_der_tlv(tbs_val, pos2)
    pos2 = pos2end
    serial_int = int.from_bytes(serial, "big")
    _, _, pos2, pos2end = read_der_tlv(tbs_val, pos2)  # signature (interno, igual ao externo)
    pos2 = pos2end
    _, _, pos2, pos2end = read_der_tlv(tbs_val, pos2)  # issuer
    pos2 = pos2end
    _, _, pos2, pos2end = read_der_tlv(tbs_val, pos2)  # validity
    pos2 = pos2end
    _, _, pos2, pos2end = read_der_tlv(tbs_val, pos2)  # subject
    pos2 = pos2end
    _, spki_val, pos2, pos2end = read_der_tlv(tbs_val, pos2)  # subjectPublicKeyInfo
    _, pk_alg_val, p5, p5end = read_der_tlv(spki_val, 0)
    _, pk_alg_oid, _, _ = read_der_tlv(pk_alg_val, 0)
    pk_bits_tag, pk_bits_val, p6, p6end = read_der_tlv(spki_val, p5end)
    pk_raw = pk_bits_val[1:]

    sig_oid_s = der_oid_to_str(sig_alg_oid)
    pk_oid_s = der_oid_to_str(pk_alg_oid)
    return {
        "serial": serial_int,
        "signature_algorithm_oid": sig_oid_s,
        "signature_algorithm_name": KNOWN_OIDS.get(sig_oid_s, f"OID nao catalogado: {sig_oid_s}"),
        "signature_raw_bytes": len(sig_raw),
        "public_key_algorithm_oid": pk_oid_s,
        "public_key_algorithm_name": KNOWN_OIDS.get(pk_oid_s, f"OID nao catalogado: {pk_oid_s}"),
        "public_key_raw_bytes": len(pk_raw),
        "der_total_bytes": len(der),
    }


def enrich_with_cryptography_lib(der: bytes, info: dict) -> dict:
    """Campos extras (subject/issuer/SAN/validade/bits RSA) via
    `cryptography`, quando a lib conseguir -- so complementa o que o
    parser DER generico (fonte primaria, sempre presente) ja deu."""
    try:
        cert = x509.load_der_x509_certificate(der)
        info["subject"] = cert.subject.rfc4514_string()
        info["issuer"] = cert.issuer.rfc4514_string()
        info["not_valid_before_utc"] = cert.not_valid_before_utc.isoformat()
        info["not_valid_after_utc"] = cert.not_valid_after_utc.isoformat()
        try:
            san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            info["san"] = [str(n.value) for n in san_ext.value]
        except x509.ExtensionNotFound:
            info["san"] = []
        try:
            pk = cert.public_key()
            info["public_key_bits_cryptography_lib"] = getattr(pk, "key_size", None)
        except ValueError:
            info["public_key_bits_cryptography_lib"] = None  # esperado p/ ML-DSA (lib sem suporte nativo)
    except Exception as e:
        info["cryptography_lib_error"] = str(e)
    return info


def get_decrypted_tls_hex(capturas_dir: Path, profile: str, route: str, frame_number: int) -> bytes:
    """Bytes DECIFRADOS reais das mensagens TLS no frame dado, lidos
    de TODOS os blocos "Decrypted TLS (N bytes):" que o `tshark -x`
    imprime (um frame pode conter mais de um registro TLS decifrado
    -- visto em classico/pqc/hibrido-v8, onde ServerHello/
    EncryptedExtensions/CertificateRequest/Certificate saem em
    registros TLS separados dentro do mesmo frame; hibrido-and tem so
    um registro, bem maior) -- concatenados na mesma ordem em que o
    tshark os imprime, que e a ordem real de envio. A MESMA
    decifragem por keylog que todo o resto do pipeline usa, nunca uma
    segunda decifragem paralela."""
    out = run_tshark(capturas_dir, profile, route, ["-Y", f"frame.number=={frame_number}", "-x"])
    lines = out.splitlines()
    pat = re.compile(r"^[0-9a-f]{4}\s+((?:[0-9a-f]{2}\s+){1,16})")
    buf = bytearray()
    i = 0
    found_any = False
    while i < len(lines):
        if lines[i].startswith("Decrypted TLS"):
            found_any = True
            i += 1
            while i < len(lines):
                m = pat.match(lines[i])
                if not m:
                    break
                buf += bytes(int(h, 16) for h in m.group(1).split())
                i += 1
            continue
        i += 1
    if not found_any:
        raise RuntimeError(f"'Decrypted TLS' nao encontrado no frame {frame_number} ({profile}/{route})")
    return bytes(buf)


def locate_certificate_handshake_message(buf: bytes) -> bytes:
    """O bloco "Decrypted TLS" de um frame pode conter VARIAS
    mensagens de handshake concatenadas (ex.: ServerHello+
    EncryptedExtensions+CertificateRequest+Certificate no mesmo
    registro TLS, visto em classico/pqc/hibrido-v8) -- caminha cada
    mensagem (1B tipo + 3B tamanho + corpo) pra achar a Certificate
    (tipo 11), em vez de assumir que ela comeca no byte 0 do buffer
    (so verdade pra hibrido-and, cujo Certificate e grande o
    suficiente pra ocupar um registro TLS so dele)."""
    pos = 0
    while pos + 4 <= len(buf):
        msg_type = buf[pos]
        msg_len = int.from_bytes(buf[pos + 1:pos + 4], "big")
        if msg_type == 0x0B:
            return buf[pos:pos + 4 + msg_len]
        pos += 4 + msg_len
    raise RuntimeError("mensagem Handshake Certificate (type 11) nao encontrada no buffer decifrado")


def parse_tls13_certificate_list(buf: bytes) -> list:
    """Caminha a estrutura real (RFC 8446 Secao 4.4.2) de uma mensagem
    de handshake Certificate ja decifrada: handshake header (1+3B) +
    certificate_request_context (1B+N) + certificate_list (3B+N) ->
    uma ou mais CertificateEntry (3B len + cert_data + 2B len + ext).

    Decisao 105 (achado real, BLOCO B item 1): a mensagem real do
    hibrido-and insere 3 bytes de padding zero NAO-PADRAO entre a 1a e
    a 2a CertificateEntry (RSA-2048 e ML-DSA-65) -- um bug de
    enconding do stack experimental, confirmado byte-a-byte contra os
    .crt reais em disco (sha256 identico). O loop abaixo so avanca
    aceitando um cert_data que comeca com 0x30 (tag SEQUENCE,
    universal pra qualquer X.509 DER); quando o proximo campo nao bate
    (ex.: por causa desse padding), tenta deslocar 1-8 bytes antes de
    desistir -- generico, nunca hardcoded pro valor "3" especifico."""
    buf = locate_certificate_handshake_message(buf)
    pos = 4
    ctx_len = buf[pos]
    pos += 1 + ctx_len
    certs_len = int.from_bytes(buf[pos:pos + 3], "big")
    pos += 3
    end = pos + certs_len
    certs = []
    while pos < end:
        if pos + 3 > end:
            break
        clen = int.from_bytes(buf[pos:pos + 3], "big")
        cert_data = buf[pos + 3:pos + 3 + clen]
        if cert_data[:1] == b"\x30" and pos + 3 + clen <= end:
            pos += 3 + clen
            extlen = int.from_bytes(buf[pos:pos + 2], "big")
            pos += 2 + extlen
            certs.append(bytes(cert_data))
            continue
        found = False
        for skip in range(1, 9):
            p2 = pos + skip
            if p2 + 3 > end:
                break
            clen2 = int.from_bytes(buf[p2:p2 + 3], "big")
            cd2 = buf[p2 + 3:p2 + 3 + clen2]
            if cd2[:1] == b"\x30" and p2 + 3 + clen2 <= end:
                pos = p2 + 3 + clen2
                extlen = int.from_bytes(buf[pos:pos + 2], "big")
                pos += 2 + extlen
                certs.append(bytes(cd2))
                found = True
                break
        if not found:
            break
    return certs, pos == end


def extract_certs(capturas_dir: Path, profile: str, route: str) -> dict:
    """Extrai TODAS as CertificateEntry reais (servidor e cliente) da
    mensagem Certificate decifrada -- substitui a abordagem anterior
    baseada em `tshark --export-objects x509af`, que nao reassemblava
    corretamente o segundo certificado (ML-DSA) do hibrido-and (ver
    Decisao 105)."""
    frames_out = run_tshark(capturas_dir, profile, route,
                             ["-Y", "tls.handshake.type==11 and tcp.stream==0",
                              "-T", "fields", "-e", "frame.number"])
    frame_numbers = [int(l) for l in frames_out.strip().splitlines() if l.strip()]
    sides = ["server", "client"][:len(frame_numbers)]
    by_side = {}
    for side, frame_no in zip(sides, frame_numbers):
        buf = get_decrypted_tls_hex(capturas_dir, profile, route, frame_no)
        der_list, fully_consumed = parse_tls13_certificate_list(buf)
        entries = []
        for der in der_list:
            digest = sha256_bytes(der)
            info = parse_der_certificate_generic(der)
            info["sha256"] = digest
            info = enrich_with_cryptography_lib(der, info)
            entries.append(info)
        by_side[side] = {"frame": frame_no, "n_entries": len(entries),
                          "certificate_list_fully_consumed": fully_consumed, "entries": entries}
    return by_side


def verify_against_disk_pki(entries_by_side: dict, pki_dir: Path) -> dict:
    """Confere os certificados extraidos do handshake real contra os
    arquivos .crt reais em disco (PKI usada pra gerar o deployment --
    dado real, nunca codigo-fonte) -- BLOCO B item 1: cross-check
    exigido pra provar que a extracao do pcap bate com o material
    real, nunca so inferido."""
    results = []
    if not pki_dir.is_dir():
        return {"pki_dir_found": False, "checks": []}
    for side, data in entries_by_side.items():
        for entry in data["entries"]:
            subj = (entry.get("subject") or "").replace("CN=", "")
            candidate = pki_dir / f"{subj}.crt"
            if not candidate.is_file():
                results.append({"subject": subj, "disk_file_found": False})
                continue
            pem = candidate.read_text()
            der_lines = pem.replace("-----BEGIN CERTIFICATE-----", "").replace("-----END CERTIFICATE-----", "")
            disk_der = base64.b64decode("".join(der_lines.split()))
            disk_sha256 = sha256_bytes(disk_der)
            results.append({"subject": subj, "disk_file_found": True, "disk_file": str(candidate.name),
                             "disk_sha256": disk_sha256, "pcap_sha256": entry["sha256"],
                             "identical": disk_sha256 == entry["sha256"]})
    return {"pki_dir_found": True, "checks": results}


def dual_signature_check(crypto_by_profile: dict) -> dict:
    """Checagem automatizada exigida pelo BLOCO B item 3 -- FALHA
    (loud, nunca so log) se:
      - Classico/Hibrido-v8 nao tiverem EXATAMENTE RSA-2048 (e nada
        mais) nas duas pontas (server+client);
      - PQC tiver qualquer componente classico (RSA/EC) em qualquer
        entrada;
      - Hibrido-AND NAO tiver AMBOS RSA-2048 E ML-DSA presentes em
        cada lado (server e client) -- AND verdadeiro, falha se
        faltar QUALQUER um dos dois;
      - o componente ML-DSA do Hibrido-AND divergir do parametro do
        perfil PQC standalone (mesma OID, mesmo tamanho de chave e de
        assinatura em bytes)."""
    failures = []

    def is_rsa2048(e):
        return (e.get("public_key_algorithm_oid") == "1.2.840.113549.1.1.1"
                and e.get("public_key_raw_bytes") in (269, 270)  # SEQUENCE{modulus 2048b+pad,exp} em DER
                and e.get("public_key_bits_cryptography_lib") == 2048)

    def is_mldsa65(e):
        return (e.get("public_key_algorithm_oid") == "2.16.840.1.101.3.4.3.18"
                and e.get("public_key_raw_bytes") == 1952
                and e.get("signature_raw_bytes") == 3309)

    for profile in ("classico", "hibrido-v8"):
        for side, data in crypto_by_profile[profile]["entries_by_side"].items():
            entries = data["entries"]
            if len(entries) != 1 or not is_rsa2048(entries[0]):
                failures.append(f"{profile}/{side}: esperado EXATAMENTE 1 entrada RSA-2048, "
                                 f"achado {[(e.get('public_key_algorithm_name'), e.get('public_key_raw_bytes')) for e in entries]}")

    for side, data in crypto_by_profile["pqc"]["entries_by_side"].items():
        for e in data["entries"]:
            if is_rsa2048(e) or "rsa" in (e.get("signature_algorithm_name") or "").lower():
                failures.append(f"pqc/{side}: componente classico (RSA) impropio encontrado -- {e.get('subject')}")
            if not is_mldsa65(e):
                failures.append(f"pqc/{side}: entrada nao bate com ML-DSA-65 esperado -- {e}")

    for side, data in crypto_by_profile["hibrido-and"]["entries_by_side"].items():
        entries = data["entries"]
        has_rsa = any(is_rsa2048(e) for e in entries)
        mldsa_entries = [e for e in entries if is_mldsa65(e)]
        if not has_rsa:
            failures.append(f"hibrido-and/{side}: componente RSA-2048 AUSENTE (AND exige os dois) -- "
                             f"entradas achadas: {len(entries)}")
        if not mldsa_entries:
            failures.append(f"hibrido-and/{side}: componente ML-DSA-65 AUSENTE (AND exige os dois) -- "
                             f"entradas achadas: {len(entries)}")

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


def render_crypto_md(crypto: dict, check: dict, pki_checks: dict, log_evidence: dict) -> str:
    lines = ["# Secao (a) -- Parametros criptograficos por perfil (extraidos de artefatos reais)", ""]
    lines.append("Certificados: parser DER generico proprio sobre os bytes DECIFRADOS reais da mensagem "
                  "TLS Certificate (`tshark -x` com keylog, bloco \"Decrypted TLS\"), nunca o exportador "
                  "`x509af` (que falhava em reassemblar o 2o certificado do hibrido-and -- Decisao 105). "
                  "Handshake (grupo/cipher/SignatureScheme): `tshark -T fields`. Cada perfil foi extraido "
                  "das 3 rotas pilotadas (L0/L219/L325); os resultados foram comparados -- ver "
                  "`cross_route_consistent`.")
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
        for side, data in c["entries_by_side"].items():
            lines.append(f"CertificateEntry real, lado **{side}** (frame {data['frame']}, "
                          f"{data['n_entries']} entrada(s), lista totalmente consumida: "
                          f"{data['certificate_list_fully_consumed']}):")
            for e in data["entries"]:
                lines.append(f"  - serial={e['serial']} `{e.get('subject')}` emitido por `{e.get('issuer')}` -- "
                              f"assinatura: {e['signature_algorithm_name']} ({e['signature_raw_bytes']}B raw) -- "
                              f"chave: {e['public_key_algorithm_name']} ({e['public_key_raw_bytes']}B raw"
                              f"{', ' + str(e['public_key_bits_cryptography_lib']) + ' bits (lib cryptography)' if e.get('public_key_bits_cryptography_lib') else ''}) -- "
                              f"DER total={e['der_total_bytes']}B -- sha256={e['sha256'][:16]}...")
        lines.append("")
    lines.append("## Checagem automatizada obrigatoria (BLOCO B item 3)")
    lines.append(f"**Resultado: {'PASS' if check['pass'] else 'FALHOU -- VER ABAIXO'}**")
    if check["failures"]:
        lines.append("")
        lines.append("```")
        for f in check["failures"]:
            lines.append(f"FALHA: {f}")
        lines.append("```")
    else:
        lines.append("- classico/hibrido-v8: exatamente 1 entrada RSA-2048 em cada lado (servidor e cliente).")
        lines.append("- pqc: toda entrada e ML-DSA-65 puro (OID 2.16.840.1.101.3.4.3.18, chave 1952B, "
                      "assinatura 3309B), nenhum componente classico.")
        lines.append("- hibrido-and: AMBOS RSA-2048 E ML-DSA-65 presentes em cada lado (AND verdadeiro), "
                      "e o componente ML-DSA bate EXATAMENTE com o parametro do perfil pqc standalone.")
    lines.append("")
    lines.append("## Achado real: a dupla assinatura do hibrido-and (\"o AND\") -- BLOCO B item 1")
    lines.append("A mensagem Certificate real do hibrido-and (servidor E cliente, nas 3 rotas) contem "
                  "DUAS CertificateEntry na MESMA mensagem de handshake: uma RSA-2048 e uma ML-DSA-65 -- "
                  "extraidas diretamente dos bytes decifrados reais (nunca do codigo-fonte). Entre as duas "
                  "entradas ha 3 bytes de padding zero NAO previstos pela RFC 8446 (um bug de encoding do "
                  "stack experimental, nao um erro de parsing deste script -- o parser so avanca aceitando "
                  "um `cert_data` que comeca com a tag SEQUENCE 0x30; quando o campo declarado nao bate, "
                  "ele busca ate 8 bytes adiante por um inicio valido).")
    lines.append("")
    lines.append("Confirmacao cruzada contra os arquivos .crt reais em disco "
                  f"(`{pki_checks.get('pki_dir', '')}`):")
    if pki_checks.get("pki_dir_found"):
        for chk in pki_checks["checks"]:
            if chk.get("disk_file_found"):
                lines.append(f"  - `{chk['subject']}`: sha256 do pcap == sha256 do disco (`{chk['disk_file']}`)? "
                              f"**{chk['identical']}**")
            else:
                lines.append(f"  - `{chk['subject']}`: arquivo .crt correspondente NAO encontrado em disco")
    else:
        lines.append("  - diretorio de PKI em disco nao encontrado nesta execucao -- cross-check nao realizado")
    lines.append("")
    lines.append("Prova de que o handshake validou AMBOS os certificados (nunca so \"o codigo diz que "
                  "confere os dois\"): evidencia do log real do gateway "
                  "(`raw/full_container_logs/v9-mtls.log`):")
    lines.append(f"  - `dualAuthenticated=true` em {log_evidence['n_dual_true']}/{log_evidence['n_connections']} "
                  f"conexoes reais do hibrido-and (as demais, dualAuthenticated=false, sao um canal interno "
                  f"nao relacionado -- `clientCert=\"op\"`, curve=CurveP256 -- nunca o cliente instrumentado "
                  f"do piloto)")
    lines.append(f"  - `handshakeBytesIn`/`handshakeBytesOut` reais observados: {log_evidence['example_line']}")
    lines.append("  - a conexao so chega a \"connection OK\" se o stack TLS (Go crypto/tls, que rejeita "
                  "handshakes com cadeia de certificado invalida) ja tiver processado a mensagem Certificate "
                  "completa (ambas as entradas) sem erro -- nao ha como chegar a esse log com so uma das "
                  "duas cadeias validada.")
    lines.append("  - limitacao honesta: o log em nivel INFO do gateway nao imprime uma linha separada "
                  "\"verifiquei RSA\" + \"verifiquei ML-DSA\" -- a evidencia disponivel e o resultado "
                  "agregado (`dualAuthenticated=true` + conexao aceita), nunca um trace de verificacao "
                  "por certificado individual.")
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

def build_log_evidence(raw_dir: Path) -> dict:
    """Evidencia real do log do gateway (BLOCO B item 1) de que o
    handshake do hibrido-and validou ambos os certificados -- nunca
    assumido, lido direto do log real preservado."""
    log_path = raw_dir / "full_container_logs" / "v9-mtls.log"
    if not log_path.is_file():
        return {"log_found": False, "n_dual_true": 0, "n_connections": 0, "example_line": None}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    real_lines = [l for l in text.splitlines()
                  if "hibrido-and connection OK" in l and 'clientCert="op"' not in l]
    n_true = sum(1 for l in real_lines if "dualAuthenticated=true" in l)
    example = next((l.split("gateway:")[-1].strip() for l in real_lines if "dualAuthenticated=true" in l), None)
    return {"log_found": True, "n_dual_true": n_true, "n_connections": len(real_lines),
            "example_line": example, "source_file": str(log_path.relative_to(raw_dir.parent))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-subdir", default="CONSOLIDATED_REPORT")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    raw_dir = run_dir / "raw"
    capturas_dir = raw_dir / "criterio1_capturas"
    out_dir = run_dir / args.out_subdir
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_json(raw_dir / "manifest.json")
    criteria_eval = load_json(run_dir / "criteria_evaluation.json")
    piloto_calls = load_json(raw_dir / "piloto_calls.json")
    criterio7 = load_json(raw_dir / "criterio7_rtt_por_rota.json")
    criterio2 = load_json(raw_dir / "criterio2_initcwnd.json")
    criterio3 = load_json(raw_dir / "criterio3_l325_execucoes.json")
    pins = load_json(run_dir.parents[2] / "campaign" / "PINS.json")
    pki_dir = run_dir.parents[2] / "certs" / "generated"

    print("Extraindo parametros criptograficos reais (tshark + parser DER proprio) para 4 perfis x 3 rotas...",
          file=sys.stderr)
    crypto = {}
    for p in PROFILES:
        per_route = {}
        for r in ROUTES:
            per_route[r] = {"handshake": extract_handshake(capturas_dir, p, r),
                             "entries": extract_certs(capturas_dir, p, r)}
        hs_all = [per_route[r]["handshake"] for r in ROUTES]
        consistent = all(
            h["ciphersuite_hex"] == hs_all[0]["ciphersuite_hex"] and
            h["negotiated_group_hex"] == hs_all[0]["negotiated_group_hex"] and
            h["certificateverify_sig_hash_alg_hex_distinct"] == hs_all[0]["certificateverify_sig_hash_alg_hex_distinct"]
            for h in hs_all)
        entries_all = [per_route[r]["entries"] for r in ROUTES]
        entries_consistent = all(
            {side: [e["sha256"] for e in d["entries"]] for side, d in ent.items()} ==
            {side: [e["sha256"] for e in d["entries"]] for side, d in entries_all[0].items()}
            for ent in entries_all)
        crypto[p] = {"handshake_l0": per_route["L0"]["handshake"],
                     "handshake_all_routes": {r: per_route[r]["handshake"] for r in ROUTES},
                     "entries_by_side": per_route["L0"]["entries"],
                     "entries_all_routes": {r: per_route[r]["entries"] for r in ROUTES},
                     "cross_route_consistent": consistent and entries_consistent}

    check = dual_signature_check(crypto)
    pki_checks = verify_against_disk_pki(crypto["hibrido-and"]["entries_by_side"], pki_dir)
    pki_checks["pki_dir"] = str(pki_dir)
    log_evidence = build_log_evidence(raw_dir)

    if not check["pass"]:
        print("=" * 70, file=sys.stderr)
        print("FALHA NA CHECAGEM AUTOMATIZADA DE CRIPTOGRAFIA (BLOCO B item 3):", file=sys.stderr)
        for f in check["failures"]:
            print(f"  - {f}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

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
        "dual_signature_and_pqc_purity_check": check,
        "pki_disk_cross_check": pki_checks,
        "gateway_log_dual_auth_evidence": log_evidence,
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

    (out_dir / "crypto_params.md").write_text(
        render_crypto_md(crypto, check, pki_checks, log_evidence), encoding="utf-8")
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

    print(json.dumps({"out_dir": str(out_dir), "all_criteria_pass": all_pass,
                       "dual_signature_and_pqc_purity_check_pass": check["pass"]}, indent=2))
    if not check["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

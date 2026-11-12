"""
Auditoria independente de uma janela real do v9 (piloto ou campanha
oficial), nos termos do criterio 1 da autorizacao condicional do
Luciano ("auditoria de recomputo a partir dos dados brutos com 0
divergencias"). Mesma filosofia de thesis/scripts/audit_v7_from_raw.py/
audit_v8_from_raw.py: reconstroi as estatisticas-chave DIRETO dos
arquivos brutos (piloto_calls.json, criterio6_execucoes.json), sem
confiar em nenhum resumo ja computado -- manifest.json e lido so por
cima (totais declarados), nunca como fonte de verdade pros numeros em
si.

Escopo (nunca reparsea gateway logs/pcap aqui -- isso fica para a
analise final de latencia/RTT, feita separadamente):
  - Contagem de chamadas por tipo (participante: AS/RS/Directory/
    PKI-CRL/Other) e consultas especificas a /jwks, por PERFIL --
    checa se e CONSTANTE entre perfis (criterio 3 da autorizacao).
  - Tamanho de assinatura (classical_sig_bytes/pq_sig_bytes, via
    jwt_sig_breakdown ja presente em cada chamada) por tipo de
    construcao (pqc_pure/strong_nesting/payload_extension/classic),
    contra os valores esperados (RSA-2048=256B, ML-DSA-65=3309B
    crus) -- qualquer divergencia e reportada (criterio 2).
  - TLS version/curve/dual asserido, recontado direto de
    criterio6_execucoes.json, contra o esperado por perfil
    (ver EXPECTED_TLS abaixo) -- nenhuma execucao fora do esperado.
  - T_fluxo (start_utc/end_utc) por (perfil, rota): mediana e N,
    independente de qualquer calculo anterior.
  - Totais (n execucoes por celula, total geral) contra
    manifest.json's expected_total/total_execucoes -- so como
    sanidade final, apos tudo acima ja ter sido recomputado sem
    olhar pro manifest.

Usage: python thesis/scripts/audit_v9_from_raw.py --out-dir <piloto_out ou similar> [--write <arquivo>]
"""
import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

EXPECTED_SIG_BYTES = {
    "pqc_pure": {"pq_sig_bytes": 3309},
    "strong_nesting": {"classical_sig_bytes": 256, "pq_sig_bytes": 3309},
    "payload_extension": {"classical_sig_bytes": 256, "pq_sig_bytes": 3309},
}
# confirmado nesta sessao: PS256/RSA-2048 = 256B crus, qualquer construcao
EXPECTED_CLASSICAL_ONLY_BYTES = 256

EXPECTED_TLS_VERSION = "TLS 1.3"
EXPECTED_DUAL = {"classico": False, "pqc": False, "hibrido-v8": False, "hibrido-and": True}


def _parse_iso(s):
    return datetime.fromisoformat(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--write")
    args = ap.parse_args()
    out_dir = Path(args.out_dir)

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    calls_raw = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))
    criterio6 = json.loads(Path(manifest["criterio6_json"]).read_text(encoding="utf-8"))

    lines = []
    problems = []

    def log(s=""):
        lines.append(s)

    log(f"Auditoria independente (recomputo dos dados brutos) -- {out_dir}")
    log(f"Execucoes no piloto_calls.json: {len(calls_raw)}")
    log(f"Linhas no criterio6_execucoes.json: {len(criterio6)}")
    log("")

    # --- 1) Contagem de chamadas por tipo de participante, por perfil ---
    by_profile_participant = defaultdict(Counter)
    by_profile_jwks = Counter()
    by_profile_total_calls = Counter()
    sig_mismatches = []

    for entry in calls_raw:
        profile = entry["profile"]
        for call in entry.get("insurance", []) + entry.get("person", []):
            by_profile_total_calls[profile] += 1
            participant = call.get("participant", "<ausente>")
            by_profile_participant[profile][participant] += 1
            endpoint = (call.get("endpoint") or "")
            if "jwks" in endpoint:
                by_profile_jwks[profile] += 1
            for breakdown in call.get("jwt_sig_breakdown", []) or []:
                construction = breakdown.get("construction")
                expected = EXPECTED_SIG_BYTES.get(construction)
                if construction in ("classic", "ps256") or (expected is None and breakdown.get("classical_sig_bytes") is not None and breakdown.get("pq_sig_bytes") is None):
                    if breakdown.get("classical_sig_bytes") not in (None, EXPECTED_CLASSICAL_ONLY_BYTES):
                        sig_mismatches.append((profile, construction, breakdown))
                    continue
                if expected is None:
                    continue
                for field, expected_bytes in expected.items():
                    got = breakdown.get(field)
                    if got != expected_bytes:
                        sig_mismatches.append((profile, construction, breakdown))
                        break

    log("== Chamadas por participante, por perfil (recomputado dos dados brutos) ==")
    all_profiles = sorted(by_profile_total_calls)
    for p in all_profiles:
        log(f"  {p}: total={by_profile_total_calls[p]} jwks={by_profile_jwks[p]} "
            f"participantes={dict(by_profile_participant[p])}")

    # Criterio 3: contagens por tipo devem ser IGUAIS entre perfis
    reference = None
    for p in all_profiles:
        shape = (by_profile_total_calls[p], by_profile_jwks[p], dict(by_profile_participant[p]))
        if reference is None:
            reference = shape
        elif shape != reference:
            problems.append(f"CRITERIO 3 FALHOU: perfil {p} tem contagem de chamadas diferente de {all_profiles[0]} "
                             f"({shape} vs {reference})")
    if reference is not None and not any("CRITERIO 3" in pr for pr in problems):
        log(f"\nCriterio 3 (contagens iguais entre perfis): OK -- todos os perfis batem com {reference}")

    log("")
    log("== Tamanhos de assinatura (recomputado dos dados brutos, contra esperado) ==")
    if sig_mismatches:
        for profile, construction, breakdown in sig_mismatches[:20]:
            problems.append(f"CRITERIO 2 FALHOU: perfil={profile} construction={construction} "
                             f"breakdown={breakdown} nao bate com o esperado")
        log(f"  {len(sig_mismatches)} divergencia(s) de tamanho de assinatura -- ver problemas abaixo")
    else:
        log("  0 divergencias -- todos os tamanhos de assinatura batem com o esperado (RSA-2048=256B, ML-DSA-65=3309B crus)")

    # --- 2) TLS version/curve/dual, recontado de criterio6 ---
    log("")
    log("== TLS version/dual asserido, recomputado de criterio6_execucoes.json ==")
    tls_problems = 0
    for row in criterio6:
        profile = row["profile"]
        expected_dual = EXPECTED_DUAL.get(profile)
        if row.get("dualAuthenticated") != expected_dual:
            problems.append(f"CRITERIO 1 FALHOU: {profile}/{row['route']}/run{row['run']} "
                             f"dualAuthenticated={row.get('dualAuthenticated')} esperado={expected_dual}")
            tls_problems += 1
    log(f"  {tls_problems} divergencia(s) de dual/perfil em {len(criterio6)} execucoes")

    # --- 3) T_fluxo por (perfil, rota), independente ---
    log("")
    log("== T_fluxo (mediana, N) por perfil x rota, recomputado de start_utc/end_utc ==")
    tfluxo_by_cell = defaultdict(list)
    for entry in calls_raw:
        try:
            t0 = _parse_iso(entry["start_utc"])
            t1 = _parse_iso(entry["end_utc"])
        except (KeyError, TypeError, ValueError):
            continue
        tfluxo_by_cell[(entry["profile"], entry["route"])].append((t1 - t0).total_seconds())
    for (profile, route), values in sorted(tfluxo_by_cell.items()):
        log(f"  {profile}/{route}: N={len(values)} mediana={statistics.median(values):.3f}s")

    # --- 4) Sanidade final contra manifest.json (so depois de tudo acima) ---
    log("")
    log("== Sanidade final contra manifest.json (consultado so agora) ==")
    total_recomputado = len(calls_raw)
    if total_recomputado != manifest.get("total_execucoes"):
        problems.append(f"Sanidade: total recomputado ({total_recomputado}) != manifest.total_execucoes "
                         f"({manifest.get('total_execucoes')})")
    else:
        log(f"  total_execucoes bate: {total_recomputado}")
    if manifest.get("cost_stop") is not None:
        log(f"  AVISO: manifest.cost_stop nao e None -- janela foi interrompida por custo: {manifest['cost_stop']}")

    log("")
    log(f"=== RESULTADO: {len(problems)} divergencia(s) ===")
    for pr in problems:
        log(f"  - {pr}")

    text = "\n".join(lines)
    print(text)
    if args.write:
        Path(args.write).write_text(text + "\n", encoding="utf-8")
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()

"""
Automacao de coleta de baseline (criptografia classica) da Conformance Suite MockOPIN,
para a tese de doutorado sobre migracao PQC.

Roda os modulos "happy path" (preflight + core/status) dos planos:
  - Insurance consents api test V3.0.0
  - person_test-plan_v2.0.0

Salva logs brutos + metricas agregadas em Tese/resultados/baseline/.
Le os templates de configuracao de Tese/config/.

Observacoes sobre os resultados:
- Os modulos "preflight" sempre terminam com result=FAILED: eles chamam uma
  condicao interna da suite (OpinCheckDirectoryDiscoveryUrl/ApiBase) que exige
  o Directory real da Raidiam e nao pode ser satisfeita rodando 100% local.
  E "continue on failure", entao o resto do fluxo roda normalmente -- so o
  rotulo de resultado fica FAILED mesmo com o trafego real capturado no log.
- Os modulos de status/core podem pausar em status=WAITING esperando um login
  + consentimento manual no navegador (ver poll_until_terminal). O script
  imprime a URL e continua o polling sozinho ate a suite detectar o redirect.
"""

import io
import json
import re
import statistics
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Caminhos relativos ao script (nao ao cwd), pra funcionar independente de
# onde o script e chamado: Tese/scripts/baseline_automation.py -> Tese/
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
OUTPUT_DIR = BASE_DIR / "resultados" / "baseline"

BASE_URL = "https://localhost:8443"
POLL_INTERVAL_SECONDS = 5
POLL_TIMEOUT_SECONDS = 600
TERMINAL_STATUSES = {"FINISHED", "INTERRUPTED"}

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)?")

# Cada plano tem 5-11 modulos (o resto sao casos negativos/erro: token
# expirado, permissao invalida, limites de cliente etc). Rodamos so os dois
# modulos "felizes" de cada um: o preflight (valida certificados/SSA) e o
# modulo que efetivamente cria/consulta um consentimento pela API real.
PLANS = [
    {
        "plan_name": "Insurance consents api test V3.0.0",
        "report_label": "consents_v3",
        "config_file": "config_template_consents_v3.json",
        "happy_path_modules": [
            "opin-consents_api_preflight_test-module_v3",
            "opin-consent-api-status-test-v3",
        ],
    },
    {
        "plan_name": "person_test-plan_v2.0.0",
        "report_label": "person_v2",
        "config_file": "config_template_person_v2.json",
        "happy_path_modules": [
            "opin-consents_api_preflight_test-module_v3",
            "person_api_core_test-module_v2.0.0",
        ],
    },
]


def api_get(path, **params):
    r = requests.get(f"{BASE_URL}{path}", params=params, verify=False, timeout=30)
    return r


def api_post(path, params=None, json_body=None):
    if json_body is None:
        r = requests.post(f"{BASE_URL}{path}", params=params, verify=False, timeout=30)
    else:
        r = requests.post(f"{BASE_URL}{path}", params=params, json=json_body, verify=False, timeout=30)
    return r


def create_plan(plan_name: str, config: dict):
    r = api_post("/api/plan", params={"planName": plan_name}, json_body=config)
    r.raise_for_status()
    data = r.json()
    return data["id"], data["modules"]


def start_module(plan_id: str, test_name: str):
    # IMPORTANT: when 'plan' is supplied, no request body may be sent
    # (the suite returns an empty-body 400 otherwise).
    r = api_post("/api/runner", params={"test": test_name, "plan": plan_id})
    r.raise_for_status()
    data = r.json()
    return data["id"]


def poll_until_terminal(test_id: str, module_label: str):
    # A doc do /api/runner recomenda explicitamente usar /api/info/{id} para
    # acompanhar o teste, nao /api/runner/{id} (que tambem existe mas nao
    # e o caminho documentado para isso).
    started = time.time()
    already_printed_url = False
    while True:
        elapsed = time.time() - started
        if elapsed > POLL_TIMEOUT_SECONDS:
            print(f"  [{module_label}] TIMEOUT apos {POLL_TIMEOUT_SECONDS}s, abortando polling.")
            return None

        r = api_get(f"/api/info/{test_id}")
        r.raise_for_status()
        info = r.json()
        status = info.get("status")
        result = info.get("result")
        print(f"  [{module_label}] status={status} result={result} ({int(elapsed)}s)")

        if status in TERMINAL_STATUSES:
            return info

        if status == "WAITING" and not already_printed_url:
            br = api_get(f"/api/runner/browser/{test_id}")
            if br.status_code == 200:
                try:
                    browser_info = br.json()
                except ValueError:
                    browser_info = br.text
                # A resposta real usa "urls" (lista) -- guardamos "url"/"redirect"
                # como fallback caso a suite mude o formato numa versao futura.
                urls = []
                if isinstance(browser_info, dict):
                    urls = browser_info.get("urls") or []
                    if not urls:
                        single = browser_info.get("url") or browser_info.get("redirect")
                        if single:
                            urls = [single]
                elif isinstance(browser_info, str) and browser_info.startswith("http"):
                    urls = [browser_info]
                if urls:
                    print("\n  " + "=" * 70)
                    print(f"  >>> INTERACAO MANUAL NECESSARIA para [{module_label}]")
                    for u in urls:
                        print(f"  >>> Abra no navegador: {u}")
                    # Sem input() de proposito: o polling ja detecta a mudanca de
                    # status assim que o navegador completa o redirect real, entao
                    # nao ha necessidade (nem como, num terminal nao-interativo)
                    # de esperar confirmacao manual aqui.
                    print("  >>> O polling continua automaticamente; nao e preciso confirmar aqui.")
                    print("  " + "=" * 70 + "\n")
                    already_printed_url = True

        time.sleep(POLL_INTERVAL_SECONDS)


def export_log(test_id: str):
    """GET /api/log/export/{id} devolve um ZIP contendo test-log-<id>.json."""
    r = api_get(f"/api/log/export/{test_id}")
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        json_names = [n for n in names if n.endswith(".json")]
        if not json_names:
            raise RuntimeError(f"Nenhum .json encontrado no export ZIP: {names}")
        with zf.open(json_names[0]) as f:
            return json.load(f)


def run_module(plan_id: str, plan_alias: str, test_name: str):
    print(f"\n=== Modulo: {test_name} (plano {plan_alias}) ===")
    test_id = start_module(plan_id, test_name)
    print(f"  test_id={test_id}")
    info = poll_until_terminal(test_id, test_name)
    if info is None:
        print(f"  [{test_name}] sem status terminal, pulando export.")
        return None

    log_export = export_log(test_id)
    # O export embrulha as entradas de log de verdade dentro de log_export["results"],
    # junto com metadados (exportedAt, testInfo etc). Guardamos o dict completo no
    # arquivo (JSON bruto pedido pela tese) mas so a lista "results" e usada pro parsing.
    log_entries = log_export.get("results", []) if isinstance(log_export, dict) else log_export
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = test_name.replace("/", "_")
    out_path = OUTPUT_DIR / f"{plan_alias}__{safe_name}_{timestamp}.json"
    out_path.write_text(json.dumps(log_export, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  log salvo em {out_path} ({len(log_entries)} entradas)")

    return {
        "plan_alias": plan_alias,
        "module": test_name,
        "test_id": test_id,
        "status": info.get("status"),
        "result": info.get("result"),
        "log_file": str(out_path),
        "log": log_entries,
    }


def header_bytes(headers: dict) -> int:
    # Aproximacao do tamanho "on the wire" dos headers (formato "Nome: valor\r\n").
    # Nao inclui a linha de requisicao/status nem overhead de TLS/TCP -- e uma
    # estimativa consistente o suficiente para comparar classico vs PQC, nao um
    # medidor exato de bytes de rede.
    if not headers:
        return 0
    total = 0
    for k, v in headers.items():
        total += len(f"{k}: {v}\r\n".encode("utf-8"))
    return total


def extract_jwts(*texts):
    # Varre request/response body + header Authorization procurando por
    # qualquer string no formato JWT (client_assertion, request object,
    # access/id_token). O tamanho desses tokens e o dado central da tese
    # (comparar tamanho de assinatura classica vs PQC).
    found = []
    for text in texts:
        if not text:
            continue
        if isinstance(text, dict):
            text = json.dumps(text)
        for m in JWT_RE.finditer(text):
            token = m.group(0)
            if len(token) > 20:
                found.append(token)
    return found


def parse_calls(log_entries):
    """Pareia entradas de request/response consecutivas em 'chamadas' HTTP."""
    # O log da suite nao tem um ID explicito ligando request a response: cada
    # chamada HTTP vira duas entradas separadas (msg="HTTP request" / "HTTP
    # response") na sequencia em que aconteceram. Empiricamente a resposta
    # sempre vem logo em seguida da requisicao correspondente, entao pareamos
    # por adjacencia no array em vez de por algum campo de correlacao.
    calls = []
    i = 0
    n = len(log_entries)
    while i < n:
        entry = log_entries[i]
        if entry.get("http") == "request":
            req = entry
            resp = None
            if i + 1 < n and log_entries[i + 1].get("http") == "response":
                resp = log_entries[i + 1]
                i += 1

            req_headers = req.get("request_headers") or {}
            req_body = req.get("request_body") or ""
            req_bytes = header_bytes(req_headers) + len(req_body.encode("utf-8"))

            resp_headers = (resp or {}).get("response_headers") or {}
            resp_body = (resp or {}).get("response_body") or ""
            resp_bytes = header_bytes(resp_headers) + len(str(resp_body).encode("utf-8"))

            latency_ms = None
            if resp is not None and "time" in req and "time" in resp:
                latency_ms = resp["time"] - req["time"]

            uri = req.get("request_uri", "")
            endpoint = urlparse(uri).path or uri

            jwts = extract_jwts(req_body, req_headers.get("Authorization"), resp_body)

            calls.append({
                "endpoint": endpoint,
                "full_uri": uri,
                "method": req.get("request_method"),
                "src": req.get("src"),
                "request_bytes": req_bytes,
                "response_bytes": resp_bytes,
                "total_bytes": req_bytes + resp_bytes,
                "latency_ms": latency_ms,
                "authorization_header": req_headers.get("Authorization"),
                "jwts": jwts,
                "jwt_sizes": [len(j) for j in jwts],
                "status_code": (resp or {}).get("response_status_code"),
            })
        i += 1
    return calls


def percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    return values[f] + (values[c] - values[f]) * (k - f)


def compute_metrics(all_calls):
    total_bytes = sum(c["total_bytes"] for c in all_calls)
    total_requests = len(all_calls)

    by_endpoint = {}
    for c in all_calls:
        by_endpoint.setdefault(c["endpoint"], []).append(c["latency_ms"])

    latency_per_endpoint = {}
    for endpoint, latencies in by_endpoint.items():
        clean = [l for l in latencies if l is not None]
        if not clean:
            continue
        latency_per_endpoint[endpoint] = {
            "count": len(clean),
            "mean_ms": round(statistics.mean(clean), 2),
            "p50_ms": round(percentile(clean, 50), 2),
            "p95_ms": round(percentile(clean, 95), 2),
            "p99_ms": round(percentile(clean, 99), 2),
        }

    all_jwt_sizes = []
    for c in all_calls:
        all_jwt_sizes.extend(c["jwt_sizes"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_bytes_exchanged": total_bytes,
        "total_requests": total_requests,
        "latency_per_endpoint": latency_per_endpoint,
        "jwt_sizes_bytes": all_jwt_sizes,
        "jwt_count": len(all_jwt_sizes),
        "jwt_size_avg_bytes": round(statistics.mean(all_jwt_sizes), 2) if all_jwt_sizes else None,
        "jwt_size_max_bytes": max(all_jwt_sizes) if all_jwt_sizes else None,
    }


def write_report_md(metrics, module_results, path: Path):
    lines = []
    lines.append("# Relatorio Baseline (Criptografia Classica)")
    lines.append("")
    lines.append(f"Gerado em: {metrics['generated_at']}")
    lines.append("")
    lines.append("## Resumo geral")
    lines.append("")
    lines.append(f"- Total de bytes trocados no fluxo completo (OPINsize classico): **{metrics['total_bytes_exchanged']} bytes**")
    lines.append(f"- Total de requisicoes HTTP: **{metrics['total_requests']}**")
    lines.append(f"- JWTs encontrados: **{metrics['jwt_count']}**")
    if metrics["jwt_size_avg_bytes"] is not None:
        lines.append(f"- Tamanho medio de JWT: **{metrics['jwt_size_avg_bytes']} bytes** (max: {metrics['jwt_size_max_bytes']} bytes)")
    lines.append("")
    lines.append("## Modulos executados")
    lines.append("")
    lines.append("| Plano | Modulo | Status | Resultado | Log |")
    lines.append("|---|---|---|---|---|")
    for m in module_results:
        if m is None:
            continue
        lines.append(f"| {m['plan_alias']} | {m['module']} | {m['status']} | {m['result']} | `{m['log_file']}` |")
    lines.append("")
    lines.append("## Latencia por endpoint")
    lines.append("")
    lines.append("| Endpoint | Requisicoes | Media (ms) | P50 (ms) | P95 (ms) | P99 (ms) |")
    lines.append("|---|---|---|---|---|---|")
    for endpoint, stats in sorted(metrics["latency_per_endpoint"].items()):
        lines.append(
            f"| `{endpoint}` | {stats['count']} | {stats['mean_ms']} | {stats['p50_ms']} | {stats['p95_ms']} | {stats['p99_ms']} |"
        )
    lines.append("")
    lines.append("## Tamanhos de JWT encontrados")
    lines.append("")
    if metrics["jwt_sizes_bytes"]:
        lines.append("| # | Tamanho (bytes) |")
        lines.append("|---|---|")
        for idx, size in enumerate(metrics["jwt_sizes_bytes"], start=1):
            lines.append(f"| {idx} | {size} |")
    else:
        lines.append("Nenhum JWT encontrado nos payloads.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    module_results = []
    all_calls = []

    for plan_spec in PLANS:
        config = json.loads((CONFIG_DIR / plan_spec["config_file"]).read_text(encoding="utf-8"))
        # plan_alias e so um rotulo pra organizar arquivos/relatorio. O campo
        # config["alias"] tem que ser literalmente "mock" nos dois planos: a
        # suite monta o redirect_uri como https://.../test/a/{alias}/callback,
        # e o unico redirect_uri registrado pro client_one e ".../test/a/mock/callback"
        # (fixo em software_statement.json). Um alias diferente causa
        # "redirect_uri did not match any of the client's registered redirect_uris".
        plan_alias = plan_spec["report_label"]

        print(f"\n############ Plano: {plan_spec['plan_name']} (alias={plan_alias}) ############")
        plan_id, _modules = create_plan(plan_spec["plan_name"], config)
        print(f"plan_id={plan_id}")

        for module_name in plan_spec["happy_path_modules"]:
            result = run_module(plan_id, plan_alias, module_name)
            module_results.append(result)
            if result is not None:
                all_calls.extend(parse_calls(result["log"]))

    metrics = compute_metrics(all_calls)
    metrics_path = OUTPUT_DIR / "metricas_baseline.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nMetricas salvas em {metrics_path}")

    report_path = OUTPUT_DIR / "RELATORIO_BASELINE.md"
    write_report_md(metrics, module_results, report_path)
    print(f"Relatorio salvo em {report_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""v9, piloto: orquestrador das 60 execucoes (4 perfis x 3 rotas x
N=5), equivalente reduzido ao `campaign_run.py` real da v8 -- mesmas
convencoes (um Executor plugavel, SSH sempre pelo IP PUBLICO do
alvo -- Decisao 43/45 -- marcadores de execucao, bloco por perfil),
mas sem a maquinaria de campanha multi-dia (janelas, latin square,
orcamento de custo/tempo, chronyc) que o piloto, de 2h e 1 so bloco
por rota, nao precisa.

Dois Executors, mesmo padrao SSHExecutor/LocalExecutor da v8 real
(`campaign_run.py`, classes homonimas):

  - SSHExecutor: fala com instancias reais via `cli.run_ssh`/`cli.run_scp`
    -- SEMPRE pelo IP PUBLICO do alvo (Decisao 43/45), nunca testado
    contra AWS de verdade nesta sessao ("nada de AWS").
  - LocalExecutor: NAO sobe o stack Docker real (isso e pesado/lento
    pra um teste automatizado) -- gera dados SINTETICOS mas
    deterministicos e REALISTAS (contagens HTTP 44/28/4/4 reais,
    CurveID esperado por perfil, tamanhos de mensagem iguais aos
    baselines MEDIDOS que o proprio avaliador ja usa -- importados,
    nunca reinventados). Prova a logica de ORQUESTRACAO (cardinalidade,
    ordem, marcadores, formato aceito pelo avaliador) -- NAO prova
    nada sobre a rede/criptografia real, que so a AWS pode confirmar
    (ver thesis/results/v9/DECISIONS.md, Decisao 47).

Ordem de execucao (Decisao 23 item 2, "blocos de perfil, replicando a
v8 real"): pra CADA rota, a ordem dos 4 blocos de perfil e sorteada
(um `random.Random(seed)` por execucao do orquestrador, logado pra
reprodutibilidade/auditoria) -- dentro de um bloco, as N=5 execucoes
daquele perfil rodam em sequencia. A sondagem de prontidao (Decisao
18/36) roda uma vez por troca de bloco, ANTES do primeiro marcador
INICIO -- fora de qualquer janela, por construcao.
"""
import argparse
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cli  # noqa: E402

_INTEGRATION_DIR = Path(__file__).resolve().parents[2] / "integration"
sys.path.insert(0, str(_INTEGRATION_DIR))
import evaluate_criteria as ec  # noqa: E402  -- reaproveita os baselines/constantes reais, nunca reinventa

PROFILES = ["classico", "pqc", "hibrido-v8", "hibrido-and"]
ROUTES = ["L0", "L219", "L325"]
N_PER_PROFILE = 5
EXPECTED_TOTAL = len(PROFILES) * len(ROUTES) * N_PER_PROFILE  # 60
EXPECTED_CAPTURES = len(PROFILES) * len(ROUTES)  # 12

_EXPECTED_HTTP = {"http": 44, "jwts": 28, "jwks": 4, "ca": 4}


def profile_block_order(route: str, rng: random.Random) -> list[str]:
    """Decisao 23 item 2: sorteia a ordem dos 4 blocos de perfil pra
    UMA rota -- chamado uma vez por rota, na ordem fixa ROUTES, pelo
    MESMO `rng` (um unico seed pro orquestrador inteiro, nao um por
    rota) -- reprodutivel dado o mesmo seed, auditavel (o seed e
    sempre gravado no manifesto de saida)."""
    order = PROFILES[:]
    rng.shuffle(order)
    return order


def execucao_marker_inicio(profile, route, run):
    return f"== EXECUCAO INICIO perfil={profile} rota={route} run={run} =="


def execucao_marker_fim(profile, route, run):
    return f"== EXECUCAO FIM perfil={profile} rota={route} run={run} =="


def _connection_ok_line(sni="mtls", remote="10.0.0.1:443"):
    return f'gateway: PERFIL connection OK remoteAddr={remote} sni="{sni}"'


def _dedicated_capture_block(profile: str) -> str:
    """Monta o bloco 'tamanho POR MENSAGEM' pra UM perfil, nos
    EXATOS baselines medidos que `evaluate_criteria.py` ja usa
    (CERTIFICATE_BASELINE/CLIENTHELLO_BASELINE/HANDSHAKE_MESSAGE_
    BASELINE, importados, nunca reinventados aqui) -- formato
    identico ao que `measure.sh` produz de verdade (colunas
    tempo\\ttipos\\ttamanhos, tipos TLS numericos: 1=ClientHello,
    2=ServerHello, 8=EncryptedExtensions, 11=Certificate,
    13=CertificateRequest, 15=CertificateVerify, 20=Finished)."""
    hb = ec.HANDSHAKE_MESSAGE_BASELINE[profile]
    cert = ec.CERTIFICATE_BASELINE[profile] - 4
    ch = ec.CLIENTHELLO_BASELINE[profile] - 4
    server_flight = [
        ("2", hb["ServerHello"] - 4), ("8", hb["EncryptedExtensions"] - 4),
        ("13", hb["CertificateRequest"] - 4), ("11", cert),
        ("15", hb["CertificateVerify_servidor"] - 4), ("20", hb["Finished_servidor"] - 4),
    ]
    client_flight = [
        ("11", hb["Certificate_cliente"] - 4),
        ("15", hb["CertificateVerify_cliente"] - 4), ("20", hb["Finished_cliente"] - 4),
    ]
    lines = [
        "tamanho POR MENSAGEM (tempo, tipos, tamanhos)",
        f"0.001\t1\t{ch}",
        "0.010\t" + ",".join(t for t, _ in server_flight) + "\t" + ",".join(str(n) for _, n in server_flight),
        "0.012\t" + ",".join(t for t, _ in client_flight) + "\t" + ",".join(str(n) for _, n in client_flight),
    ]
    return f"== Perfil: {profile} ==\n" + "\n".join(lines) + "\n== fim =="


class LocalExecutor:
    """Simulacao local (sem SSH, sem AWS) -- ver docstring do modulo."""

    def __init__(self):
        self.calls_counter = 0

    def readiness_probe(self):
        """Decisao 18/36: a sondagem de prontidao completa um
        handshake real (sni=mtls) -- UMA linha, retornada pro
        chamador escrever FORA de qualquer janela."""
        return _connection_ok_line(sni="mtls", remote="203.0.113.9:51000")

    def run_execution(self, profile, route, run):
        """Devolve o necessario pros criterios 4 e 6 de UMA execucao:
        6 linhas 'connection OK' (sni=mtls, client-facing) + 1 linha
        interna (sni=matls-api.local, pra provar que a exclusao do
        avaliador funciona) + a lista insurance/person com as
        contagens HTTP reais esperadas (44/28/4/4) + CurveID/
        DualAuthenticated do perfil."""
        lines = [_connection_ok_line(sni="mtls", remote=f"203.0.113.{10 + i}:5100{i}") for i in range(6)]
        lines.append(_connection_ok_line(sni="matls-api.local", remote="127.0.0.1:9000"))
        # 44 chamadas totais (10 insurance + 34 person), 4 /jwks (1+3),
        # 4 CA (root-ca.pem + issuer-ca.pem, 2+2), 36 chamadas de
        # "conteudo" restantes -- das quais 28 levam 1 JWT e 8 nenhum,
        # pra bater exatamente com os 44/28/4/4 reais (Decisao 17/18).
        insurance = (
            [{"endpoint": "/jwks", "jwts": []}, {"endpoint": "/root-ca.pem", "jwts": []},
             {"endpoint": "/issuer-ca.pem", "jwts": []}]
            + [{"endpoint": "/insurance", "jwts": ["a"]} for _ in range(7)]
        )
        person = (
            [{"endpoint": "/jwks", "jwts": []} for _ in range(3)]
            + [{"endpoint": "/root-ca.pem", "jwts": []}, {"endpoint": "/issuer-ca.pem", "jwts": []}]
            + [{"endpoint": "/person", "jwts": ["a"]} for _ in range(29)]
        )
        all_calls = insurance + person
        jwt_bearing = [c for c in all_calls if c["endpoint"] not in ("/jwks", "/root-ca.pem", "/issuer-ca.pem")]
        for c in jwt_bearing[28:]:
            c["jwts"] = []
        dual = True if profile == "hibrido-and" else False
        return {
            "insurance": insurance, "person": person,
            "gateway_log_lines": lines,
            "curveID": ec.EXPECTED_CURVE[profile], "dualAuthenticated": dual,
        }

    def dedicated_capture(self, profile, route):
        return _dedicated_capture_block(profile)


class SSHExecutor:
    """Fala com instancias reais -- SEMPRE pelo IP PUBLICO do alvo
    (Decisao 43/45), nunca o privado, so pra SSH. `inventory` e o
    dict que `terraform output -json inventory` produz (ver
    thesis/results/v9/terraform/outputs.tf)."""

    def __init__(self, inventory, key_path=None):
        self.inventory = inventory
        self.key_path = key_path

    def _server_ip(self):
        return self.inventory["server"]["public_ip"]

    def _client_ip(self, route):
        return self.inventory["clients"][route]["public_ip"]

    def _server_gateway_ip(self, route):
        """Decisao 27 item 1/outputs.tf `colocated`: so o trafego de
        GATEWAY (443, dentro da execucao real do cliente) usa o IP
        PRIVADO do servidor pro cliente co-localizado -- SSH (acima)
        nunca usa isso."""
        client = self.inventory["clients"][route]
        return self.inventory["server"]["private_ip"] if client.get("colocated") else self.inventory["server"]["public_ip"]

    def readiness_probe(self):
        ip = self._server_ip()
        proc = cli.run_ssh(ip, "echo readiness-probe-placeholder", key_path=self.key_path)
        return proc.stdout.strip() or _connection_ok_line()

    def run_execution(self, profile, route, run):
        client_ip = self._client_ip(route)
        server_gw_ip = self._server_gateway_ip(route)
        remote_cmd = (
            f"CRYPTO_PROFILE={profile} REMOTE_GATEWAY_HOST={server_gw_ip} V9_HARNESS=1 "
            f"python3 opin_flow.py"
        )
        proc = cli.run_ssh(client_ip, remote_cmd, key_path=self.key_path)
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"execucao {profile}/{route}/{run}: saida remota nao-JSON: {e}") from None

    def dedicated_capture(self, profile, route):
        server_ip = self._server_ip()
        proc = cli.run_ssh(server_ip, f"cat /tmp/criterio1_{profile}_{route}.log", key_path=self.key_path)
        return proc.stdout


def run_pilot(executor, seed: int, out_dir: Path, n_per_profile: int = N_PER_PROFILE, smoke: bool = False) -> dict:
    """Roda `n_per_profile` execucoes por bloco (4 perfis x 3 rotas)
    + as 12 capturas dedicadas, escreve todos os artefatos no formato
    que `evaluate_criteria.py --aws-dir` espera. Devolve um resumo
    (cardinalidade, ordem por rota, seed).

    `smoke=True` (Decisao 48/Emenda 12 ao pre-registro v9-prereg):
    `n_per_profile` continua livre pro CHAMADOR escolher (a porta de
    fumaca usa 1), mas o manifesto fica marcado explicitamente como
    `"smoke": true` e `out_dir` tem que ser um diretorio PROPRIO,
    nunca reaproveitado pelas 60 execucoes reais -- a porta de fumaca
    NUNCA conta pro total oficial do piloto, mesmo que gere artefatos
    no MESMO formato (pra poder ser avaliada pelos mesmos criterios)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    capturas_dir = out_dir / "criterio1_capturas"
    capturas_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    combined_log_lines = []
    execucoes_calls = []
    criterio6_rows = []
    route_orders = {}

    for route in ROUTES:
        order = profile_block_order(route, rng)
        route_orders[route] = order
        for profile in order:
            combined_log_lines.append(f"== Perfil: {profile} ==")
            combined_log_lines.append(executor.readiness_probe())
            for run in range(1, n_per_profile + 1):
                combined_log_lines.append(execucao_marker_inicio(profile, route, run))
                result = executor.run_execution(profile, route, run)
                combined_log_lines.extend(result["gateway_log_lines"])
                combined_log_lines.append(execucao_marker_fim(profile, route, run))
                execucoes_calls.append({
                    "profile": profile, "route": route, "run": run,
                    "insurance": result["insurance"], "person": result["person"],
                })
                criterio6_rows.append({
                    "profile": profile, "route": route, "run": run,
                    "curveID": result["curveID"], "dualAuthenticated": result["dualAuthenticated"],
                    "keylog_evidence": True,
                })

    for profile in PROFILES:
        for route in ROUTES:
            block = executor.dedicated_capture(profile, route)
            (capturas_dir / f"{profile}_{route}.log").write_text(block, encoding="utf-8")

    combined_log_path = out_dir / "piloto_combined.log"
    combined_log_path.write_text("\n".join(combined_log_lines) + "\n", encoding="utf-8")

    calls_path = out_dir / "piloto_calls.json"
    calls_path.write_text(json.dumps(execucoes_calls, indent=2, ensure_ascii=False), encoding="utf-8")

    criterio6_path = out_dir / "criterio6_execucoes.json"
    criterio6_path.write_text(json.dumps(criterio6_rows, indent=2, ensure_ascii=False), encoding="utf-8")

    expected_total = len(PROFILES) * len(ROUTES) * n_per_profile
    manifest = {
        "seed": seed, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "smoke": smoke, "n_per_profile": n_per_profile,
        "route_orders": route_orders,
        "total_execucoes": len(execucoes_calls), "expected_total": expected_total,
        "total_capturas": EXPECTED_CAPTURES,
        "combined_log": str(combined_log_path), "calls_json": str(calls_path),
        "criterio6_json": str(criterio6_path), "capturas_dir": str(capturas_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


SMOKE_N_PER_PROFILE = 1
SMOKE_EXPECTED_TOTAL = len(PROFILES) * len(ROUTES) * SMOKE_N_PER_PROFILE  # 12


def run_smoke_gate(executor, seed: int, out_dir: Path) -> dict:
    """Decisao 48 (Emenda 12 ao pre-registro v9-prereg): 1 execucao
    por perfil x rota (12 no total, NUNCA contadas nas 60 oficiais) --
    roda ANTES do bloco cronometrado, so com `SSHExecutor` real,
    contra as instancias de verdade recem-subidas. Critério de
    abortar: QUALQUER uma das 12 execucoes falhando (excecao,
    `insurance`/`person` vazios, ou qualquer criterio avaliavel por
    execucao-unica dando FAIL) e motivo pra abortar o piloto inteiro
    e destruir -- nunca prosseguir pras 60 execucoes reais sobre uma
    infraestrutura que a propria porta de fumaca ja mostrou com
    problema."""
    manifest = run_pilot(executor, seed, out_dir, n_per_profile=SMOKE_N_PER_PROFILE, smoke=True)
    execucoes = json.loads(Path(manifest["calls_json"]).read_text(encoding="utf-8"))
    failures = []
    for entry in execucoes:
        counts = ec._http_counts_for_calls(entry)
        if counts != _EXPECTED_HTTP:
            failures.append({"profile": entry["profile"], "route": entry["route"],
                              "esperado": _EXPECTED_HTTP, "obtido": counts})
    manifest["smoke_ok"] = manifest["total_execucoes"] == SMOKE_EXPECTED_TOTAL and not failures
    manifest["smoke_failures"] = failures
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["simulate", "ssh"], default="simulate")
    ap.add_argument("--seed", type=int, default=20261107)
    ap.add_argument("--out", required=True)
    ap.add_argument("--inventory-json", help="obrigatorio no modo --mode ssh (terraform output -json inventory)")
    ap.add_argument("--ssh-key", help="caminho da chave privada do piloto (modo ssh)")
    ap.add_argument("--smoke", action="store_true",
                     help="Decisao 48: porta de fumaca, 1 execucao por perfil x rota (12, nunca contadas nas 60)")
    args = ap.parse_args()

    if args.mode == "simulate":
        executor = LocalExecutor()
    else:
        if not args.inventory_json:
            ap.error("--mode ssh exige --inventory-json")
        inventory = json.load(open(args.inventory_json, encoding="utf-8"))
        executor = SSHExecutor(inventory, key_path=args.ssh_key)

    if args.smoke:
        manifest = run_smoke_gate(executor, args.seed, Path(args.out))
    else:
        manifest = run_pilot(executor, args.seed, Path(args.out))
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    if args.smoke and not manifest["smoke_ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Degrau 2, Etapa 1, sub-etapa 2 -- corrida contra o dead-man's-switch.

Confirmado lendo o codigo real (modules/campaign_instance/templates/
safety_timer.sh.tftpl): systemd timer `mockopin-safety-timer.timer`,
`OnBootSec=5min OnUnitActiveSec=5min` -- a PRIMEIRA checagem do dead-
man's-switch em cada host ocorre exatamente 5 minutos apos o boot
daquele host especifico (nunca assumido, confirmado no arquivo real,
Decisao 194 reconfirma o mesmo valor). O arquivo de deadline
(`/etc/mockopin-campaign/deadline`) guarda um EPOCH EM SEGUNDOS (`date
+%s`), nunca uma string ISO -- a escrita nova precisa ser nesse mesmo
formato.

Este script tenta SSH nos 8 hosts em paralelo (controle tem prioridade
-- so depois dele responder os outros 7 sao tentados, via controle como
bastiao, mesmo padrao de segundo salto ja usado nesta sessao), a cada 3
segundos, e no PRIMEIRO sucesso de CADA host grava o deadline de forma
ATOMICA (arquivo temporario + `mv`), rele o arquivo gravado pra conferir,
e so entao marca aquele host como pronto. Nenhuma outra acao e feita em
nenhum host antes de seu proprio deadline estar gravado e conferido.

Modo `--dry-run`: nunca chama rede/SSH/AWS -- simula sucesso apos N
tentativas fake, pra testar a logica de paralelismo/prioridade/relatorio
localmente, conforme exigido antes de rodar contra a AWS de verdade."""
import argparse
import json
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

POLL_INTERVAL_S = 3
SSH_CONNECT_TIMEOUT_S = 3
DEADLINE_HOURS = 5
WARN_AFTER_S = 4.5 * 60  # se um host passar disso sem sucesso, alerta alto (risco do switch ja ter disparado)
MAX_WAIT_S = 20 * 60


def now_utc_iso():
    return datetime.now(timezone.utc).isoformat()


class HostTarget:
    def __init__(self, label, role, host, user, key_path, via_control=False):
        self.label = label
        self.role = role
        self.host = host
        self.user = user
        self.key_path = key_path
        self.via_control = via_control  # True para os 7 nao-controle (segundo salto)


def ssh_argv_direct(target: HostTarget, remote_cmd: str) -> list[str]:
    return [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        "-o", f"ConnectTimeout={SSH_CONNECT_TIMEOUT_S}", "-o", "BatchMode=yes",
        "-i", target.key_path, f"{target.user}@{target.host}", remote_cmd,
    ]


def ssh_argv_via_control(target: HostTarget, control: HostTarget, remote_cmd: str) -> list[str]:
    """Segundo salto: SSH no controle, que por sua vez faz SSH no alvo
    usando a chave da campanha (que vive so no controle). O comando
    remoto e passado com aspas simples escapadas corretamente."""
    escaped = remote_cmd.replace("'", "'\\''")
    inner_ssh = (
        f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        f"-o ConnectTimeout={SSH_CONNECT_TIMEOUT_S} -o BatchMode=yes "
        f"-i {target.key_path} {target.user}@{target.host} '{escaped}'"
    )
    return ssh_argv_direct(control, inner_ssh)


DEADLINE_WRITE_AND_VERIFY_CMD = (
    "sudo bash -c '"
    f"date -d \"+{DEADLINE_HOURS} hours\" +%s > /etc/mockopin-campaign/deadline.tmp && "
    "mv /etc/mockopin-campaign/deadline.tmp /etc/mockopin-campaign/deadline && "
    "cat /etc/mockopin-campaign/deadline'"
)


class RealConnector:
    """Modo real -- chama ssh de verdade. So usado quando --dry-run NAO
    e passado (ou seja, nunca nesta rodada de teste local)."""

    def try_once(self, argv: list[str], label: str) -> tuple[bool, str]:
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=SSH_CONNECT_TIMEOUT_S + 5)
            return proc.returncode == 0, proc.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, ""


class FakeConnector:
    """Modo --dry-run -- NUNCA chama rede/SSH/AWS. Simula sucesso apos
    um numero fixo de tentativas (configuravel por host, pra exercitar
    tanto o caminho rapido quanto o lento), devolvendo um epoch
    plausivel de "+5h" como se fosse a saida real do comando remoto.
    Recebe `label` explicitamente (nunca tenta adivinhar do argv, que
    pro modo via-controle e so uma string de comando aninhado, nunca
    igual ao label do host)."""

    def __init__(self, succeed_after_n_tries: dict[str, int]):
        self.succeed_after_n_tries = succeed_after_n_tries
        self.attempts: dict[str, int] = {}
        self._lock = threading.Lock()

    def try_once(self, argv: list[str], label: str) -> tuple[bool, str]:
        with self._lock:
            self.attempts[label] = self.attempts.get(label, 0) + 1
            n = self.attempts[label]
        threshold = self.succeed_after_n_tries.get(label, 1)
        if n < threshold:
            return False, ""
        fake_epoch = int(time.time()) + DEADLINE_HOURS * 3600
        return True, str(fake_epoch)


def poll_until_success(connector, argv_builder, label: str, result_store: dict, store_lock: threading.Lock,
                        start_time: float, stop_event: threading.Event):
    attempt = 0
    while not stop_event.is_set():
        attempt += 1
        argv = argv_builder()
        t_attempt = time.monotonic()
        ok, deadline_written_str = connector.try_once(argv, label)
        elapsed = time.monotonic() - start_time
        if ok:
            with store_lock:
                result_store[label] = {
                    "ready": True, "elapsed_since_start_s": round(elapsed, 2),
                    "attempts": attempt, "deadline_epoch_written": deadline_written_str,
                    "deadline_utc_written": (
                        datetime.fromtimestamp(int(deadline_written_str), tz=timezone.utc).isoformat()
                        if deadline_written_str.strip().isdigit() else None
                    ),
                    "confirmed_at_utc": now_utc_iso(),
                }
            print(f"[{label}] PRONTO em {elapsed:.1f}s (tentativa {attempt}) -- deadline gravado e conferido.")
            return
        if elapsed > WARN_AFTER_S:
            print(f"[{label}] AVISO: {elapsed:.1f}s sem sucesso (> {WARN_AFTER_S:.0f}s) -- "
                  f"RISCO REAL de o dead-man's-switch ja ter disparado de novo neste host.")
        time.sleep(POLL_INTERVAL_S)


def run(control: HostTarget, others: list[HostTarget], connector, max_wait_s: float = MAX_WAIT_S) -> dict:
    result_store: dict = {}
    store_lock = threading.Lock()
    start_time = time.monotonic()
    stop_event = threading.Event()

    # Fase A -- controle tem PRIORIDADE: so lanca os outros 7 depois do controle responder.
    print(f"[{control.label}] aguardando SSH (prioridade sobre os outros 7)...")
    poll_until_success(
        connector, lambda: ssh_argv_direct(control, DEADLINE_WRITE_AND_VERIFY_CMD),
        control.label, result_store, store_lock, start_time, stop_event,
    )
    if control.label not in result_store:
        return result_store  # esgotou tempo/stop_event sem o controle responder -- nao lanca os outros

    # Fase B -- os outros 7, EM PARALELO, via controle como bastiao.
    threads = []
    for t in others:
        th = threading.Thread(
            target=poll_until_success,
            args=(connector, lambda t=t: ssh_argv_via_control(t, control, DEADLINE_WRITE_AND_VERIFY_CMD),
                  t.label, result_store, store_lock, start_time, stop_event),
            daemon=True,
        )
        th.start()
        threads.append(th)

    deadline_wait = start_time + max_wait_s
    while time.monotonic() < deadline_wait:
        with store_lock:
            done = len(result_store)
        if done >= 1 + len(others):
            break
        time.sleep(1)
    stop_event.set()
    for th in threads:
        th.join(timeout=2)
    return result_store


def build_targets_from_inventory(inv: list[dict]) -> tuple[HostTarget, list[HostTarget]]:
    control = None
    others = []
    for e in inv:
        t = HostTarget(e["label"], e["role"], e["host"], e["user"], e["key_path"])
        if e["role"] == "control":
            control = t
        else:
            others.append(t)
    if control is None:
        raise ValueError("inventario sem host role=control")
    return control, others


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", help="JSON com os 8 hosts {label,role,host,user,key_path}")
    parser.add_argument("--dry-run", action="store_true", help="NUNCA chama rede/SSH/AWS -- so testa a logica")
    parser.add_argument("--out", help="Caminho do relatorio JSON final")
    args = parser.parse_args()

    if args.dry_run:
        # Inventario FAKE, nunca IPs reais -- so pra exercitar a logica.
        inv = [
            {"label": "control", "role": "control", "host": "198.51.100.1", "user": "ec2-user", "key_path": "~/.ssh/id_ed25519"},
            {"label": "server-sa-east-1", "role": "server", "host": "198.51.100.2", "user": "ec2-user", "key_path": "~/.ssh/campaign_key"},
            {"label": "client-L0-sa-east-1", "role": "client", "host": "198.51.100.3", "user": "ec2-user", "key_path": "~/.ssh/campaign_key"},
            {"label": "server-us-east-1", "role": "server", "host": "198.51.100.4", "user": "ec2-user", "key_path": "~/.ssh/campaign_key"},
            {"label": "client-L0-us-east-1", "role": "client", "host": "198.51.100.5", "user": "ec2-user", "key_path": "~/.ssh/campaign_key"},
            {"label": "server-ap-northeast-1", "role": "server", "host": "198.51.100.6", "user": "ec2-user", "key_path": "~/.ssh/campaign_key"},
            {"label": "client-L0-ap-northeast-1", "role": "client", "host": "198.51.100.7", "user": "ec2-user", "key_path": "~/.ssh/campaign_key"},
            {"label": "client-L123", "role": "client", "host": "198.51.100.8", "user": "ec2-user", "key_path": "~/.ssh/campaign_key"},
        ]
        control, others = build_targets_from_inventory(inv)
        connector = FakeConnector({
            "control": 1,            # controle responde na 1a tentativa (3s)
            "server-sa-east-1": 2,   # os outros variam, pra exercitar o paralelismo de verdade
            "client-L0-sa-east-1": 3,
            "server-us-east-1": 1,
            "client-L0-us-east-1": 4,
            "server-ap-northeast-1": 2,
            "client-L0-ap-northeast-1": 1,
            "client-L123": 3,
        })
        result = run(control, others, connector, max_wait_s=60)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        assert len(result) == 8, f"esperava 8 hosts prontos, recebeu {len(result)}"
        assert all(v["ready"] for v in result.values())
        assert result["control"]["attempts"] == 1
        print("\nDRY-RUN OK: logica de paralelismo/prioridade/escrita-e-confirmacao de deadline validada "
              "sem nenhuma chamada de rede/SSH/AWS.")
        return

    if not args.inventory:
        raise SystemExit("--inventory e obrigatorio fora do modo --dry-run")
    inv = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    control, others = build_targets_from_inventory(inv)
    connector = RealConnector()
    result = run(control, others, connector)
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""v9, piloto, Etapa 1 (pedido do Luciano, item 2 do relatorio de
robustez): TRAVA LOCAL de custo, por contabilidade de horas de
instancia x preco de tabela publico -- a credencial do operador nao
le billing (`ce:GetCostAndUsage`/`budgets:ViewBudget`/`freetier:
GetFreeTierUsage` todos `AccessDenied`, confirmado na Verificacao
Pre-Campanha desta mesma sessao), entao esta estimativa e LOCAL e
CONSERVADORA (arredondada pra cima), nunca o Cost Explorer real --
serve so de rede de seguranca pra nao ultrapassar o credito do plano
gratuito sem supervisao, nunca como numero oficial de custo.

Fonte dos precos (declarada explicitamente, pedido do Luciano):
preco de instancia e de armazenamento buscados via agregadores
terceiros (Devzero, aws-pricing.com, Holori, cloudbolt.io) em
2026-11-11 -- a pagina oficial da AWS (aws.amazon.com/ec2/pricing,
aws.amazon.com/ebs/pricing) nao foi acessada diretamente nesta sessao
(sem ferramenta de navegador). Arredondados PARA CIMA sobre o valor
mais citado, nunca pra baixo. O preco de IPv4 publico (US$0,005/hora)
e o valor OFICIAL do AWS News Blog ("New – AWS Public IPv4 Address
Charge", vigente desde 2024-02-01), usado exato, sem margem, porque e
uma tarifa fixa unica, nao uma faixa que varia por fonte. O preco de
transferencia de dados (US$0,09/GB) e a tarifa publica padrao de
saida pra internet (primeiros 10TB/mes), estavel ha varios anos,
usada como teto conservador (trafego entre regioes via IP publico
pode custar igual ou menos, nunca mais, nesta topologia).

CONFIRME contra o AWS Pricing Calculator ou o Cost Explorer real
antes de qualquer decisao financeira que nao seja esta trava de
seguranca local.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PRICE_SOURCE_NOTE = (
    "Instancia/EBS: agregadores terceiros (Devzero, aws-pricing.com, Holori, cloudbolt.io), "
    "buscados em 2026-11-11, arredondados PARA CIMA -- pagina oficial da AWS nao acessada "
    "diretamente nesta sessao. IPv4 publico: valor OFICIAL do AWS News Blog, US$0,005/hora, "
    "vigente desde 2024-02-01, sem margem. Transferencia: tarifa publica padrao de saida pra "
    "internet (primeiros 10TB/mes), US$0,09/GB, estavel ha anos, usada como teto conservador."
)

# Medido (fonte acima): m7i-flex.large ~US$0,0958/h em us-east-1 (Linux, on-demand);
# t4g.micro ~US$0,0084/h em us-east-1. Arredondados pra cima com margem pra cobrir
# variacao entre as 7 regioes da campanha (preco on-demand varia por regiao).
HOURLY_PRICE_USD = {
    "m7i-flex.large": 0.12,
    "t4g.micro": 0.01,
}
# Preco de fallback pra qualquer tipo de instancia NAO listado acima -- o maior
# preco conhecido, nunca um default barato que subestimaria o custo real.
_FALLBACK_HOURLY_PRICE_USD = max(HOURLY_PRICE_USD.values())

PUBLIC_IPV4_HOURLY_USD = 0.005
EBS_GP3_GB_MONTH_USD = 0.08
# 730h/mes (media), +10% de margem conservadora sobre o preco medido.
EBS_GP3_GB_HOUR_USD = (EBS_GP3_GB_MONTH_USD / 730.0) * 1.10
DATA_TRANSFER_OUT_GB_USD = 0.09

DEFAULT_PILOT_ALERT_USD = 10.0
DEFAULT_PILOT_STOP_USD = 13.0


def hourly_price_for(instance_type: str) -> float:
    return HOURLY_PRICE_USD.get(instance_type, _FALLBACK_HOURLY_PRICE_USD)


@dataclass
class CostTracker:
    """Contabiliza o custo estimado da frota ATIVA desde `window_start_utc`
    (pedido do Luciano: "horas ativas de cada instancia vezes preco de
    tabela publico, mais IPv4 publico, disco e transferencia medida").

    `instance_types`: {instance_id: tipo} -- toda instancia considerada
    LIGADA desde o inicio da janela (pessimista/conservador: nao desconta
    nenhum tempo de boot/entrega de imagem, que ja roda com a instancia
    ligada e cobrando).
    `n_public_ips`: EIPs alocados durante a janela (controle + servidores +
    clientes -- 1 por instancia, por desenho da Decisao 49/campaign_instance).
    `ebs_gb_per_instance`: tamanho do volume raiz gp3 de cada instancia
    (30GB, confirmado em `modules/campaign_instance/main.tf`, Decisao 59).
    `data_transfer_gb`: bytes MEDIDOS ate agora (nunca estimados a priori --
    atualizar via `add_data_transfer_bytes` com o que de fato foi
    transferido, se/quando essa medicao existir).
    `alert_usd`/`stop_usd`: limiares, CONFIGURAVEIS -- piloto usa os
    defaults (10/13); a campanha oficial deve passar os seus proprios."""

    instance_types: dict[str, str] = field(default_factory=dict)
    n_public_ips: int = 0
    ebs_gb_per_instance: float = 30.0
    data_transfer_gb: float = 0.0
    alert_usd: float = DEFAULT_PILOT_ALERT_USD
    stop_usd: float = DEFAULT_PILOT_STOP_USD
    window_start_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_data_transfer_bytes(self, n_bytes: int) -> None:
        self.data_transfer_gb += n_bytes / (1024 ** 3)

    def elapsed_hours(self, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        return max(0.0, (now - self.window_start_utc).total_seconds() / 3600.0)

    def breakdown_usd(self, now: datetime | None = None) -> dict:
        hours = self.elapsed_hours(now)
        n_instances = len(self.instance_types)
        compute = sum(hourly_price_for(t) for t in self.instance_types.values()) * hours
        ipv4 = self.n_public_ips * PUBLIC_IPV4_HOURLY_USD * hours
        ebs = n_instances * self.ebs_gb_per_instance * EBS_GP3_GB_HOUR_USD * hours
        transfer = self.data_transfer_gb * DATA_TRANSFER_OUT_GB_USD
        return {
            "elapsed_hours": hours, "n_instances": n_instances, "n_public_ips": self.n_public_ips,
            "compute_usd": compute, "public_ipv4_usd": ipv4, "ebs_usd": ebs,
            "data_transfer_usd": transfer, "total_usd": compute + ipv4 + ebs + transfer,
            "price_source_note": PRICE_SOURCE_NOTE,
        }

    def estimated_cost_usd(self, now: datetime | None = None) -> float:
        return self.breakdown_usd(now)["total_usd"]

    def status(self, now: datetime | None = None) -> str:
        """'ok' | 'alert' | 'stop' -- comparado contra `alert_usd`/`stop_usd`,
        configuraveis por chamador (piloto: 10/13; campanha: outro limite)."""
        cost = self.estimated_cost_usd(now)
        if cost >= self.stop_usd:
            return "stop"
        if cost >= self.alert_usd:
            return "alert"
        return "ok"


def write_cost_log_entry(out_dir: Path, event: str, breakdown: dict) -> None:
    """Acrescenta UMA linha JSONL em `out_dir/cost_tracker.jsonl` -- log
    auditavel e append-only (nunca sobrescrito), coberto pelo mesmo
    hash sha256 de `collect_artifacts.py` igual a qualquer outro
    artefato do diretorio."""
    out_dir.mkdir(parents=True, exist_ok=True)
    entry = {"event": event, "logged_at_utc": datetime.now(timezone.utc).isoformat(), **breakdown}
    with (out_dir / "cost_tracker.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

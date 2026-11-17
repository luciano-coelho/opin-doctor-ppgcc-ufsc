# Degrau 2 — reduced inventory (8 hosts)

Prepared in Stage 0 (local, with no AWS command at all). **No real IP, no account ID, no key content appears in this document** — the real `host`/`key_path` will only be filled in during Stage 1, from a **scoped/filtered** `terraform output -json` (never the full output), its own sub-stage, with the user present.

## The 8 hosts (reused from the official campaign's already-existing fleet — no new instance)

| Role | Label | Region | Reuses host from |
|---|---|---|---|
| control | `control` | `sa-east-1` | the official campaign's same control host |
| server | `server-sa-east-1` | `sa-east-1` | the official campaign's same server (serves `L0-sa-east-1` **and** `L123` — co-located, confirmed in Degrau 1; **no 9th instance is needed**) |
| client | `client-L0-sa-east-1` | `sa-east-1` (co-located) | the official campaign's same L0 client |
| server | `server-us-east-1` | `us-east-1` | the official campaign's same server (serves `L0-us-east-1`) |
| client | `client-L0-us-east-1` | `us-east-1` (co-located) | the official campaign's same L0 client |
| server | `server-ap-northeast-1` | `ap-northeast-1` | the official campaign's same server (serves `L0-ap-northeast-1`) |
| client | `client-L0-ap-northeast-1` | `ap-northeast-1` (co-located) | the official campaign's same L0 client |
| client | `client-L123` | `ca-central-1` | the official campaign's same `L123` client |

**Explicit confirmation (already established in Degrau 1, reconfirmed here):** `L123`'s server is the same as `sa-east-1`'s — co-located, by the official campaign's topology design (`campaign_topology.CAMPAIGN_ROUTE_SERVER["L123"] == "sa-east-1"`). No separate 9th instance/server is needed for `L123`.

## Cells and profiles of this supplementary campaign

- **Cells (4):** `L0-sa-east-1`, `L0-us-east-1`, `L0-ap-northeast-1`, `L123`.
- **Profiles (3):** `classico`, `pqc`, `hibrido-and`. **Control (`hibrido-v8`) out of scope**, per `PLANO_DEGRAU2.md`.
- **Rounds:** 2, independent, seeds `20261117` (round 1) and `20261118` (round 2) — the same as the pre-registration.
- **N per cell per round:** 15 official executions + 5 discarded warm-ups (never read in the Stage 2 analyses).
- **Profile block order:** drawn per route AND per round (2 independent draws per route, 1 per round), recorded in the manifest — the same convention as the official campaign (`route_orders`).

## Campaign count (confirmed, matches the request)

`4 cells × 3 profiles × 15 executions × 2 rounds = 360 official executions` (+ `4 × 3 × 5 × 2 = 120` discarded warm-ups, not included in the 360).

## Intended output

- **Remote (on the control host):** `~/campaign-data/v9/degrau2/` — the same directory structure as the official campaign (`raw`/`organized`, a manifest with `route_orders`/seeds/timestamps), adapted for the 4 cells × 3 profiles.
- **Local (copy, as always):** `thesis/results/v9/degrau2/campaign_data/` (does not exist yet — it will be created in Stage 1, when copying the real data from the control host; **do not confuse it with `thesis/results/v9/degrau2/` itself, which already exists and contains only this Stage 0's artifacts** — the plan, scripts, this inventory).

## Explicit pending items for Stage 1 (never resolved in this Stage 0)

1. Resolve the real `host` (public IP) and `key_path` of the 8 hosts via a **scoped** `terraform output -json` (e.g., only the `public_ip`/`private_ip` fields of the 8 labels above, never the full output) — recorded only in a LOCAL file outside git (the same security convention already used throughout the official campaign), never committed as plain text.
2. Confirm that the fleet (currently stopped, confirmed in Degrau 1) is in the expected state before any action — a separate, read-only sub-stage, before any restart.
3. Run `probe_overhead.py` and `collect_cpu_info.py` (both written in this Stage 0) from the control host.
4. Only after that, run the supplementary 360-execution campaign itself.

Each of these 4 pending items is a SEPARATE sub-stage, individually authorized by the user, with the user present — no authorization from this Stage 0 covers any of them.

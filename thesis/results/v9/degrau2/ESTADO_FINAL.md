# Degrau 2 — final state of this session

Updated at approximately `2026-11-17T11:30Z`. Replaces the previous checkpoint (below, kept as history) — Stage 2 has been completed.

## What has been done so far

1. **Critical finding (Decision 212):** the 2 original Degrau 2 rounds (`tentativa1_sem_campo_fino/`) contained no `t_fluxo_fino_seconds`/`phase_accounting` in any record — a serialization bug in `orchestrator.py` (second layer, `execucao_entry`/`aquecimento_entry`, never touched by the original additive change). Fixed locally (commit `fe532c9e`), with no action on AWS.
2. **Smoke test:** passed fully (1 execution + 1 warm-up, the complete path through to disk, all fields present and non-null).
3. **Safety gate (gate_watcher.py):** implemented, runs in parallel on each round, checks the first real `run01.json`. **Passed on both rounds** (`ok: true`), never aborted anything.
4. **Full round 3 — repeat of the pre-registered plan with the fixed code:**
   - Round1 (seed `20261117`): 180/180 executions, 60/60 warm-ups, exit code 0, cost ~US$2,86. 2/12 dedicated captures failed (category "incomplete decryption", non-fatal, self-handled).
   - Round2 (seed `20261118`): 180/180 executions, 60/60 warm-ups, exit code 0, cost ~US$2,77. **12/12 dedicated captures failed** — the same textual/structural category ("incomplete decryption after 3 attempts", never "size mismatch"), a uniform pattern across the 3 attempts in all 12 inspected cells — **but with a much higher failure rate than Round 1 (100% vs 17%), suggesting a systemic cause tied to Round 2's window, not per-execution randomness. This does NOT affect `t_fluxo_fino_seconds`/`phase_accounting` (Degrau 2's central fields) — it is an orthogonal failure, in criterion 1 (certificate-size verification via dedicated TLS capture), not in the fine-grained timer.** Recorded as a finding to investigate separately, it does not block D1-D5.
   - No other type of failure (transport, signature, unhandled Traceback) in either round.
   - Total Round 3 cost: **~US$5,63** (well under the US$12 limit).

## Current state confirmed now (re-verified from scratch, not assumed)

- **Processes:** no `orchestrator.py`/`gate_watcher.py` active on the control host (`pgrep` clean); `launch_persistent.py status` confirms `alive: false` for both rounds.
- **Fleet:** the 8 required hosts are `running` (confirmed via a read-only `describe-instances`, 4 regions). **No `stop-instances`/`terminate-instances` was run at any point in this session.**
- **Deadline:** ~0,96h (58min) remaining on the 8 hosts, counting with no renewal since the end of Round 2 (the orchestrator's heartbeat stops when the process ends).

## What was completed after this checkpoint

- **Data collection:** Round 1 -- 376 files verified by sha256; Round 2 -- 346 files verified by sha256 (`collect_artifacts.py`).
- **Required-field verification:** across the 480 real records (360 executions + 120 warm-ups) -- 0 problems. `t_fluxo_fino_seconds`, the 6 `phase_accounting` components, `start_utc`/`end_utc`, `insurance[].latency_ms` present in 100% of the files.
- **Deadline shortened** to `2026-11-17T11:24:49Z` (now+10min) on the 8 hosts, atomic write with confirmation read -- the fleet shuts itself down via the dead-man's switch. No `stop-instances`/`terminate-instances` called.
- **Stage 2 completed:** the 7 analyses (D1, D2, D2b, D3, D4a, D4b, D5) run per `PLANO_DEGRAU2.md` + Amendment 1, without changing criteria/tests/seeds/aggregation rules. The two-round rule applied first -- 0/28 divergences, pooling allowed in all analyses. Full result: `RELATORIO_ETAPA2_D1_D5.md` (draft for review, not final/published) + `ETAPA2_RESULTADOS.json` (all the numbers).
  - **Summary of verdicts:** D1 SUPPORTED, D2 REFUTED (small margin on the slope), D3 SUPPORTED (but the L0-sa-east-1 inversion does NOT persist in the fine-grained T_fluxo), D4a REFUTED, D4b PARTIAL, D5 SUPPORTED.
- **Independent audit** (a separate agent, which never read a key file) found 1 high-severity finding (undeclared denominator in D4a/D4b) and other minor ones -- all fixed before this report was treated as ready for review (no final verdict changed, only supporting numbers). Full detail of the fixes: its own section in `RELATORIO_ETAPA2_D1_D5.md`.
- Everything committed locally (no push, no force, no moving tags) -- commits `42a3b175` (Round 3 + data) and the commit for this Stage 2.

**Fleet confirmed `stopped` on the 8 hosts** (a read-only `describe-instances` check, 4 regions, done ~11min after the deadline) -- all with `Reason: "User initiated"` (the dead-man's switch runs `shutdown -h now` inside the guest, never an AWS API stop/terminate call). **No `stop-instances`/`terminate-instances` was called at any point in this session.**

## What now depends on the user

Review `RELATORIO_ETAPA2_D1_D5.md` -- it is a draft, explicitly marked as not final. Decide whether to separately investigate the finding of the 100% dedicated-capture failure rate in Round 2 (it blocks nothing, but is a real, unexplained finding).

# Attempt 1 — Rounds 1 and 2 of Degrau 2, without the fine-grained field (archived)

Real data from the first two rounds of the supplementary campaign (seeds `20261117`/`20261118`, 360 executions + 120 warm-ups, 0 failures, collected and sha256-verified). **Do not delete, do not mix with data from future rounds.**

**Cause:** Stage 0's additive change (commit `02b1fa9d`) only touched the return dict of `run_execution()` in `orchestrator.py`. A second serialization layer inside `run_pilot()` (`aquecimento_entry`/`execucao_entry` -- the dicts that actually persist to disk) had its own fixed key list, which never included `t_fluxo_fino_seconds`/`phase_accounting`, silently discarding them. Full detail: `thesis/results/v9/DECISIONS.md`, Decision 212.

**Impact:** none of the 480 records here contains the fine-grained T_fluxo or `phase_accounting`. The 7 analyses (D1, D2, D2b, D3, D4a, D4b, D5) in `PLANO_DEGRAU2.md` + Amendment 1 depend on at least one of these two fields -- none can be done with this data. All the WALL-CLOCK fields (`start_utc`/`end_utc`/`insurance`/`cpu_*`/etc.) remain valid and intact -- only the 2 new fields are missing.

**Fix:** `orchestrator.py` was fixed in the same commit where this finding was recorded (`fe532c9e`) -- `aquecimento_entry`/`execucao_entry` now pass through the 2 keys. Round 3 (data in `thesis/results/v9/degrau2/campaign_data/`, outside this archive directory) repeats the same plan with the fixed code.

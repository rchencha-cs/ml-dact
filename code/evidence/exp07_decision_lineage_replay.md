# EXP-07 — Decision-Lineage Replay

**Experiment ID:** `EXP-07`
**Git commit:** `026e7f7`
**Raw artifact:** `evidence/exp07_replay.json`
**Environment:** fresh, isolated `docker compose` stack (postgres/mlflow/backend only),
on host ports 5477/5027/8167 — deliberately **not** the pre-existing `dact-local-eks-control-plane`
kind cluster also present on this machine, which was left completely untouched.

## Protocol

1. Added `policy_version`/`threshold_config_version` provenance columns to `EvaluationResult`,
   and a new `JointDecision` table persisting the Section 8.4 trigger decision (previously only
   a free-text audit-log line) — see commit `aae2df0`.
2. Brought up a fresh stack (`docker compose down -v && up postgres mlflow backend`), which ran
   the standard 5-scenario seed (`healthy`, `feature_drift`, `volume_anomaly`, `label_imbalance`,
   `regression`) for `churn-predictor`.
3. Exercised `POST /api/v1/models/{model}/joint-retrain` for all 5 churn scenarios × 2 seeds
   (42, 777), and `POST /api/v1/electricity/joint-retrain` for all 5 Electricity folds (0–4),
   persisting one `JointDecision` row per call.
4. Ran `scripts/exp07_replay.py`, which independently reconstructs each persisted
   `JointDecision` and `EvaluationResult` row and replays it through the **real**
   `app.ml.policy.decide_trigger_state` / `should_retrain` and `app.ml.gates.evaluation_gate`
   functions (the same ones EXP-06 unit-tests), then checks the replayed action equals the
   recorded action.

## Result

| Metric | Value |
|---|---:|
| Total decisions replayed | 23 |
| Matched | **23** |
| Mismatched | 0 |
| JointDecision rows (RETAIN/EVALUATE/RETRAIN) | 15 |
| EvaluationResult rows (PROMOTE/REJECT) | 8 |

All three trigger states (RETAIN, EVALUATE, RETRAIN) and both gate outcomes (PASS, FAIL)
are represented in the replayed set — not just the easy cases. Full per-decision detail
in `evidence/exp07_replay.json`.

## Acceptance criterion

"Replay must reproduce the original decision" — met: 23/23 (100%).

## Disclosed scope limitation

Rollback (`RollbackEvent`) is **not** included in this replay. In this codebase, rollback is
a manually/externally triggered action (`pipeline_engine.rollback`, called by an operator or a
simulated-regression script), not the output of an automated "should we roll back" policy —
there is nothing to replay a *decision* against, only deterministic state-transition mechanics,
which EXP-06 already covers with dedicated tests (`test_failed_promoted_candidate_triggers_rollback`,
etc.). This is reported rather than papered over, per the PRD's no-fabrication rule.

## Separate finding: provenance columns are schema-additive, not migratable

`Base.metadata.create_all()` (this project has no Alembic) only creates missing tables; it
cannot add new columns to a pre-existing table. The pre-existing `dact-local-eks-control-plane`
cluster's Postgres (30 historical runs from earlier research scripts, dated ~2026-09-07 to
09-09) therefore cannot receive `policy_version`/`threshold_config_version` without either a
manual `ALTER TABLE` or a fresh reseed — it was left untouched for this experiment rather than
risking that cluster. A future EXP-05 pass should decide whether to backfill it.

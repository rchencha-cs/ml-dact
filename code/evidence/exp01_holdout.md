# EXP-01 — Independent Post-Selection Holdout

**Experiment ID:** `EXP-01`
**Raw artifact:** `evidence/exp01_holdout.json`
**Scope:** the churn-predictor PyTorch pipeline (paper Section 7.1's primary protocol).
Electricity is out of scope — it is already labeled exploratory/transferability (EXP-04),
not the primary confirmatory evaluation this holdout protects.

## Method

Per the PRD's own ordering (`Training data → Candidate generation → Controller-facing
evaluation → MEDP decision → Freeze policy decision → Independent final holdout`),
every candidate's promotion/rejection decision was already frozen (from the seeded
stack run used in EXP-07) **before** this holdout was generated or scored.

1. **Reserved holdout seeds** — `backend/app/data_generator.py::generate_holdout()`
   uses one fixed seed per scenario (900001–900005), hardcoded, and marks every
   row `"holdout"` (never `train`/`val`/`test`). Grep-proof of separation:
   `generate_holdout`/`_HOLDOUT_SEEDS` appear **only** in `data_generator.py`
   (definition) and `scripts/exp01_holdout_eval.py` (consumer) — never in
   `seed.py`, `pipeline_engine.py`, any router, or any Airflow DAG.
2. For every historical `PipelineRun` that trained a PyTorch candidate (promoted
   or rejected), `scripts/exp01_holdout_eval.py` **deterministically reproduces**
   that exact candidate — same `dataset_seed`/`torch_seed`, derived only from the
   model name and run id already persisted in the DB — rather than relying on
   `champion_store` (which only ever saves weights for *promoted* candidates;
   rejected candidates' weights are not persisted anywhere in this codebase, so
   reproduction is the only way to score them at all).
3. The reproduction is sanity-checked against the real stored controller-facing
   F1 on `ModelVersion` before being trusted (see `reproduction_exactly_matches_stored_metrics`).
4. That exact model + threshold is then scored on `generate_holdout()`'s data —
   generated from a seed never seen during training, validation, thresholding, or
   the promotion decision — and the deltas are reported.

## Result

All 5 trained candidates from the seeded run reproduced their stored controller-facing
F1 exactly (`reproduction_exactly_matches_stored_metrics: true` for all 5); `volume_anomaly`
is correctly excluded (it never trains a candidate — blocked at the data-volume gate).

| Scenario | Version | Outcome | Controller-facing F1 | Final-holdout F1 | Δ F1 |
|---|---|---|---:|---:|---:|
| healthy | v1 | PROMOTED | 0.7843 | 0.7832 | −0.0011 |
| feature_drift | v2 | PROMOTED | 0.9584 | 0.9574 | −0.0011 |
| label_imbalance | v3 | MODEL_NOT_PROMOTED | 0.0000 | 0.3000 | **+0.3000** |
| regression | v4 | MODEL_NOT_PROMOTED | 0.7149 | 0.6957 | −0.0193 |
| healthy (post-rollback) | v5 | MODEL_NOT_PROMOTED | 0.8134 | 0.7770 | −0.0364 |

Full precision/recall/accuracy deltas in the raw JSON.

## Finding (reported as-is, not smoothed over)

`label_imbalance` (v3) shows the largest and only *positive* delta: controller-facing
F1 was 0.0000 (the tiny, ~2%-churn test split the candidate was scored on likely
contained too few positive examples for a stable F1), while the independent holdout
— drawn from the same label-imbalance generation process with a different seed —
produced F1 = 0.30. This is disclosed as evidence that single-split F1 under extreme
class imbalance is unstable, not as evidence the candidate was secretly better than
reported; both numbers come from the same frozen model, so neither is "wrong," they
simply reflect sampling variance at ~2% positive prevalence.

## Acceptance criteria

- [x] Holdout never reaches the controller — code path has zero overlap with
      ingestion/training/evaluation/promotion code (grep-verified above).
- [x] Holdout never influences thresholds — the decision threshold used against
      the holdout is the one already fixed from the val split, before the holdout
      was ever generated.
- [x] Holdout evaluated only after policy decisions are frozen — generated and
      scored after the seeded run's promotions/rejections already happened (EXP-07).
- [x] Code/configuration proves separation — see grep-proof above.

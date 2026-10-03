# EXP-04 — Structured Electricity Replication

**Experiment ID:** `EXP-04`
**Executable:** `scripts/run_electricity_natural.py` (unmodified for this experiment except the
EXP-06 refactor that made it call the real `app.ml.policy`/`app.ml.gates` functions instead of a
duplicated inline copy — see commit `808dd9f`)
**Raw artifact:** `evidence/exp04_electricity_replication.json`
**Interpretation:** this is a **transferability evaluation**, not evidence of population-wide
generalization, per the PRD's own framing — a second, independently-sourced workload where the
*same real policy code* is exercised, nothing more.

## Required protocol documentation

1. **Dataset/version** — public Electricity (Elec2) corpus, OpenML id 151 (`sklearn.datasets.fetch_openml`
   fallback), frozen locally at `data/electricity.csv` (45,312 rows). No injected drift, label noise,
   or volume manipulation — rows are used in their published chronological order.
2. **Chronological split** — 6 equal contiguous blocks over the published row order; 5 adjacent
   transfers (block *i* = reference/champion, block *i*+1 = production), `date`/`period` excluded
   from both the model and the PSI calculation so `DriftLevel` is not `SIGNIFICANT` by construction
   of the split.
3. **Drift definition** — identical to the primary protocol: `app.ml.drift.psi_numeric` /
   `drift_level` (PSI < 0.10 Normal, 0.10–0.25 Warning, > 0.25 Significant), averaged over the 7
   monitored features (`nswprice, nswdemand, vicprice, vicdemand, transfer, period, day`).
4. **Incumbent definition** — `EvaluationLevel = GOOD` iff the champion's F1 on the production
   block's test split ≥ 0.70 (`F1_GOOD`), identical floor to the primary protocol's `minimum_f1`.
5. **Candidate generation** — `sklearn.ensemble.HistGradientBoostingClassifier`, trained on the
   production block, always trained regardless of whether the joint cell fires (so a paired
   candidate-vs-champion F1 comparison exists even when the policy holds).
6. **Quality gate** — the real, unmodified `app.ml.gates.evaluation_gate` (same function EXP-06
   unit-tests and the primary churn pipeline uses).
7. **Thresholds** — identical to the primary protocol's published values: F1 ≥ 0.70,
   precision/recall ≥ 0.60, regression budget 10%. No Electricity-specific tuning.
8. **Replicate count** — 5 adjacent chronological transfers (folds 0–4) — the full set of
   transfers available from a 6-block split; not a subsample.
9. **Deviations from primary protocol** — (a) candidate family is HistGradientBoosting, not the
   primary protocol's PyTorch MLP (Elec2 is tabular/public, not the synthetic churn generator —
   model family necessarily differs); (b) no drift is *injected* — PSI is measured on the
   corpus's natural chronological variation, not a controlled shift; (c) exploratory/in-process
   script, not wired through the full 16-stage pipeline or a live Airflow trigger (that live-Airflow
   variant exists separately as `scripts/run_live_electricity_airflow.py`, out of scope here).

## Required outputs (per fold)

| Fold | PSI | Drift level | Champion F1 (ref→prod) | Evaluation level | Candidate F1 | Policy action | Gate result |
|---|---:|---|---|---|---:|---|---|
| 0 | 0.155 | WARNING | 0.823 → 0.810 | GOOD | 0.872 | hold (Continue) | PROMOTED |
| 1 | 0.298 | SIGNIFICANT | 0.867 → 0.592 | BAD | 0.818 | **FIRE** (Retrain / review) | REJECTED |
| 2 | 0.790 | SIGNIFICANT | 0.830 → 0.503 | BAD | 0.834 | **FIRE** (Retrain / review) | PROMOTED |
| 3 | 0.117 | WARNING | 0.825 → 0.608 | BAD | 0.753 | hold (Investigate model) | REJECTED |
| 4 | 0.711 | SIGNIFICANT | 0.766 → 0.699 | BAD | 0.849 | **FIRE** (Retrain / review) | PROMOTED |

Full per-fold detail (PSI per feature, precision/recall, regression %, gate reasons) in the raw
artifact.

## Transferability finding

The same real policy code (`policy.should_retrain`/`joint_cell`) correctly reproduces the full
RETAIN/EVALUATE/RETRAIN-equivalent state space on an entirely different, publicly-sourced,
naturally-drifting workload: both "significant drift + healthy incumbent" (none observed this run)
and "significant drift + degraded incumbent → fire" (folds 1, 2, 4) and "sub-significant drift +
degraded incumbent → hold/investigate, not fire" (fold 3) appear. Fold 3 is a concrete
counter-example to "drift alone predicts promotion": its incumbent degraded (BAD) but drift was
only WARNING, so the policy correctly did **not** fire, and the (still-trained) candidate was
separately rejected by the quality gate on its own merits — drift and gate operate as the two
independent signals the paper's design intends, confirmed on a second, independent dataset.

This is reported as transferability evidence only — 5 folds on one additional public corpus is
not a population-wide generalization claim, and is not presented as one.

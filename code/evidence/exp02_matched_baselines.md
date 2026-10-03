# EXP-02 — Matched Policy Baselines

**Experiment ID:** `EXP-02`
**Raw artifacts:** `evidence/exp02_matched_baselines.json` (per-cycle detail, all 12 seeds × 5 policies),
`evidence/exp02_statistical_summary.json`/`.md` (aggregated statistics)
**Protocol:** `scripts/exp02_matched_baselines.py` + `scripts/exp02_policies.py`

## Protocol

Identical dataset, data ordering, workload, model family (`ChurnMLP`), training budget
(epochs/batch size/lr/hidden dims), and candidate generator across every arm — **only**
the retrain-trigger decision differs. For each of 12 seeds, the same 5-scenario
sequence (`healthy → feature_drift → volume_anomaly → label_imbalance → regression`)
is generated **once** and shared byte-for-byte across all 5 policy arms for that seed;
each arm then independently decides, per cycle, whether to retrain, and — if it does —
runs the exact same `app.ml.gates.evaluation_gate` to decide promote/reject.

Policies (defined in `scripts/exp02_policies.py` before any run):

1. **drift_only** — retrain iff `drift_level == SIGNIFICANT`.
2. **periodic** — retrain every 2nd cycle, regardless of signal.
3. **performance_triggered** — retrain iff champion's live `evaluation_level == BAD`.
4. **medp** — `app.ml.policy.should_retrain` (the paper's actual policy), unmodified.
5. **static** (optional 5th policy per the PRD) — retrain only to bootstrap the first
   champion; never again.

Cycle 0 always bootstraps a champion for every policy unconditionally — this mirrors
the real system, where the first model is always created via an unconditional
schedule/manual trigger (`backend/app/seed.py`), not gated by the joint-cell policy.

## Results (12 seeds, paired by seed)

| Policy | Mean final F1 | Std | Mean retrains | Mean promotions | Mean wasted retrains | Mean train time (s) | Paired Δ vs MEDP | Paired Cohen's d vs MEDP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| drift_only | 0.9496 | 0.0405 | 2.000 | 1.917 | 0.083 | 1.374 | **+0.1477** | **2.618** |
| periodic | 0.7958 | 0.0380 | 3.000 | 1.167 | 0.833 | 1.248 | −0.0060 | −0.322 |
| performance_triggered | 0.8018 | 0.0301 | 2.333 | 1.000 | 1.250 | 1.404 | +0.0000 | 0.000 |
| medp | 0.8018 | 0.0301 | 1.000 | 1.000 | 0.000 | 0.577 | — | — |
| static | 0.8018 | 0.0301 | 1.000 | 1.000 | 0.000 | 0.581 | +0.0000 | 0.000 |

"Wasted retrains" = retrains that were attempted but rejected by the gate (compute
spent with no quality benefit).

## Interpretation (per the PRD's acceptance criterion)

**A superiority claim is allowed only if the matched experiment supports it.** Here:

- **MEDP does *not* outperform drift-only on final quality.** drift_only's final F1 is
  higher by a large, consistent margin (paired Cohen's d = 2.62 — a very large effect),
  because it retrains on every significant-drift batch unconditionally, sometimes
  catching a genuine quality improvement MEDP's health-gated trigger skips. This is
  reported as a **negative result for an MEDP-superiority-on-quality claim against
  drift-only**, not smoothed over. The trade-off: drift_only does this at roughly
  2.4× MEDP's training compute (2.0 vs 1.0 mean retrains; 1.37s vs 0.58s mean training
  time) for a 0.083-retrain average rate of wasted (rejected) compute.
- **MEDP matches periodic and performance_triggered on final quality** (paired
  difference ≈ 0, negligible-to-small effect sizes) **while using substantially less
  compute**: periodic retrains 3× on average (0.83 of them wasted) and
  performance_triggered retrains 2.33× on average (1.25 of them wasted), against
  MEDP's 1.0 retrains with zero wasted retrains. This **does** support a narrower,
  evidence-backed claim: *MEDP achieves equivalent final quality to periodic and
  performance-triggered retraining in this evaluated protocol, at lower retraining
  and wasted-compute cost.*
- **MEDP is behaviorally identical to the static baseline** in this specific protocol
  (both retrain count = 1, same final quality). This is disclosed as a degenerate-case
  finding: under this exact 5-scenario workload, the champion never degrades enough
  (`evaluation_level` never reaches `BAD` after bootstrap under MEDP's own health
  check) for MEDP's drift×health predicate to fire a second time — MEDP collapses to
  "retrain once, then never again" here, which is itself useful evidence about when
  MEDP's extra machinery does and does not add value over a static baseline.

## Acceptance criteria check

- [x] Controlled variables held identical across arms (dataset, ordering, workload,
      model family, candidate generator, training budget) — enforced by construction
      (one shared per-cycle batch per seed, reused byte-for-byte by every policy).
- [x] Matched runs with identical seeds — 12 seeds, paired statistics reported.
- [x] Per-run values, mean, standard deviation, paired differences, and effect sizes
      reported — not only aggregate averages.
- [x] Superiority claims restricted to what the matched data actually supports;
      the drift_only result is reported as a loss for MEDP on quality, not omitted.

## Disclosed limitations

- Rollback is not modeled in this comparison (`rollback_count` is uniformly 0) — none
  of these 5 cycles simulate a post-promotion production regression; rollback
  mechanics are already covered separately by EXP-06's tests.
- "periodic" uses a fixed every-2-cycles schedule, chosen before running (not tuned
  after seeing results); a different period would shift periodic's compute/quality
  trade-off and is not explored here.
- This is a 5-cycle, 12-seed protocol on the synthetic churn generator — it
  characterizes behavior under this evaluated protocol, not a claim of population-wide
  or cross-domain generalization (see EXP-04 for the separate transferability check).

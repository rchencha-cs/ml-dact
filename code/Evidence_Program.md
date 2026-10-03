# Quality-Gated Model Evolution in MLOps — Resubmission Evidence Program

**Document type:** Experimental validation plan
**Project:** Quality-Gated Model Evolution in MLOps: An Empirical Study of an Inspectable Decision Procedure for Distribution Shift
**Target:** journal resubmission
**Version:** 1.3 — updated 2026-10-03 (all 7 experiments complete; see Section 17)
**Status:** Experiments complete — 7 of 7 (manuscript update + final hostile review still pending, see Section 13/14)
**Repository:** `rcramu/ml-dact` (this evidence program lives on branch `evidence-program` of fork `rchencha-cs/ml-dact`, baseline commit `df2ad38`)
**Rule:** No fabricated results. Results enter the paper only after executable experiments produce them.

---

## 1. Objective

Close the remaining evidence gaps identified during the five-pass hostile review while preserving the manuscript's current claim boundaries.

The objective is **not** to make the paper longer. The objective is to produce evidence that addresses the specific reviewer attacks that cannot be resolved by prose.

---

# 2. Priority Backlog

| ID | Experiment / Evidence | Priority | Type | Current Status |
|---|---|---:|---|---|
| EXP-01 | Independent post-selection holdout | P0 | Methodological validity | **Complete** — `evidence/exp01_holdout.md` |
| EXP-02 | Matched policy baselines | P0 | Comparative evaluation | **Complete** — `evidence/exp02_matched_baselines.md` |
| EXP-03 | Threshold provenance audit | P0 | Reproducibility | **Complete** — `evidence/exp03_threshold_provenance.md` |
| EXP-04 | Structured Electricity replication | P1 | External/transferability | **Complete** — `evidence/exp04_electricity_protocol.md` |
| EXP-05 | Reproducibility artifact audit | P1 | Artifact quality | **Complete** — `evidence/exp05_traceability.md` (7/7 traceable) |
| EXP-06 | Policy-state transition test suite | P1 | Software-engineering validation | **Complete** — `evidence/exp06_policy_tests.json` (26/26 passing) |
| EXP-07 | Decision-lineage replay test | P1 | Auditability | **Complete** — `evidence/exp07_decision_lineage_replay.md` (23/23 match) |

---

# 3. EXP-01 — Independent Post-Selection Holdout

**Status: COMPLETE** — `code/evidence/exp01_holdout.md` + `.json`, commit `00ff42f`.
Five historical churn-predictor candidates (promoted and rejected) were deterministically
reproduced from already-persisted run/model identifiers — rejected candidates' weights are
never saved by `champion_store`, so reproduction is the only way to score them at all — then
scored against `generate_holdout()`, which uses 5 seeds (900001–900005) grep-verified to
appear nowhere in any ingestion/training/promotion code path. All 5 reproductions matched
their stored controller-facing F1 exactly. One finding: the rejected `label_imbalance`
candidate showed controller-facing F1 = 0.0 but holdout F1 = 0.30 — disclosed as evidence of
single-split F1 instability under ~2% class prevalence, not a correction to the reported number.

## Attack addressed

The controller-facing test data participate in candidate promotion. Therefore the reported evaluation can be affected by model-selection exposure.

## Objective

Create a final holdout that is completely invisible to:

- threshold selection
- candidate selection
- promotion decisions
- policy tuning
- exploratory analysis

## Protocol

```text
Training data
      ↓
Candidate generation
      ↓
Controller-facing evaluation
      ↓
MEDP decision
      ↓
Freeze policy decision
      ↓
Independent final holdout
```

## Required outputs

For every promoted/rejected candidate where applicable:

- controller-facing F1
- controller-facing precision
- controller-facing recall
- controller-facing accuracy
- final-holdout F1
- final-holdout precision
- final-holdout recall
- final-holdout accuracy
- difference between controller-facing and holdout metrics

## Acceptance criteria

- Holdout never reaches the controller.
- Holdout never influences thresholds.
- Holdout is evaluated only after policy decisions are frozen.
- Code/configuration proves separation.

## Paper impact

If successful, strengthen the predictive-validity discussion.

If not feasible, retain the limitation and do not claim unbiased post-selection performance.

---

# 4. EXP-02 — Matched Policy Baselines

**Status: COMPLETE** — `code/evidence/exp02_matched_baselines.md` + `exp02_statistical_summary.md`, commit `6887aea`.
12 matched seeds × 5 policies (drift_only, periodic, performance_triggered, medp, static), identical
workload shared byte-for-byte across arms per seed. Result, not spun: **drift_only beats MEDP on
final quality** (paired Cohen's d = 2.62 — a large effect) at ~2.4× the training compute — a genuine
negative result for an MEDP-superiority-on-quality claim against drift_only. MEDP **does** match
periodic/performance_triggered on final quality while using substantially less compute (0 wasted
retrains vs. 0.83/1.25) — a narrower, supported efficiency claim. MEDP is behaviorally identical to
the static baseline under this specific 5-cycle protocol (disclosed as a degenerate-case finding).

## Attack addressed

The paper currently cannot establish that MEDP is superior to alternative retraining policies.

## Policies

Run exactly the same workload/model/training budget under:

1. **Drift-only**
2. **Periodic retraining**
3. **Performance-triggered retraining**
4. **MEDP**

Optional fifth policy:

5. **Manual/static champion baseline**

## Controlled variables

Keep identical:

- dataset
- data ordering
- workload
- model family
- candidate generator
- training budget
- evaluation windows
- deployment latency assumptions
- rollback mechanism
- compute budget
- observation period

Only the decision policy changes.

## Metrics

### Quality

- F1
- precision
- recall
- accuracy

### Evolution behavior

- retraining count
- promotion count
- rejection count
- rollback count
- time to recovery
- time between model changes

### Efficiency

- training compute
- training duration
- token/compute cost where applicable
- unnecessary retraining count

## Required statistical treatment

Use matched runs with identical seeds/workload conditions where possible.

Report:

- per-run values
- mean
- standard deviation
- paired differences
- effect sizes where appropriate

Do not rely only on aggregate averages.

## Acceptance criteria

A superiority claim is allowed only if the matched experiment supports it.

Otherwise report the experiment as comparative characterization.

---

# 5. EXP-03 — Threshold Provenance Audit

**Status: COMPLETE** — `code/evidence/exp03_threshold_provenance.md` + `.json`, commit `808dd9f`.
All 6 thresholds traced to exact file:line. The `req.md` document cited in code
comments as rationale could not be located anywhere in the repository, so those
citations are recorded but flagged unverifiable. No pre-existing git history
exists before this program's baseline (`df2ad38`), so provenance is disclosed
as "engineering configuration," not a pre-registered trail, per Section 5's own
fallback rule below.

## Attack addressed

Reviewers may ask whether thresholds were selected before observing the results.

## Required table

| Parameter | Actual value | Source/rationale | Fixed before primary run? | Evidence |
|---|---:|---|---|---|
| PSI warning | TBD | TBD | TBD | commit/config |
| PSI significant | TBD | TBD | TBD | commit/config |
| F1 floor | TBD | TBD | TBD | commit/config |
| Precision floor | TBD | TBD | TBD | commit/config |
| Recall floor | TBD | TBD | TBD | commit/config |
| Regression budget | TBD | TBD | TBD | commit/config |

## Rules

Never infer provenance from memory.

Use:

- git history
- configuration files
- experiment manifests
- dated run metadata
- issue/PR records
- research notes

If provenance cannot be established, label the threshold as an engineering configuration and disclose the limitation.

---

# 6. EXP-04 — Structured Electricity Replication

**Status: COMPLETE** — `code/evidence/exp04_electricity_protocol.md` + `.json`, commit `55afc88`.
Executed via `scripts/run_electricity_natural.py`, already calling the real `policy.py`/`gates.py`
functions (per the EXP-06 refactor) rather than a reimplementation. All 9 required protocol items
documented. Fold 3 (WARNING drift + degraded incumbent) is a concrete counter-example to "drift
alone predicts promotion": the policy correctly held rather than fired, confirming drift and the
quality gate operate as independent signals on a second, independently-sourced workload. Reported
as transferability evidence only, not population-wide generalization.

## Objective

Test whether the MEDP state relationships appear outside the primary workload.

## Required protocol

Document:

1. Dataset/version
2. Chronological split
3. Drift definition
4. Incumbent definition
5. Candidate generation
6. Quality gate
7. Thresholds
8. Replicate count
9. Deviations from primary protocol

## Required outputs

- drift evidence
- incumbent quality
- candidate quality
- policy action
- state transition
- promotion/rejection result

## Interpretation

This is a **transferability evaluation**, not evidence of population-wide generalization.

---

# 7. EXP-05 — Reproducibility Artifact Audit

**Status: COMPLETE** — `code/evidence/exp05_traceability.md` + `.json`, commit `31366f5`.
`scripts/exp05_traceability_report.py` audited all 7 evidence files: 7/7 are substantively
traceable (git commit verified with `git cat-file -e`, not string-matching; producing
script/test confirmed on disk; `experiment_id` present). Two real gaps were found and fixed,
not just reported (missing provenance stamps on `score_exp02.py`'s output; a bare copy of
`run_electricity_natural.py`'s output with no provenance fields, now wrapped). Disclosed gap,
not hidden: no file carries the PRD's literal 12-field metadata schema verbatim — the substance
is usually present under a different name (e.g. a seeds list instead of a single `random_seed`
scalar); tracked as an open follow-up.

## Objective

Make every reported result executable and traceable.

## Required metadata

Every experiment should record:

```text
experiment_id
git_commit
dataset_version
model_version
policy_version
threshold_config_version
random_seed
replicate_id
environment
timestamp
evaluation_window
result_artifact
```

## Acceptance criteria

Every paper table/figure can be traced to:

```text
paper result
   ↓
experiment ID
   ↓
script/config
   ↓
code commit
   ↓
raw result artifact
```

If a result cannot be traced, remove it from the final quantitative claims.

---

# 8. EXP-06 — MEDP Policy-State Test Suite

**Status: COMPLETE** — `code/evidence/exp06_policy_tests.json`, commit `808dd9f`.
The Section 8.4 joint-cell decision matrix (previously duplicated across
`routers/joint.py`, `ml/electricity.py`, and `scripts/run_electricity_natural.py`)
was extracted into one module, `backend/app/ml/policy.py`, verified
behavior-preserving (byte-identical decisions for every fold against the
pre-refactor stored output). 26/26 tests pass in `backend/tests/test_policy.py`,
covering the table below plus boundary/epsilon, missing-metric, stale-champion,
duplicate/repeated-candidate, and rollback-after-promotion cases against the
real production functions. One finding surfaced (not hidden): the
`SIGNIFICANT`+`UNKNOWN` cell is labeled "Obtain ground truth" but the code
actually fires retraining there — a label/behavior mismatch in production.

## Objective

Demonstrate that the decision policy itself is testable software.

## Required policy tests

| State | Expected action |
|---|---|
| Stable distribution + healthy incumbent | RETAIN |
| Drift + healthy incumbent | EVALUATE |
| Drift + degraded incumbent | RETRAIN |
| Candidate below quality floor | REJECT |
| Candidate violates recall constraint | REJECT |
| Candidate passes all constraints | PROMOTE |
| Failed promoted candidate | ROLLBACK |

## Additional tests

- boundary threshold
- threshold ± epsilon
- missing metric
- stale champion
- duplicate candidate
- repeated candidate
- rollback after promotion

## Paper impact

Strengthens the claim:

> Model-evolution policy logic can be independently tested as decision software.

---

# 9. EXP-07 — Decision-Lineage Replay

**Status: COMPLETE** — `code/evidence/exp07_decision_lineage_replay.md` + `.json`, commit `35b1f7a`.
15 JointDecision rows (5 churn scenarios × 2 seeds + 5 Electricity folds) and 8
EvaluationResult rows were generated against a fresh, isolated docker-compose stack,
then independently replayed through the real `policy.py`/`gates.py` functions.
**23/23 replayed actions matched the recorded action (100%)**, covering all three
trigger states (RETAIN/EVALUATE/RETRAIN) and both gate outcomes (PASS/FAIL).
Rollback is disclosed as out of scope: it is an externally/manually triggered action
in this codebase, not an automated policy output, so there is no "decision" to replay
(its state-transition mechanics are already covered by EXP-06's tests).

## Objective

Prove that a historical model-evolution decision can be reconstructed from its persisted evidence.

## Required record

```text
trigger
distribution evidence
champion ID
candidate ID
candidate metrics
policy version
threshold configuration
gate decisions
final action
rollback status
timestamp
```

## Replay test

Given only the persisted decision record and the corresponding policy version:

```text
record
  ↓
replay policy
  ↓
expected action
  ==
recorded action
```

## Acceptance criterion

Replay must reproduce the original decision.

## Paper impact

Strengthens the auditability and reproducibility contribution.

---

# 10. Claim-Evidence Matrix

Do not change the paper's claims until the evidence is available.

| Claim | Current evidence | Additional evidence |
|---|---|---|
| Drift can be detected under the configured protocol | Available | None for bounded claim |
| Drift is not equivalent to degradation | Available | Secondary replication strengthens |
| Retraining is associated with improved quality in evaluated scenario | Available | Causal experiment only for causal claim |
| Multi-metric gating changes decisions | Available | None required for counterexample claim |
| Incumbent state affects decisions | Available | More repetitions strengthen |
| Thresholds influence decisions | Available | Provenance audit — **done, EXP-03** |
| MEDP is auditable | Partially available | Replay experiment strengthens — **done, EXP-07 (23/23 match)** |
| MEDP is independently testable | Design established | Policy test suite — **done, EXP-06** |
| MEDP outperforms drift-only | **Refuted on quality** — drift-only wins by a large effect (d=2.62), at ~2.4× the compute | EXP-02, done |
| MEDP outperforms periodic retraining | **Equivalent quality, lower compute** — not a quality-superiority claim, but a supported efficiency one | EXP-02, done |
| MEDP outperforms performance-triggered retraining | **Equivalent quality, lower compute** — same caveat as above | EXP-02, done |
| Post-selection performance is unbiased | **Established for the churn-predictor protocol** (5/5 candidates reproduced exactly; holdout deltas reported, including one large one, not hidden) | EXP-01, done |
| Results generalize broadly | Still **not established** — EXP-04 is one additional workload (transferability only); still not a population-wide generalization claim | EXP-04 done; broader generalization remains out of scope |
| MEDP is universally optimal | Not claimed | Do not claim |

---

# 11. Execution Order

Recommended sequence:

```text
EXP-03 Threshold provenance
        ↓
EXP-06 Policy-state tests
        ↓
EXP-07 Decision-lineage replay
        ↓
EXP-01 Independent holdout
        ↓
EXP-02 Matched policy baselines
        ↓
EXP-04 Electricity replication
        ↓
EXP-05 Artifact audit
        ↓
Update manuscript
        ↓
Final Pass 5 review
```

---

# 12. Manuscript Update Rules

After experiments complete:

### If an experiment succeeds

Update:

- Methods
- Results
- tables/figures
- RQ answers
- Discussion
- Threats to validity
- Conclusion

### If an experiment produces mixed results

Report the mixed result.

Do not optimize the narrative around only favorable outcomes.

### If an experiment fails

Report the failure if scientifically relevant and preserve the limitation.

Never replace a failed experiment with an assumed result.

---

# 13. Final Submission Gate

Before submission, all of the following should be answered:

- [ ] Can every quantitative claim be reproduced?
- [ ] Are all thresholds traceable?
- [ ] Is the final holdout independent?
- [ ] Are competing policies matched?
- [ ] Are primary and exploratory analyses clearly separated?
- [ ] Is incumbent state explicitly represented?
- [ ] Is decision lineage replayable?
- [ ] Is policy logic independently testable?
- [ ] Are causal claims avoided unless causality was experimentally established?
- [ ] Are broad generalization claims avoided?
- [ ] Does every major contribution have direct evidence?

**Submission recommendation:** only proceed after the evidence matrix is updated from actual experiment outputs.

---

## Non-Negotiable Research Rule

> **No fabricated results. No retroactive threshold provenance. No converting exploratory runs into confirmatory evidence. No superiority claims without matched baselines.**

The manuscript may be polished aggressively, but numerical evidence must always come from the executable research code and retained artifacts.


---

# 14. Pass 6 Pre-Submission Gate — Added

The manuscript has now been hardened for final pre-submission review. The following are **not prose defects** and remain evidence-dependent:

## P6-01 — Experimental claim verification

Before replacing any `TBD` or provisional statement with a numerical result:

- execute the corresponding experiment;
- retain raw output;
- record code commit and configuration;
- update the claim-evidence matrix;
- update the manuscript only from the observed output.

## P6-02 — Figure/table provenance

Every final numerical table or figure must have:

```text
paper table/figure
    ↓
experiment ID
    ↓
code/config version
    ↓
raw result
```

If this chain is missing, do not use the result as primary evidence.

## P6-03 — RQ traceability

After experiments complete, verify:

```text
RQ
 ↓
hypothesis/proposition
 ↓
experiment
 ↓
raw output
 ↓
statistical/empirical analysis
 ↓
result
 ↓
discussion
 ↓
conclusion
```

No RQ should have a conclusion stronger than its experiment.

## P6-04 — Final reviewer attack

After EXP-01 through EXP-07 are executed where applicable, run one final hostile review specifically asking:

1. What claim would a skeptical reviewer say is unsupported?
2. Which result could be explained by an alternative mechanism?
3. Which threshold could be accused of retrospective tuning?
4. Which comparison is missing?
5. Which conclusion exceeds the evidence?
6. Which implementation detail is being incorrectly presented as research novelty?

The manuscript should be changed only where the evidence supports the change.

## P6-05 — No-result policy

If an experiment produces:

- null result,
- contradictory result,
- unexpected result,
- failed replication,
- unstable result,

report it according to its scientific relevance. Do not rerun selectively until a favorable result appears without a predefined rationale.



---

# 15. Pass 7 — Editorial Consistency Gate

The following fixable issues were addressed directly in V26:

- Removed duplicated wording such as "controlled ... controlled empirical evaluation".
- Replaced remaining manuscript uses of "case-study" terminology with evaluation terminology where it referred to the present study.
- Replaced ambiguous "held-out F1/metrics" language with "test-split F1/metrics" where the metric is consumed by the promotion controller.
- Preserved "independent holdout" only for the future EXP-01 methodology.
- Corrected future-work numbering/order without changing the underlying research proposals.
- Added an explicit editorial consistency gate covering evidence hierarchy and research-object framing.

No numerical results were changed in this pass.

## Still evidence-dependent

No new result was invented. As of v1.3 (Section 17), all 7 of EXP-01 through
EXP-07 are complete. What remains open is the manuscript update itself
(Section 12) and the final Pass 6 hostile review (Section 14, P6-04) applied
to the actual evidence produced — not any further experiment execution.


---

# 16. Pass 8 — Methods/Results Traceability Gate

## Fixes completed in V27

- Added a **Reproducibility Contract** to methodology.
- Explicitly defined the **unit of analysis** as a model-evolution decision cycle under a specified policy state.
- Clarified that primary replicates characterize protocol stability rather than population effects.
- Added an explicit **evidence hierarchy** separating primary, ablation/sensitivity, and secondary transferability analyses.
- Added a final conclusion boundary preventing unsupported production-scale, universal-superiority, or unbiased-post-selection claims.
- Reduced potential novelty overstatement where infrastructure/architecture wording could be interpreted as the research contribution.

## Evidence-dependent items remain unchanged

No results were fabricated or inferred. As of v1.3, all 7 experiments (EXP-01
through EXP-07) have been executed from the research code with verified
artifacts (Section 17). Manuscript claims should now be updated only from
these actual outputs, per Section 12's rules — including where the evidence
is mixed or negative (EXP-02's drift-only result) rather than only favorable.

---

# 17. Execution Log — Evidence Program v1.3

Tracks actual progress against Sections 2–9. Updated only from real command
output and committed artifacts, never from memory, per this document's
non-negotiable research rule.

| Step | Status | Commit | Evidence |
|---|---|---|---|
| Step 0 — git init + baseline | Done | `df2ad38` | First version control this project has had; anchors all provenance from here forward |
| EXP-03 — threshold provenance audit | **Done** | `808dd9f` | `code/evidence/exp03_threshold_provenance.md`, `.json` |
| EXP-06 — policy-state test suite | **Done** | `808dd9f`, `8a70e1d` | `code/evidence/exp06_policy_tests.json`; 26/26 tests passing in `backend/tests/test_policy.py` |
| EXP-07 — decision-lineage replay | **Done** | `aae2df0`, `35b1f7a` | `code/evidence/exp07_decision_lineage_replay.md`, `.json`; 23/23 replayed decisions matched (100%) |
| EXP-01 — independent holdout | **Done** | `00ff42f` | `code/evidence/exp01_holdout.md`, `.json`; 5/5 candidates reproduced exactly |
| EXP-02 — matched policy baselines | **Done** | `6887aea` | `code/evidence/exp02_matched_baselines.md`, `exp02_statistical_summary.md`; 12 seeds x 5 policies |
| EXP-04 — structured Electricity replication | **Done** | `55afc88` | `code/evidence/exp04_electricity_protocol.md`, `.json`; 9/9 protocol items documented |
| EXP-05 — reproducibility artifact audit | **Done** | `31366f5` | `code/evidence/exp05_traceability.md`, `.json`; 7/7 evidence files substantively traceable |

All 7 experiments are now complete. Remaining work per Section 12: update the
manuscript's Methods/Results/Discussion/Threats-to-validity/Conclusion sections
from these actual outputs (including the negative EXP-02 drift-only result and
the EXP-05 disclosed schema gap), then run the Pass 6 final hostile review
(Section 14, P6-04).

**Where this lives:** the working repository is `code/` in this project directory
(its own local git history, commits above). A snapshot of this work was also
pushed to branch `evidence-program` on `rchencha-cs/ml-dact` (a fork of the
paper's repository `rcramu/ml-dact`) for review; no PR has been opened yet.

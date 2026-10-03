# EXP-05 — Reproducibility Artifact Audit

**Experiment ID:** `EXP-05`
**Raw artifact:** `evidence/exp05_traceability.json`
**Executable:** `scripts/exp05_traceability_report.py`

## What this checks

For every `evidence/*.json` produced by EXP-01, EXP-02, EXP-03, EXP-04, EXP-06, and EXP-07:

1. **Substantive traceability** — the actual chain the PRD cares about: does the file cite an
   `experiment_id`? Is its `git_commit` a real commit in this repo (verified with
   `git cat-file -e`, not just string-shaped)? Does the script/config that produced it exist on
   disk? This is what "paper result → experiment ID → script/config → code commit → raw result
   artifact" means in practice.
2. **Literal schema compliance** — whether the PRD's full 12-field metadata block
   (`experiment_id, git_commit, dataset_version, model_version, policy_version,
   threshold_config_version, random_seed, replicate_id, environment, timestamp,
   evaluation_window, result_artifact`) is present verbatim as top-level keys.

These are reported **separately** on purpose: (1) is the real acceptance criterion ("can this
be traced and reproduced"), and (2) is a stricter, literal schema check that this audit does not
let (1) paper over.

## Result

**7/7 evidence files are substantively traceable** (commit verified in `git log`, producing
script/test file exists on disk, `experiment_id` present) — two real gaps found and fixed
during this audit, not just reported and left:

- `evidence/exp02_statistical_summary.json` (from `scripts/score_exp02.py`) originally had no
  `experiment_id`/`git_commit` at all. Fixed by adding provenance stamping to the script
  (commit `6887aea`+fix).
- `evidence/exp04_electricity_replication.json` was a raw copy of
  `scripts/run_electricity_natural.py`'s own output format (an older exploratory script,
  never designed with provenance fields). Fixed by wrapping it in an
  `{experiment_id, git_commit, timestamp, source_script, raw_output}` envelope instead of a
  bare copy.

## Disclosed gap: literal schema compliance is partial

No evidence file carries all 12 PRD-specified field names verbatim (9–10 of 12 missing in each,
per the raw audit). The substance is usually present under a different name or nested one level
down rather than absent outright:

| PRD field | Typically present as |
|---|---|
| `dataset_version` | scenario name + seed (e.g. `holdout_seeds`, `dataset_seed` inside per-run detail) — not a single top-level version string |
| `model_version` | `candidate_version` / `version` inside per-row detail, not top-level |
| `policy_version` | present top-level in EXP-06/EXP-07 (`app.ml.policy@<commit>`); absent from EXP-01/02/04 |
| `threshold_config_version` | present inside individual EXP-06/EXP-07 decision records, not as a top-level summary field |
| `random_seed` | present as a `seeds`/`holdout_seeds` **list**, not a single `random_seed` scalar (these experiments are multi-seed by design) |
| `replicate_id` | not present as a named field — the seed itself identifies a replicate |
| `environment` | not captured anywhere (no Python/package-version fingerprint stamped into any evidence file yet) |
| `evaluation_window` | not applicable in the PRD's streaming-system sense — these are one-shot script runs, not windowed online monitoring |
| `result_artifact` | implicit (the file's own path) — no evidence file names itself |

## Recommendation

This gap is real and should be closed before treating these artifacts as final
manuscript-ready evidence: add `app.ml.provenance.environment_fingerprint()` (already written
for EXP-07's backend use, but not yet called from any of the standalone `scripts/exp0*.py`) to
every experiment script's output, and adopt a single top-level `random_seed`/`replicate_id`
convention for multi-seed experiments (e.g. `"seeds": [...], "n_replicates": 12`, already present
in substance, just not under the PRD's exact field names). This is tracked as an open follow-up,
not silently fixed by renaming existing keys after the fact.

## Acceptance criteria check

- [x] Every evidence file traces to a real, verifiable git commit.
- [x] Every evidence file's producing script/test exists on disk at that commit.
- [x] Gaps found during the audit were fixed, not just reported (EXP-02 summary, EXP-04 wrapper).
- [ ] Full literal 12-field PRD metadata schema — **partial**, disclosed above, not claimed as met.

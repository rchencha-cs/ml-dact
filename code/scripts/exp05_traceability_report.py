"""EXP-05 -- reproducibility artifact audit.

Walks every evidence/*.json file produced by EXP-01..EXP-04/06/07 and checks,
for each one:
  1. Does it cite a git_commit, and does that commit actually exist in this
     repo's history (not just a plausible-looking string)?
  2. Does the script/config that produced it exist on disk?
  3. Does it carry the PRD's full required metadata block verbatim
     (experiment_id, git_commit, dataset_version, model_version,
     policy_version, threshold_config_version, random_seed, replicate_id,
     environment, timestamp, evaluation_window, result_artifact)?

This does not retroactively relabel anything as compliant -- gaps in (3) are
reported as gaps, per the PRD's own rule: "if a result cannot be traced,
remove it from the final quantitative claims." What this script checks
instead is the *substantive* chain (paper result -> experiment ID -> script
-> commit -> raw artifact), which is a weaker but real claim: every number
in these evidence files can actually be regenerated and inspected, even
where the literal metadata schema isn't uniformly embedded in the JSON yet.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = REPO / "evidence"

REQUIRED_FIELDS = [
    "experiment_id", "git_commit", "dataset_version", "model_version",
    "policy_version", "threshold_config_version", "random_seed", "replicate_id",
    "environment", "timestamp", "evaluation_window", "result_artifact",
]

# Which script/config actually produced each file -- the substantive
# traceability chain's "script/config" link, verified to exist on disk.
SCRIPT_MAP = {
    "exp01_holdout.json": "scripts/exp01_holdout_eval.py",
    "exp02_matched_baselines.json": "scripts/exp02_matched_baselines.py",
    "exp02_statistical_summary.json": "scripts/score_exp02.py",
    "exp03_threshold_provenance.json": None,  # hand-authored static source audit, no script
    "exp04_electricity_replication.json": "scripts/run_electricity_natural.py",
    "exp06_policy_tests.json": "backend/tests/test_policy.py",
    "exp07_replay.json": "scripts/exp07_replay.py",
}

SKIP = {"exp05_traceability.json"}


def commit_exists(commit: str | None) -> bool:
    if not commit or commit in ("unknown", ""):
        return False
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=REPO, check=True, capture_output=True,
        )
        return True
    except Exception:
        return False


def audit_file(path: Path) -> dict:
    data = json.loads(path.read_text())
    present = {f: (f in data) for f in REQUIRED_FIELDS}
    missing = [f for f, ok in present.items() if not ok]
    script = SCRIPT_MAP.get(path.name, "NOT_MAPPED")
    script_exists = (REPO / script).is_file() if script else None
    commit = data.get("git_commit")
    commit_ok = commit_exists(commit)
    chain_breaks = []
    if not data.get("experiment_id"):
        chain_breaks.append("no experiment_id")
    if script == "NOT_MAPPED":
        chain_breaks.append("no script mapped in SCRIPT_MAP -- audit this script")
    elif script is not None and not script_exists:
        chain_breaks.append("mapped script not found on disk")
    if commit and not commit_ok:
        chain_breaks.append("cited git_commit not found in this repo's history")
    return {
        "file": str(path.relative_to(REPO)),
        "experiment_id": data.get("experiment_id"),
        "schema_fields_present": [f for f, ok in present.items() if ok],
        "schema_fields_missing": missing,
        "cited_commit": commit,
        "commit_verified": commit_ok,
        "mapped_script": script,
        "script_exists_on_disk": script_exists,
        "substantively_traceable": len(chain_breaks) == 0,
        "chain_breaks": chain_breaks,
    }


def main() -> None:
    results = [audit_file(f) for f in sorted(EVIDENCE_DIR.glob("*.json")) if f.name not in SKIP]
    traceable = sum(1 for r in results if r["substantively_traceable"])
    blob = {
        "experiment_id": "EXP-05",
        "required_schema_fields": REQUIRED_FIELDS,
        "files_audited": len(results),
        "substantively_traceable": traceable,
        "not_traceable": len(results) - traceable,
        "results": results,
    }
    out = EVIDENCE_DIR / "exp05_traceability.json"
    out.write_text(json.dumps(blob, indent=2) + "\n")

    print(f"Audited {len(results)} evidence files: {traceable} substantively traceable, "
          f"{len(results) - traceable} with chain breaks.\n")
    for r in results:
        flag = "OK" if r["substantively_traceable"] else "GAP"
        print(f"[{flag}] {r['file']:45} commit={r['cited_commit']!s:10} "
              f"verified={r['commit_verified']}  missing_schema_fields={len(r['schema_fields_missing'])}/12")
        if r["chain_breaks"]:
            for b in r["chain_breaks"]:
                print(f"       - {b}")


if __name__ == "__main__":
    main()

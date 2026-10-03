"""EXP-01 -- independent post-selection holdout.

Scope: the churn-predictor PyTorch pipeline (paper Section 7.1's primary
protocol). Electricity is out of scope -- it is already labeled exploratory/
transferability (EXP-04), not part of the primary confirmatory evaluation.

For every PipelineRun that actually trained a candidate (promoted or
rejected), this script:
  1. Deterministically reproduces that exact candidate: same dataset_seed
     and torch_seed pipeline_engine.run_pipeline used (derived only from
     model name + run id, both already persisted), so it does not depend on
     champion_store having saved weights -- rejected candidates' weights are
     never persisted in this codebase, so reproduction is the only way to
     score them at all.
  2. Sanity-checks the reproduction against the real controller-facing
     metrics already stored on the ModelVersion row (should match to
     floating-point precision).
  3. Scores that exact model+threshold against data_generator.generate_holdout(),
     which uses seeds (900001-900005) reserved for this purpose and never
     passed to generate_scenario() anywhere else in this codebase -- grep
     proof is included in the evidence doc, not just asserted here.
  4. Reports controller-facing vs. holdout metrics and their deltas.

Run after the stack's seed scenarios (and any other training) have already
completed and their promotion/rejection decisions are frozen in the DB --
this script only reads already-committed PipelineRun/ModelVersion rows and
never writes anything back.

    CTP_POSTGRES_PORT=5477 PYTHONPATH=backend python scripts/exp01_holdout_eval.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models as m
from app import data_generator as gen
from app.config import settings
from app.ml.evaluation_metrics import classification_metrics
from app.ml.pytorch_trainer import best_threshold_for_f1, predict, train_model

HOST_POSTGRES_PORT = os.environ.get("CTP_POSTGRES_PORT", "5476")
HOST_DATABASE_URL = f"postgresql+psycopg2://dact_user:dact_pass@localhost:{HOST_POSTGRES_PORT}/dact_training"
OUT = Path(__file__).resolve().parents[1] / "evidence" / "exp01_holdout.json"
HOLDOUT_ROWS = 1500


def _reproduce_and_score(run: m.PipelineRun, scenario: str) -> dict | None:
    dataset_seed = gen.stable_seed(f"{run.model.name}:{run.id}") % 100000
    records = gen.generate_scenario(scenario, dataset_seed, settings.expected_volume)
    x_train, y_train = gen.records_to_arrays(records, "train")
    x_val, y_val = gen.records_to_arrays(records, "val")
    x_test, y_test = gen.records_to_arrays(records, "test")
    if len(y_train) == 0:
        return None

    torch_seed = dataset_seed % (2**31)
    trained, _final_loss = train_model(
        x_train, y_train, epochs=settings.train_epochs, batch_size=settings.train_batch_size,
        learning_rate=settings.train_learning_rate, hidden1=settings.hidden_dim_1, hidden2=settings.hidden_dim_2,
        seed=torch_seed,
    )
    val_probs = predict(trained, x_val)
    threshold = best_threshold_for_f1(val_probs, y_val) if len(y_val) else 0.5
    test_probs = predict(trained, x_test)
    test_preds = (test_probs >= threshold).astype(int)
    reproduced_test_metrics = classification_metrics(test_probs, test_preds, y_test) if len(y_test) else None

    holdout_records = gen.generate_holdout(scenario, HOLDOUT_ROWS)
    x_hold, y_hold = gen.records_to_arrays(holdout_records, "holdout")
    hold_probs = predict(trained, x_hold)
    hold_preds = (hold_probs >= threshold).astype(int)
    holdout_metrics = classification_metrics(hold_probs, hold_preds, y_hold)

    return {
        "threshold": round(float(threshold), 4),
        "reproduced_controller_facing": reproduced_test_metrics,
        "holdout": holdout_metrics,
        "n_holdout": int(len(y_hold)),
    }


def main() -> None:
    engine = create_engine(HOST_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    runs = (
        db.query(m.PipelineRun)
        .filter(m.PipelineRun.candidate_version_id.isnot(None))
        .order_by(m.PipelineRun.started_at.asc())
        .all()
    )

    rows = []
    for run in runs:
        candidate = db.query(m.ModelVersion).filter_by(id=run.candidate_version_id).one_or_none()
        if candidate is None or candidate.framework != "PyTorch":
            continue  # Electricity candidates (sklearn) are out of scope -- see docstring
        dataset = db.query(m.DatasetVersion).filter_by(id=run.dataset_version_id).one_or_none()
        if dataset is None:
            continue
        scenario = dataset.scenario
        if scenario not in gen._HOLDOUT_SEEDS:
            continue

        repro = _reproduce_and_score(run, scenario)
        if repro is None:
            continue

        stored_controller_facing = {
            "f1": candidate.test_f1, "precision": candidate.precision,
            "recall": candidate.recall, "accuracy": candidate.accuracy,
        }
        reproduction_matches = (
            repro["reproduced_controller_facing"] is not None
            and abs(repro["reproduced_controller_facing"]["f1"] - stored_controller_facing["f1"]) < 1e-6
        )
        holdout = repro["holdout"]
        rows.append({
            "run_id": run.id,
            "model_name": run.model.name,
            "scenario": scenario,
            "outcome": run.outcome,
            "candidate_version": candidate.version,
            "controller_facing_f1": stored_controller_facing["f1"],
            "controller_facing_precision": stored_controller_facing["precision"],
            "controller_facing_recall": stored_controller_facing["recall"],
            "controller_facing_accuracy": stored_controller_facing["accuracy"],
            "reproduction_exactly_matches_stored_metrics": reproduction_matches,
            "final_holdout_f1": holdout["f1"],
            "final_holdout_precision": holdout["precision"],
            "final_holdout_recall": holdout["recall"],
            "final_holdout_accuracy": holdout["accuracy"],
            "delta_f1": round(holdout["f1"] - stored_controller_facing["f1"], 4),
            "delta_precision": round(holdout["precision"] - stored_controller_facing["precision"], 4),
            "delta_recall": round(holdout["recall"] - stored_controller_facing["recall"], 4),
            "delta_accuracy": round(holdout["accuracy"] - stored_controller_facing["accuracy"], 4),
            "n_holdout": repro["n_holdout"],
        })
    db.close()

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True,
        ).strip()
    except Exception:
        commit = "unknown"

    blob = {
        "experiment_id": "EXP-01",
        "git_commit": commit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "holdout_seeds": gen._HOLDOUT_SEEDS,
        "n_candidates_evaluated": len(rows),
        "candidates": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(blob, indent=2, default=str) + "\n")
    print(json.dumps({k: v for k, v in blob.items() if k != "candidates"}, indent=2))
    for r in rows:
        print(f"{r['scenario']:16} v{r['candidate_version']:<3} {r['outcome']:20} "
              f"ctrl_f1={r['controller_facing_f1']:.4f} holdout_f1={r['final_holdout_f1']:.4f} "
              f"delta={r['delta_f1']:+.4f} repro_match={r['reproduction_exactly_matches_stored_metrics']}")


if __name__ == "__main__":
    main()

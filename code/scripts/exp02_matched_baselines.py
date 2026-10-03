"""EXP-02 -- matched policy baselines.

Runs the identical workload (same 5 scenarios, same order, same per-cycle
synthetic batches -- generated once and shared byte-for-byte across every
policy arm for a given seed) under 5 trigger policies: drift_only, periodic,
performance_triggered, medp (the paper's actual policy, unmodified), and
static. Only the retrain-trigger decision differs between arms; the quality
gate (app.ml.gates.evaluation_gate) and training budget are identical for all.

Design choices fixed here, before running (not tuned after seeing results):
  - Cycle 0 always bootstraps a champion for every policy, unconditionally --
    this mirrors how the real system actually works: the very first model is
    always created via an unconditional schedule/manual trigger
    (backend/app/seed.py), never gated by the joint-cell policy. Each
    policy's own trigger logic governs cycles 1-4 only.
  - PSI reference batch is one extra "healthy" batch per seed, generated
    before cycle 0 and held fixed for the whole sequence (mirrors
    routers/joint.py's use of the model's original healthy reference dataset).
  - The quality gate compares each candidate against the champion's *stored*
    metrics from when it was promoted (matching pipeline_engine.py's
    compare_champion stage), not a live re-score of the champion on the
    current batch -- that live re-score is what drives evaluation_level
    instead.

    PYTHONPATH=backend python scripts/exp02_matched_baselines.py
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import data_generator as gen
from app.config import settings
from app.ml.drift import drift_level, psi_numeric
from app.ml.evaluation_metrics import classification_metrics
from app.ml.gates import evaluation_gate
from app.ml.pytorch_trainer import best_threshold_for_f1, predict, train_model

from exp02_policies import POLICY_NAMES, TRIGGER_FUNCS, PERIODIC_EVERY_N

SCENARIOS = ["healthy", "feature_drift", "volume_anomaly", "label_imbalance", "regression"]
SEEDS = list(range(1, 13))  # 12 matched replicates, matching this repo's run_replicates.py convention
F1_GOOD = settings.minimum_f1
OUT = Path(__file__).resolve().parents[1] / "evidence" / "exp02_matched_baselines.json"


def _mean_psi(ref_records: list[dict], prod_records: list[dict]) -> float:
    vals = []
    for name in gen.FEATURE_NAMES:
        a = [float(r[name]) if not isinstance(r[name], bool) else float(int(r[name])) for r in ref_records]
        b = [float(r[name]) if not isinstance(r[name], bool) else float(int(r[name])) for r in prod_records]
        import numpy as np
        vals.append(psi_numeric(np.array(a), np.array(b)))
    return float(sum(vals) / len(vals)) if vals else 0.0


def run_one_seed(seed: int) -> dict:
    ref_seed = gen.stable_seed(f"exp02:{seed}:ref") % 100000
    ref_records = gen.generate_scenario("healthy", ref_seed, settings.expected_volume)

    champions: dict[str, dict | None] = {name: None for name in POLICY_NAMES}
    cycles: dict[str, list[dict]] = {name: [] for name in POLICY_NAMES}
    training_seconds: dict[str, float] = {name: 0.0 for name in POLICY_NAMES}

    for cycle_index, scenario in enumerate(SCENARIOS):
        dataset_seed = gen.stable_seed(f"exp02:{seed}:{cycle_index}:{scenario}") % 100000
        records = gen.generate_scenario(scenario, dataset_seed, settings.expected_volume)
        psi = _mean_psi(ref_records, records)
        dlev = drift_level(psi)
        ratio = len(records) / settings.expected_volume
        volume_ok = (1 - settings.volume_anomaly_tolerance) <= ratio <= (1 + settings.volume_anomaly_tolerance)
        x_train, y_train = gen.records_to_arrays(records, "train")
        x_val, y_val = gen.records_to_arrays(records, "val")
        x_test, y_test = gen.records_to_arrays(records, "test")
        torch_seed = dataset_seed % (2**31)

        for policy_name in POLICY_NAMES:
            champion = champions[policy_name]
            has_champion = champion is not None
            if champion is not None and len(y_test) >= 5:
                probs = predict(champion["model"], x_test)
                preds = (probs >= champion["threshold"]).astype(int)
                live_metrics = classification_metrics(probs, preds, y_test)
                elev = "GOOD" if live_metrics["f1"] >= F1_GOOD else "BAD"
            else:
                elev = "UNKNOWN"

            decide = True if cycle_index == 0 else TRIGGER_FUNCS[policy_name](cycle_index, dlev, elev, has_champion)
            entry = {
                "cycle": cycle_index, "scenario": scenario, "drift_level": dlev,
                "evaluation_level": elev, "decided_retrain": decide, "volume_ok": volume_ok,
            }

            if not decide:
                entry["action"] = "RETAIN"
            elif not volume_ok:
                entry["action"] = "BLOCKED_VOLUME"
            elif len(y_train) == 0:
                entry["action"] = "SKIPPED_NO_TRAIN_DATA"
            else:
                t0 = time.perf_counter()
                trained, _final_loss = train_model(
                    x_train, y_train, epochs=settings.train_epochs, batch_size=settings.train_batch_size,
                    learning_rate=settings.train_learning_rate, hidden1=settings.hidden_dim_1,
                    hidden2=settings.hidden_dim_2, seed=torch_seed,
                )
                training_seconds[policy_name] += time.perf_counter() - t0
                val_probs = predict(trained, x_val)
                threshold = best_threshold_for_f1(val_probs, y_val) if len(y_val) else 0.5
                test_probs = predict(trained, x_test)
                test_preds = (test_probs >= threshold).astype(int)
                cand_metrics = classification_metrics(test_probs, test_preds, y_test) if len(y_test) else {
                    "f1": 0.0, "precision": 0.0, "recall": 0.0, "accuracy": 0.0}
                champ_metrics_for_gate = (
                    {"f1": champion["f1"], "precision": champion["precision"], "recall": champion["recall"]}
                    if champion is not None else None
                )
                gate_result, regression_pct, reasons = evaluation_gate(cand_metrics, champ_metrics_for_gate)
                entry["gate_result"] = gate_result
                entry["candidate_f1"] = round(cand_metrics["f1"], 4)
                entry["regression_pct"] = regression_pct
                if gate_result == "PASS":
                    champions[policy_name] = {
                        "model": trained, "threshold": threshold, "f1": cand_metrics["f1"],
                        "precision": cand_metrics["precision"], "recall": cand_metrics["recall"],
                        "accuracy": cand_metrics["accuracy"], "promoted_at_cycle": cycle_index,
                    }
                    entry["action"] = "PROMOTED"
                else:
                    entry["action"] = "REJECTED"
            cycles[policy_name].append(entry)

    summaries = {}
    for policy_name in POLICY_NAMES:
        log = cycles[policy_name]
        retrain_count = sum(1 for e in log if e["decided_retrain"])
        promoted = [e for e in log if e["action"] == "PROMOTED"]
        rejected = [e for e in log if e["action"] == "REJECTED"]
        blocked = [e for e in log if e["action"] == "BLOCKED_VOLUME"]
        promotion_cycles = [e["cycle"] for e in promoted]
        gaps = [b - a for a, b in zip(promotion_cycles, promotion_cycles[1:])]
        first_bad_cycle = next((e["cycle"] for e in log if e["evaluation_level"] == "BAD"), None)
        recovery_cycle = next((c for c in promotion_cycles if first_bad_cycle is not None and c >= first_bad_cycle), None)
        final = champions[policy_name]
        summaries[policy_name] = {
            "final_f1": final["f1"] if final else None,
            "final_precision": final["precision"] if final else None,
            "final_recall": final["recall"] if final else None,
            "final_accuracy": final["accuracy"] if final else None,
            "retrain_count": retrain_count,
            "promotion_count": len(promoted),
            "rejection_count": len(rejected),
            "unnecessary_retrain_count": len(rejected),  # trained but not promoted
            "blocked_count": len(blocked),
            "rollback_count": 0,  # not modeled in this comparison -- see evidence doc
            "mean_cycles_between_promotions": (sum(gaps) / len(gaps)) if gaps else None,
            "time_to_recovery_cycles": (recovery_cycle - first_bad_cycle) if recovery_cycle is not None else None,
            "training_seconds": round(training_seconds[policy_name], 3),
            "cycles": log,
        }
    return summaries


def main() -> None:
    all_seeds = {}
    for seed in SEEDS:
        all_seeds[seed] = run_one_seed(seed)

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True,
        ).strip()
    except Exception:
        commit = "unknown"

    blob = {
        "experiment_id": "EXP-02",
        "git_commit": commit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "policies": POLICY_NAMES,
        "periodic_every_n": PERIODIC_EVERY_N,
        "scenarios": SCENARIOS,
        "seeds": SEEDS,
        "per_seed": all_seeds,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(blob, indent=2, default=str) + "\n")

    for policy_name in POLICY_NAMES:
        f1s = [all_seeds[s][policy_name]["final_f1"] for s in SEEDS if all_seeds[s][policy_name]["final_f1"] is not None]
        promos = [all_seeds[s][policy_name]["promotion_count"] for s in SEEDS]
        retrains = [all_seeds[s][policy_name]["retrain_count"] for s in SEEDS]
        mean_f1 = sum(f1s) / len(f1s) if f1s else None
        print(f"{policy_name:24} n_f1={len(f1s):2} mean_final_f1={mean_f1} mean_retrains={sum(retrains)/len(retrains):.2f} mean_promotions={sum(promos)/len(promos):.2f}")


if __name__ == "__main__":
    main()

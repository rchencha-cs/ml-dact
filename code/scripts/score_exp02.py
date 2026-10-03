"""EXP-02 statistical treatment: per-run values, mean/std, paired differences
(vs. medp, the paper's actual policy), and a paired Cohen's d effect size.
Does not retrain anything -- reads evidence/exp02_matched_baselines.json.
"""
from __future__ import annotations

import json
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "evidence" / "exp02_matched_baselines.json"
OUT_JSON = Path(__file__).resolve().parents[1] / "evidence" / "exp02_statistical_summary.json"
OUT_MD = Path(__file__).resolve().parents[1] / "evidence" / "exp02_statistical_summary.md"

QUALITY_METRIC = "final_f1"
BASELINE = "medp"


def paired_cohens_d(a: list[float], b: list[float]) -> float | None:
    diffs = [x - y for x, y in zip(a, b)]
    if len(diffs) < 2:
        return None
    mean_diff = statistics.mean(diffs)
    sd_diff = statistics.stdev(diffs)
    if sd_diff == 0:
        return 0.0 if mean_diff == 0 else None
    return mean_diff / sd_diff


def main() -> None:
    data = json.loads(SRC.read_text())
    seeds = data["seeds"]
    policies = data["policies"]
    per_seed = data["per_seed"]

    per_policy_values = {
        p: [per_seed[str(s)][p][QUALITY_METRIC] for s in seeds] for p in policies
    }
    # per_seed keys may be int or str depending on JSON round-trip; normalize
    if any(v is None for vals in per_policy_values.values() for v in [] ):
        pass

    def get(policy, seed):
        key = str(seed) if str(seed) in per_seed else seed
        return per_seed[key][policy]

    rows = []
    for s in seeds:
        row = {"seed": s}
        for p in policies:
            row[p] = get(p, s)[QUALITY_METRIC]
        rows.append(row)

    summary = {}
    baseline_vals = [get(BASELINE, s)[QUALITY_METRIC] for s in seeds]
    for p in policies:
        vals = [get(p, s)[QUALITY_METRIC] for s in seeds]
        retrain_counts = [get(p, s)["retrain_count"] for s in seeds]
        promo_counts = [get(p, s)["promotion_count"] for s in seeds]
        unnecessary = [get(p, s)["unnecessary_retrain_count"] for s in seeds]
        training_secs = [get(p, s)["training_seconds"] for s in seeds]
        paired_diff = [a - b for a, b in zip(vals, baseline_vals)]
        summary[p] = {
            "mean_final_f1": round(statistics.mean(vals), 4),
            "std_final_f1": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
            "mean_retrain_count": round(statistics.mean(retrain_counts), 3),
            "mean_promotion_count": round(statistics.mean(promo_counts), 3),
            "mean_unnecessary_retrain_count": round(statistics.mean(unnecessary), 3),
            "mean_training_seconds": round(statistics.mean(training_secs), 3),
            "paired_mean_diff_vs_medp": round(statistics.mean(paired_diff), 4),
            "paired_std_diff_vs_medp": round(statistics.stdev(paired_diff), 4) if len(paired_diff) > 1 else 0.0,
            "paired_cohens_d_vs_medp": (
                round(d, 4) if (d := paired_cohens_d(vals, baseline_vals)) is not None else None
            ),
        }

    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=SRC.resolve().parents[1], text=True,
        ).strip()
    except Exception:
        commit = "unknown"

    blob = {
        "experiment_id": "EXP-02",
        "git_commit": commit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_artifact": str(SRC.relative_to(SRC.resolve().parents[1])),
        "metric": QUALITY_METRIC, "baseline": BASELINE, "per_run": rows, "summary": summary,
    }
    OUT_JSON.write_text(json.dumps(blob, indent=2) + "\n")

    lines = ["# EXP-02 — Statistical Summary (final champion test F1, paired by seed)\n"]
    lines.append("| Policy | Mean F1 | Std F1 | Mean retrains | Mean promotions | Mean wasted retrains | Mean train time (s) | Paired Δ vs MEDP | Paired Cohen's d vs MEDP |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for p in policies:
        s = summary[p]
        lines.append(
            f"| {p} | {s['mean_final_f1']} | {s['std_final_f1']} | {s['mean_retrain_count']} | "
            f"{s['mean_promotion_count']} | {s['mean_unnecessary_retrain_count']} | {s['mean_training_seconds']} | "
            f"{s['paired_mean_diff_vs_medp']:+.4f} | {s['paired_cohens_d_vs_medp']} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

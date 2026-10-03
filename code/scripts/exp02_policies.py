"""EXP-02 matched policy baselines: trigger-decision functions.

Each policy only decides WHETHER a retrain cycle happens; the quality gate
that decides PROMOTE/REJECT (app.ml.gates.evaluation_gate) is identical for
every policy, per the PRD's controlled variables ("only the decision policy
changes"). These are comparison-only baselines, not production code -- they
are deliberately kept out of backend/app/ml/policy.py.

Definitions (fixed here, before any run, to avoid retrospective tuning):
  - drift_only:          retrain iff drift_level == SIGNIFICANT. Ignores
                          incumbent health entirely.
  - periodic:            retrain every PERIODIC_EVERY_N-th cycle (0-indexed),
                          regardless of drift or incumbent health.
  - performance_triggered: retrain iff evaluation_level == BAD. Ignores drift.
  - medp:                app.ml.policy.should_retrain (drift_level ==
                          SIGNIFICANT and evaluation_level != GOOD) -- the
                          paper's actual policy, used unmodified.
  - static:              retrain only on the very first cycle a model exists
                          (i.e. only when there is no champion yet); never
                          retrains again regardless of signal.
"""
from __future__ import annotations

from app.ml import policy as medp_policy

PERIODIC_EVERY_N = 2

POLICY_NAMES = ["drift_only", "periodic", "performance_triggered", "medp", "static"]


def drift_only(cycle_index: int, drift_level: str, evaluation_level: str, has_champion: bool) -> bool:
    return drift_level == "SIGNIFICANT"


def periodic(cycle_index: int, drift_level: str, evaluation_level: str, has_champion: bool) -> bool:
    return (cycle_index % PERIODIC_EVERY_N) == 0


def performance_triggered(cycle_index: int, drift_level: str, evaluation_level: str, has_champion: bool) -> bool:
    return evaluation_level == "BAD"


def medp(cycle_index: int, drift_level: str, evaluation_level: str, has_champion: bool) -> bool:
    return medp_policy.should_retrain(drift_level, evaluation_level)


def static(cycle_index: int, drift_level: str, evaluation_level: str, has_champion: bool) -> bool:
    return not has_champion


TRIGGER_FUNCS = {
    "drift_only": drift_only,
    "periodic": periodic,
    "performance_triggered": performance_triggered,
    "medp": medp,
    "static": static,
}

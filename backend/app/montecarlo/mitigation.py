"""Applies a user-chosen mitigation's effectiveness to Monte Carlo
params, for a before/after comparison. See config_data/mitigations.yaml
for the available actions per taxonomy group (not per the finer-grained
category - a documented scope simplification).
"""

from dataclasses import dataclass
from functools import lru_cache

import yaml

from app.config import CONFIG_DATA_DIR
from app.montecarlo.simulate import MonteCarloParams

MITIGATIONS_PATH = CONFIG_DATA_DIR / "mitigations.yaml"


@dataclass
class MitigationAction:
    name: str
    control_type: str  # prevent | reduce | transfer
    effectiveness_frequency: tuple[float, float] | None
    effectiveness_severity: tuple[float, float] | None


@lru_cache
def _load_playbooks() -> dict[str, list[MitigationAction]]:
    with open(MITIGATIONS_PATH, encoding="utf-8") as f:
        rows = yaml.safe_load(f)
    out: dict[str, list[MitigationAction]] = {}
    for row in rows:
        actions = [
            MitigationAction(
                name=a["name"],
                control_type=a["control_type"],
                effectiveness_frequency=tuple(a["effectiveness_frequency"])
                if "effectiveness_frequency" in a
                else None,
                effectiveness_severity=tuple(a["effectiveness_severity"])
                if "effectiveness_severity" in a
                else None,
            )
            for a in row["actions"]
        ]
        out[row["group"]] = actions
    return out


def actions_for_group(category_group: str | None) -> list[MitigationAction]:
    if category_group is None:
        return []
    return _load_playbooks().get(category_group, [])


def apply_mitigation(
    params: MonteCarloParams, effectiveness_frequency: float, effectiveness_severity: float
) -> MonteCarloParams:
    """Returns a NEW params object with p_annual and median_severity
    reduced by the given fractions (0-1 each) - the user's own slider
    values, not fixed to a playbook action's range.
    """
    e_f = min(max(effectiveness_frequency, 0.0), 0.95)
    e_s = min(max(effectiveness_severity, 0.0), 0.95)
    return MonteCarloParams(
        p_annual=params.p_annual * (1 - e_f),
        median_severity=params.median_severity * (1 - e_s),
        sigma=params.sigma,
        horizon_years=params.horizon_years,
        n_sims=params.n_sims,
        seed=params.seed,
    )

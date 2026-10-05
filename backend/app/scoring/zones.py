"""4T zone assignment from (probability, impact_norm). Thresholds are
configurable judgment calls, not fit to any dataset - see
docs/METHODOLOGY.md once written.

      low impact_norm   high impact_norm
low P    Tolerate           Transfer
high P   Treat              Terminate
"""

P_THRESHOLD = 0.20
IMPACT_THRESHOLD = 0.50

TOLERATE = "tolerate"
TREAT = "treat"
TRANSFER = "transfer"
TERMINATE = "terminate"


def assign_zone(
    p_mean: float,
    impact_norm: float,
    p_threshold: float = P_THRESHOLD,
    impact_threshold: float = IMPACT_THRESHOLD,
) -> str:
    high_p = p_mean >= p_threshold
    high_impact = impact_norm >= impact_threshold

    if high_p and high_impact:
        return TERMINATE
    if high_p:
        return TREAT
    if high_impact:
        return TRANSFER
    return TOLERATE

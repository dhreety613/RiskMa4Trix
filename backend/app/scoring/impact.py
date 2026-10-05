"""Impact as % of EBITDA (fallback % of market cap when EBITDA <= 0 or
missing) - math/finance, no LLM. Driver per category from
config_data/category_drivers.yaml; every fallback that fires gets
recorded (RiskScore.fallbacks) so the UI can show an "assumption-driven"
badge instead of presenting a guess as measured fact.
"""

import math
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

from app.config import CONFIG_DATA_DIR

DRIVERS_PATH = CONFIG_DATA_DIR / "category_drivers.yaml"

DEFAULT_REVENUE_SHARE = 0.10
DEFAULT_SHOCK = 0.15  # used when the company's own dd95_1y is unavailable
DEFAULT_RATE_SHOCK_BPS = 200

# impact_band thresholds on impact_pct_ebitda -> bands 1 (lowest) .. 5.
# Judgment calls, not fit to data - documented as configurable.
BAND_THRESHOLDS = [0.02, 0.05, 0.15, 0.40]

# Log-scale mapping range for impact_norm (0-1): 0.1% to 100% of EBITDA.
_NORM_LO, _NORM_HI = 0.001, 1.0


@dataclass
class ImpactResult:
    impact_usd: float
    impact_pct_ebitda: float
    impact_norm: float
    impact_band: int
    fallbacks: list[str] = field(default_factory=list)
    inputs: dict = field(default_factory=dict)


@lru_cache
def _load_drivers() -> dict[str, dict]:
    with open(DRIVERS_PATH, encoding="utf-8") as f:
        rows = yaml.safe_load(f)
    return {row["slug"]: row for row in rows}


def _impact_band(pct: float) -> int:
    for i, threshold in enumerate(BAND_THRESHOLDS):
        if pct < threshold:
            return i + 1
    return len(BAND_THRESHOLDS) + 1


def _normalize_impact(pct: float) -> float:
    pct = max(pct, 1e-6)
    log_pct = math.log(pct)
    log_lo, log_hi = math.log(_NORM_LO), math.log(_NORM_HI)
    norm = (log_pct - log_lo) / (log_hi - log_lo)
    return min(max(norm, 0.0), 1.0)


def compute_impact(
    category_slug: str | None,
    revenue: float | None,
    ebitda: float | None,
    total_debt: float | None,
    mcap: float | None,
    dd95_1y: float | None,
) -> ImpactResult:
    driver = _load_drivers().get(category_slug, {}) if category_slug else {}
    driver_type = driver.get("driver", "revenue_share")
    fallbacks: list[str] = []
    inputs: dict = {"category_slug": category_slug, "driver_type": driver_type}

    if driver_type == "interest_rate":
        rate_shock = driver.get("rate_shock_bps", DEFAULT_RATE_SHOCK_BPS) / 10000.0
        if total_debt is not None:
            exposure = total_debt
        else:
            exposure = (revenue or 0.0) * DEFAULT_REVENUE_SHARE
            fallbacks.append("total_debt unavailable - used revenue-share assumption as exposure")
        impact_usd = exposure * rate_shock
        inputs.update(exposure=exposure, rate_shock_bps=rate_shock * 10000.0)
    else:
        revenue_share = driver.get("revenue_share_assumption", DEFAULT_REVENUE_SHARE)
        if revenue is None:
            fallbacks.append("revenue unavailable - exposure computed as 0")
        exposure = (revenue or 0.0) * revenue_share
        if dd95_1y is not None:
            shock = dd95_1y
        else:
            shock = DEFAULT_SHOCK
            fallbacks.append(
                "price-based shock (dd95_1y) unavailable - used default shock assumption"
            )
        impact_usd = exposure * shock
        inputs.update(exposure=exposure, revenue_share=revenue_share, shock=shock)

    if ebitda is not None and ebitda > 0:
        impact_pct_ebitda = impact_usd / ebitda
        inputs["denominator"] = "ebitda"
    elif mcap:
        impact_pct_ebitda = impact_usd / mcap
        fallbacks.append("EBITDA <= 0 or unavailable - used market cap as denominator")
        inputs["denominator"] = "market_cap"
    else:
        impact_pct_ebitda = 0.0
        fallbacks.append("neither EBITDA nor market cap available - impact set to 0")
        inputs["denominator"] = "none"

    return ImpactResult(
        impact_usd=impact_usd,
        impact_pct_ebitda=impact_pct_ebitda,
        impact_norm=_normalize_impact(impact_pct_ebitda),
        impact_band=_impact_band(impact_pct_ebitda),
        fallbacks=fallbacks,
        inputs=inputs,
    )

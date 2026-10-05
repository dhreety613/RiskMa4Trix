"""Beta-Bernoulli probability update - math/finance, no LLM (hard rule).

Prior per category from config_data/category_priors.yaml:
    alpha0 = p0 * n0, beta0 = (1 - p0) * n0

Evidence over the trailing 12 months:
    k = number of distinct months with >=1 news item linked to this
        specific risk (news_risk_links - category match + similarity,
        see extract/pipeline.py)
    d = a drift pseudo-count: +1 if this risk's most recent appearance
        was flagged "new" by drift matching (a brand-new risk factor is
        itself a signal the underlying exposure is freshly live)

Posterior: Beta(alpha0 + k + d, beta0 + (12 - k)), mean + 90% CI.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

import yaml
from scipy import stats
from sqlalchemy.orm import Session

from app.config import CONFIG_DATA_DIR
from app.models import DriftEvent, NewsItem, NewsRiskLink, Risk

PRIORS_PATH = CONFIG_DATA_DIR / "category_priors.yaml"

DEFAULT_P0 = 0.10
DEFAULT_N0 = 10
TRAILING_MONTHS = 12
DRIFT_NEW_PSEUDO_COUNT = 1


@dataclass
class ProbabilityResult:
    p_mean: float
    p_lo: float
    p_hi: float
    alpha: float
    beta: float
    evidence_months: int
    drift_pseudo_count: int
    used_default_prior: bool


@lru_cache
def _load_priors() -> dict[str, dict]:
    with open(PRIORS_PATH, encoding="utf-8") as f:
        rows = yaml.safe_load(f)
    return {row["slug"]: row for row in rows}


def _prior_for_category(category_slug: str | None) -> tuple[float, float, bool]:
    if category_slug is None:
        return DEFAULT_P0, DEFAULT_N0, True
    row = _load_priors().get(category_slug)
    if row is None:
        return DEFAULT_P0, DEFAULT_N0, True
    return row["p0"], row["n0"], False


def _evidence_months(db: Session, risk: Risk) -> int:
    cutoff = datetime.utcnow() - timedelta(days=365)
    rows = (
        db.query(NewsItem.published_at)
        .join(NewsRiskLink, NewsRiskLink.news_id == NewsItem.id)
        .filter(NewsRiskLink.risk_id == risk.id, NewsItem.published_at >= cutoff)
        .all()
    )
    months = {(d.year, d.month) for (d,) in rows}
    return min(len(months), TRAILING_MONTHS)


def _drift_pseudo_count(db: Session, risk: Risk) -> int:
    is_new = (
        db.query(DriftEvent)
        .filter(DriftEvent.risk_id == risk.id, DriftEvent.label == "new")
        .first()
        is not None
    )
    return DRIFT_NEW_PSEUDO_COUNT if is_new else 0


def compute_probability(db: Session, risk: Risk, category_slug: str | None) -> ProbabilityResult:
    p0, n0, used_default = _prior_for_category(category_slug)
    alpha0 = p0 * n0
    beta0 = (1 - p0) * n0

    k = _evidence_months(db, risk)
    d = _drift_pseudo_count(db, risk)

    alpha = alpha0 + k + d
    beta_param = beta0 + (TRAILING_MONTHS - k)

    p_mean = alpha / (alpha + beta_param)
    p_lo, p_hi = stats.beta.ppf([0.05, 0.95], alpha, beta_param)

    return ProbabilityResult(
        p_mean=float(p_mean),
        p_lo=float(p_lo),
        p_hi=float(p_hi),
        alpha=float(alpha),
        beta=float(beta_param),
        evidence_months=k,
        drift_pseudo_count=d,
        used_default_prior=used_default,
    )

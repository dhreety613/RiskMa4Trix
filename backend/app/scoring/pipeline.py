"""Scores every active risk in a company's MOST RECENT filing (scoring
is for the "live" matrix, not a historical restatement of old filings).
Idempotent: clears existing RiskScore rows for these risks before
writing fresh ones.
"""

from sqlalchemy.orm import Session

from app.models import Company, Filing, FinancialFact, PriceStat, Risk, RiskScore, Taxonomy
from app.scoring.impact import compute_impact
from app.scoring.probability import compute_probability
from app.scoring.zones import assign_zone


def _latest_filing(db: Session, company: Company) -> Filing | None:
    return (
        db.query(Filing)
        .filter(Filing.company_id == company.id)
        .order_by(Filing.fiscal_year.desc())
        .first()
    )


def _financial_facts(db: Session, company_id: int, fiscal_year: int) -> dict[str, float]:
    rows = (
        db.query(FinancialFact)
        .filter(FinancialFact.company_id == company_id, FinancialFact.fiscal_year == fiscal_year)
        .all()
    )
    return {row.metric: row.value for row in rows}


def _latest_price_stat(db: Session, company_id: int) -> PriceStat | None:
    return (
        db.query(PriceStat)
        .filter(PriceStat.company_id == company_id)
        .order_by(PriceStat.as_of.desc())
        .first()
    )


def score_company_risks(db: Session, company: Company) -> int:
    """Returns the number of RiskScore rows written."""
    filing = _latest_filing(db, company)
    if filing is None:
        return 0

    risks = db.query(Risk).filter(Risk.filing_id == filing.id, Risk.status == "active").all()
    if not risks:
        return 0

    facts = _financial_facts(db, company.id, filing.fiscal_year)
    price_stat = _latest_price_stat(db, company.id)
    category_slugs = {row.id: row.slug for row in db.query(Taxonomy).all()}

    risk_ids = [r.id for r in risks]
    db.query(RiskScore).filter(RiskScore.risk_id.in_(risk_ids)).delete(synchronize_session=False)

    for risk in risks:
        category_slug = category_slugs.get(risk.category_id) if risk.category_id else None

        probability = compute_probability(db, risk, category_slug)
        impact = compute_impact(
            category_slug=category_slug,
            revenue=facts.get("revenue"),
            ebitda=facts.get("ebitda"),
            total_debt=facts.get("total_debt"),
            mcap=price_stat.mcap if price_stat else None,
            dd95_1y=price_stat.dd95_1y if price_stat else None,
        )
        expected_loss = probability.p_mean * impact.impact_usd
        zone = assign_zone(probability.p_mean, impact.impact_norm)

        fallbacks = list(impact.fallbacks)
        if probability.used_default_prior:
            fallbacks.append("category has no configured prior - used a generic default")

        db.add(
            RiskScore(
                risk_id=risk.id,
                p_mean=probability.p_mean,
                p_lo=probability.p_lo,
                p_hi=probability.p_hi,
                alpha=probability.alpha,
                beta=probability.beta,
                impact_usd=impact.impact_usd,
                impact_pct_ebitda=impact.impact_pct_ebitda,
                impact_norm=impact.impact_norm,
                impact_band=impact.impact_band,
                expected_loss=expected_loss,
                zone=zone,
                inputs_json={
                    **impact.inputs,
                    "evidence_months": probability.evidence_months,
                    "drift_pseudo_count": probability.drift_pseudo_count,
                    "fiscal_year": filing.fiscal_year,
                },
                fallbacks={"items": fallbacks},
            )
        )

    db.flush()
    return len(risks)

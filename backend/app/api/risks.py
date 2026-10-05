from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, Risk, RiskScore, Taxonomy
from app.schemas import RiskCardOut

router = APIRouter(prefix="/risks", tags=["risks"])


@router.get("/{risk_id}", response_model=RiskCardOut)
def get_risk_card(risk_id: int, db: Session = Depends(get_db)) -> RiskCardOut:
    risk = db.query(Risk).filter(Risk.id == risk_id).one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")

    score = db.query(RiskScore).filter(RiskScore.risk_id == risk_id).one_or_none()
    taxonomy = (
        db.query(Taxonomy).filter(Taxonomy.id == risk.category_id).one_or_none()
        if risk.category_id
        else None
    )
    company = db.query(Company).filter(Company.id == risk.company_id).one_or_none()

    fallbacks = list(score.fallbacks.get("items", [])) if score and score.fallbacks else []

    return RiskCardOut(
        risk_id=risk.id,
        ticker=company.ticker if company else "",
        title=risk.title,
        text_excerpt=risk.text[:600],
        category=taxonomy.slug if taxonomy else None,
        category_name=taxonomy.name if taxonomy else None,
        zone=score.zone if score else None,
        p_mean=score.p_mean if score else None,
        p_lo=score.p_lo if score else None,
        p_hi=score.p_hi if score else None,
        impact_usd=score.impact_usd if score else None,
        impact_pct_ebitda=score.impact_pct_ebitda if score else None,
        expected_loss=score.expected_loss if score else None,
        is_generic=risk.is_generic,
        generic_score=risk.generic_score,
        is_assumption_driven=bool(fallbacks),
        fallbacks=fallbacks,
        can_run_monte_carlo=(score.zone == "treat") if score else False,
    )

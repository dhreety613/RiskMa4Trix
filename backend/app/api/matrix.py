from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, Filing, Risk, RiskScore, Taxonomy
from app.schemas import MatrixPointOut

router = APIRouter(prefix="/companies", tags=["matrix"])


@router.get("/{ticker}/matrix", response_model=list[MatrixPointOut])
def get_matrix(
    ticker: str,
    year: int | None = Query(default=None, description="Fiscal year; defaults to latest"),
    zone: str | None = Query(default=None, description="tolerate|treat|transfer|terminate"),
    category: str | None = Query(default=None, description="Taxonomy slug"),
    include_generic: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[MatrixPointOut]:
    company = db.query(Company).filter(Company.ticker == ticker.upper()).one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail=f"{ticker!r} not ingested yet")

    filing_query = db.query(Filing).filter(Filing.company_id == company.id)
    if year is not None:
        filing = filing_query.filter(Filing.fiscal_year == year).one_or_none()
    else:
        filing = filing_query.order_by(Filing.fiscal_year.desc()).first()
    if filing is None:
        return []

    query = (
        db.query(Risk, RiskScore, Taxonomy)
        .join(RiskScore, RiskScore.risk_id == Risk.id)
        .outerjoin(Taxonomy, Taxonomy.id == Risk.category_id)
        .filter(Risk.filing_id == filing.id, Risk.status == "active")
    )
    if not include_generic:
        query = query.filter(Risk.is_generic.is_(False))
    if zone:
        query = query.filter(RiskScore.zone == zone)
    if category:
        query = query.filter(Taxonomy.slug == category)

    points = []
    for risk, score, taxonomy in query.all():
        points.append(
            MatrixPointOut(
                risk_id=risk.id,
                title=risk.title,
                category=taxonomy.slug if taxonomy else None,
                category_name=taxonomy.name if taxonomy else None,
                p_mean=score.p_mean,
                impact_norm=score.impact_norm,
                impact_pct_ebitda=score.impact_pct_ebitda,
                expected_loss=score.expected_loss,
                zone=score.zone,
                is_generic=risk.is_generic,
                is_assumption_driven=bool(score.fallbacks and score.fallbacks.get("items")),
            )
        )
    return points

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, DriftEvent, Filing, Risk
from app.schemas import DriftEventOut

router = APIRouter(prefix="/companies", tags=["drift"])


@router.get("/{ticker}/drift", response_model=list[DriftEventOut])
def get_drift(ticker: str, db: Session = Depends(get_db)) -> list[DriftEventOut]:
    company = db.query(Company).filter(Company.ticker == ticker.upper()).one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail=f"{ticker!r} not ingested yet")

    events = (
        db.query(DriftEvent)
        .filter(DriftEvent.company_id == company.id)
        .order_by(DriftEvent.to_filing_id)
        .all()
    )

    filings = {f.id: f for f in db.query(Filing).filter(Filing.company_id == company.id).all()}
    risks = {r.id: r for r in db.query(Risk).filter(Risk.company_id == company.id).all()}

    out = []
    for e in events:
        curr_risk = risks.get(e.risk_id) if e.risk_id else None
        prev_risk = risks.get(e.prev_risk_id) if e.prev_risk_id else None
        risk = curr_risk or prev_risk
        to_filing = filings.get(e.to_filing_id)
        from_filing = filings.get(e.from_filing_id) if e.from_filing_id else None
        out.append(
            DriftEventOut(
                id=e.id,
                from_fiscal_year=from_filing.fiscal_year if from_filing else None,
                to_fiscal_year=to_filing.fiscal_year if to_filing else 0,
                label=e.label,
                similarity=e.similarity,
                title=risk.title if risk else "",
                category_id=risk.category_id if risk else None,
            )
        )
    return out
